"""Atomic local registry for trusted, service-produced forecasting artifacts.

Hashes detect corruption, not a compromised registry owner. Pickle-based joblib
must never receive user uploads; authentication and service-owned storage remain
the integrating application's responsibility.
"""

from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import stat
from uuid import uuid4

import fcntl
import joblib
from pydantic import TypeAdapter

from .persistence_schemas import ArtifactManifest, ModelMetadata, RegistryState, SafeIdentifier
from .trained import FEATURE_SCHEMA_VERSION, TrainedForecastModel, dependency_versions, validate_trained_model


_UNSET = object()
_MAX_MANIFEST_BYTES = 2 * 1024 * 1024
_MAX_ARTIFACT_BYTES = 128 * 1024 * 1024


class LocalModelRegistry:
    """Small POSIX filesystem registry; configure one trusted root in backend code.

    Each business receives immutable model-version directories and an atomic
    pointer manifest. Advisory flock serializes cooperating service operations.
    The root must not be writable by upload clients or other untrusted users.
    """

    def __init__(self, root: Path):
        self._root = Path(os.path.abspath(root))
        for path in (self._root, *self._root.parents):
            if path.is_symlink():
                raise ValueError("model registry root must not contain symlinks")
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._check_directory(self._root)

    @property
    def root(self) -> Path:
        return self._root

    @staticmethod
    def _identifier(value: str) -> str:
        return TypeAdapter(SafeIdentifier).validate_python(value)

    @staticmethod
    def _check_directory(path: Path):
        if path.is_symlink() or not path.is_dir():
            raise ValueError("model registry directories must be real directories, not symlinks")

    def _business_path(self, business_id: str) -> Path:
        business_id = self._identifier(business_id)
        self._check_directory(self._root)
        path = self._root / business_id
        if path.is_symlink():
            raise ValueError("business registry path must not be a symlink")
        path.mkdir(mode=0o700, exist_ok=True)
        self._check_directory(path)
        return path

    @contextmanager
    def _file_locked(self, business_id, lock_filename):
        path = self._business_path(business_id)
        try:
            fd = os.open(path / lock_filename, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        except OSError as exc:
            raise ValueError("registry lock is missing or unsafe") from exc
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("registry lock must be a regular file")
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield path
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    @contextmanager
    def _locked(self, business_id):
        with self._file_locked(business_id, ".registry.lock") as path:
            yield path

    @contextmanager
    def retraining_lock(self, business_id: str):
        """Serialize complete per-business evaluations using a separate lock.

        Registry reads and mutations remain callable inside this context because
        their short lock uses a different file. This context is deliberately not
        reentrant; the application should acquire it once per retraining request.
        """
        with self._file_locked(business_id, ".retraining.lock"):
            yield

    @staticmethod
    def _read(path: Path, maximum: int) -> bytes:
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
                raise ValueError("registry file is not a regular file within supported size limits")
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as exc:
            raise ValueError(f"registry file is missing or unsafe: {path.name}") from exc
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
                raise ValueError("registry file is not a regular file within supported size limits")
            data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError("registry file exceeds supported size limits")
        return data

    @staticmethod
    def _atomic_json(path: Path, payload: object):
        if path.is_symlink():
            raise ValueError("registry JSON destination must not be a symlink")
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if len(data) > _MAX_MANIFEST_BYTES:
            raise ValueError("registry JSON exceeds supported size limits")
        temporary = path.parent / (".write-" + uuid4().hex)
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _state(self, path: Path, business_id: str) -> RegistryState:
        target = path / "registry.json"
        if not target.exists() and not target.is_symlink():
            return RegistryState(business_id=business_id)
        state = RegistryState.model_validate_json(self._read(target, _MAX_MANIFEST_BYTES))
        if state.business_id != business_id:
            raise ValueError("registry business identity does not match the requested business")
        return state

    @staticmethod
    def _update(path: Path, state: RegistryState, **changes) -> RegistryState:
        updated = RegistryState.model_validate({**state.model_dump(), **changes})
        LocalModelRegistry._atomic_json(path / "registry.json", updated.model_dump(mode="json"))
        return updated

    @staticmethod
    def _compatibility(metadata: ModelMetadata, business_id: str, model_version: str,
                       expected_currency=None, expected_metadata=None):
        if metadata.business_id != business_id or metadata.model_version != model_version:
            raise ValueError("artifact metadata business or model version does not match its registry path")
        expected_model_id = "model-" + sha256(f"{business_id}:{model_version}".encode()).hexdigest()[:20]
        if metadata.model_id != expected_model_id:
            raise ValueError("artifact model identifier is incompatible with its business and version")
        if expected_currency is not None and metadata.currency != expected_currency:
            raise ValueError("artifact currency is incompatible with the requested business history")
        if metadata.feature_schema_version != FEATURE_SCHEMA_VERSION:
            raise ValueError("artifact feature schema is incompatible with this runtime")
        if metadata.dependency_versions != dependency_versions():
            raise ValueError("artifact dependency versions are incompatible with this runtime")
        if expected_metadata is not None and metadata != expected_metadata:
            raise ValueError("artifact metadata does not match expected metadata")

    def save_candidate(self, bundle: TrainedForecastModel) -> ModelMetadata:
        """Save an immutable version before atomically recording it as a candidate."""
        validate_trained_model(bundle)
        metadata = bundle.metadata
        self._compatibility(metadata, metadata.business_id, metadata.model_version)
        with self._locked(metadata.business_id) as path:
            state = self._state(path, metadata.business_id)
            destination = path / metadata.model_version
            if destination.exists() or destination.is_symlink() or metadata.model_version in state.failed_versions:
                raise ValueError("model versions are immutable; use a new version identifier")
            staging = path / (".candidate-" + uuid4().hex)
            staging.mkdir(mode=0o700)
            try:
                artifact = staging / "model.joblib"
                joblib.dump(bundle, artifact, compress=3)
                os.chmod(artifact, 0o600)
                data = self._read(artifact, _MAX_ARTIFACT_BYTES)
                manifest = ArtifactManifest(metadata=metadata, artifact_sha256=sha256(data).hexdigest())
                self._atomic_json(staging / "manifest.json", manifest.model_dump(mode="json"))
                # No overwrite of an existing nonempty immutable version directory.
                os.rename(staging, destination)
                self._update(path, state, candidate_versions=state.candidate_versions + (metadata.model_version,))
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        return metadata

    def _load(self, path: Path, business_id: str, model_version: str, *, expected_currency=None,
              expected_metadata=None) -> TrainedForecastModel:
        self._identifier(model_version)
        version_path = path / model_version
        self._check_directory(version_path)
        manifest = ArtifactManifest.model_validate_json(self._read(version_path / "manifest.json", _MAX_MANIFEST_BYTES))
        self._compatibility(manifest.metadata, business_id, model_version, expected_currency, expected_metadata)
        data = self._read(version_path / manifest.artifact_filename, _MAX_ARTIFACT_BYTES)
        if sha256(data).hexdigest() != manifest.artifact_sha256:
            raise ValueError("artifact checksum mismatch; refusing deserialization")
        # Deserialize the identical bytes already checked, not a reopened mutable path.
        try:
            bundle = joblib.load(BytesIO(data))
            validate_trained_model(bundle)
        except Exception as exc:
            raise ValueError("invalid trusted model artifact") from exc
        if bundle.metadata != manifest.metadata:
            raise ValueError("artifact runtime metadata does not match the manifest")
        return bundle

    def load(self, business_id: str, model_version: str, *, expected_currency=None,
             expected_metadata: ModelMetadata | None = None) -> TrainedForecastModel:
        """Load only a named business version beneath this configured trusted root."""
        self._identifier(model_version)
        with self._locked(business_id) as path:
            self._state(path, business_id)
            return self._load(path, business_id, model_version, expected_currency=expected_currency,
                              expected_metadata=expected_metadata)

    def get_status(self, business_id: str) -> RegistryState:
        with self._locked(business_id) as path:
            return self._state(path, business_id)

    def promote(self, business_id: str, model_version: str, *, expected_active_version=_UNSET) -> ModelMetadata:
        """Promote a validated candidate; scientific eligibility is the caller's gate."""
        self._identifier(model_version)
        if expected_active_version is not _UNSET and expected_active_version is not None:
            self._identifier(expected_active_version)
        with self._locked(business_id) as path:
            state = self._state(path, business_id)
            if expected_active_version is not _UNSET and state.active_version != expected_active_version:
                raise ValueError("active model changed during candidate evaluation; promotion rejected")
            if model_version not in state.candidate_versions or model_version in state.failed_versions:
                raise ValueError("promotion requires a valid recorded candidate")
            bundle = self._load(path, business_id, model_version)
            previous = tuple(dict.fromkeys(
                (() if state.active_version is None else (state.active_version,)) + state.previous_versions
            ))
            self._update(path, state, active_version=model_version, previous_versions=previous,
                         candidate_versions=tuple(item for item in state.candidate_versions if item != model_version))
            return bundle.metadata

    def rollback(self, business_id: str) -> ModelMetadata:
        """Activate the most recent previous version only after successful validation."""
        with self._locked(business_id) as path:
            state = self._state(path, business_id)
            if not state.previous_versions:
                raise ValueError("no previous model version is available for rollback")
            previous = state.previous_versions[0]
            bundle = self._load(path, business_id, previous)
            remaining = state.previous_versions[1:]
            if state.active_version is not None:
                remaining = (state.active_version,) + remaining
            self._update(path, state, active_version=previous, previous_versions=remaining)
            return bundle.metadata

    def mark_failed(self, business_id: str, model_version: str, reason: str) -> RegistryState:
        """Record a bounded candidate failure without changing the active version."""
        self._identifier(model_version)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise ValueError("failure reason must be a nonblank string of at most 2000 characters")
        with self._locked(business_id) as path:
            state = self._state(path, business_id)
            if model_version == state.active_version or model_version in state.previous_versions:
                raise ValueError("a deployed model cannot be marked as a failed candidate")
            failed = {**state.failed_versions, model_version: reason}
            return self._update(path, state, failed_versions=failed,
                                candidate_versions=tuple(item for item in state.candidate_versions if item != model_version))

    def _decisions(self, path: Path, business_id: str) -> tuple[dict, ...]:
        target = path / "decisions.json"
        if not target.exists() and not target.is_symlink():
            return ()
        data = json.loads(self._read(target, _MAX_MANIFEST_BYTES))
        if not isinstance(data, dict) or data.get("business_id") != business_id or not isinstance(data.get("decisions"), list) or any(not isinstance(item, dict) for item in data["decisions"]):
            raise ValueError("invalid business-scoped retraining decision history")
        return tuple(data["decisions"])

    def get_decisions(self, business_id: str) -> tuple[dict, ...]:
        with self._locked(business_id) as path:
            self._state(path, business_id)
            return self._decisions(path, business_id)

    def record_decision(self, business_id: str, decision: dict) -> None:
        """Record JSON evaluation evidence supplied by the trusted retraining service."""
        if not isinstance(decision, dict):
            raise ValueError("retraining decision must be a JSON object")
        json.dumps(decision, allow_nan=False)
        if decision.get("business_id", business_id) != business_id:
            raise ValueError("decision business identity does not match the registry")
        with self._locked(business_id) as path:
            self._state(path, business_id)
            decisions = self._decisions(path, business_id) + (decision,)
            self._atomic_json(path / "decisions.json", {"business_id": business_id, "decisions": decisions})
