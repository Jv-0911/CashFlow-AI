from dataclasses import replace
from hashlib import sha256
import json

import pytest

from backend.app.forecast.persistence import LocalModelRegistry
from backend.app.forecast.trained import forecast_trained_model
from backend.tests.forecast.test_trained import train


def registry(tmp_path):
    return LocalModelRegistry(tmp_path / "models")


def edit_manifest(registry, changes, business_id="business_a", version="v1"):
    path = registry.root / business_id / version / "manifest.json"
    manifest = json.loads(path.read_text())
    changes(manifest)
    path.write_text(json.dumps(manifest))


@pytest.mark.parametrize("ml", [False, True])
def test_saved_model_reload_produces_equivalent_predictions(tmp_path, ml):
    store = registry(tmp_path)
    bundle = train(84 if ml else 42, trend=ml, ml=ml)
    assert store.save_candidate(bundle) == bundle.metadata
    loaded = store.load("business_a", "v1", expected_currency="USD", expected_metadata=bundle.metadata)
    assert loaded.metadata == bundle.metadata
    assert loaded.history == bundle.history
    assert forecast_trained_model(loaded) == forecast_trained_model(bundle)
    assert store.get_status("business_a").candidate_versions == ("v1",)


def test_versions_are_immutable_and_isolated(tmp_path):
    store = registry(tmp_path)
    first, second = train(), train(43, version="v2")
    store.save_candidate(first)
    store.save_candidate(second)
    with pytest.raises(ValueError, match="immutable"):
        store.save_candidate(first)
    assert store.load("business_a", "v1").history != store.load("business_a", "v2").history


def test_business_models_and_registry_state_are_isolated(tmp_path):
    store = registry(tmp_path)
    a, b = train(), train(business_id="business_b")
    store.save_candidate(a)
    store.save_candidate(b)
    store.promote("business_a", "v1")
    assert store.get_status("business_b").active_version is None
    assert store.load("business_b", "v1").metadata.business_id == "business_b"
    assert a.metadata.model_id != b.metadata.model_id
    with pytest.raises(ValueError):
        store.load("business_b", "other")
    with pytest.raises(ValueError, match="expected metadata"):
        store.load("business_b", "v1", expected_metadata=a.metadata)


@pytest.mark.parametrize("incompatibility", ["feature", "dependency", "business", "version", "format", "filename", "currency", "model_id"])
def test_incompatibilities_are_rejected_before_deserialization(tmp_path, monkeypatch, incompatibility):
    store = registry(tmp_path)
    store.save_candidate(train())
    def change(manifest):
        if incompatibility == "feature":
            manifest["metadata"]["feature_schema_version"] = "unknown"
        elif incompatibility == "dependency":
            manifest["metadata"]["dependency_versions"]["scikit-learn"] = "0.0"
        elif incompatibility == "business":
            manifest["metadata"]["business_id"] = "business_b"
        elif incompatibility == "version":
            manifest["metadata"]["model_version"] = "v2"
        elif incompatibility == "format":
            manifest["manifest_version"] = 99
        elif incompatibility == "filename":
            manifest["artifact_filename"] = "../../unsafe.joblib"
        elif incompatibility == "currency":
            manifest["metadata"]["currency"] = "EUR"
        elif incompatibility == "model_id":
            manifest["metadata"]["model_id"] = "incorrect"
    edit_manifest(store, change)
    monkeypatch.setattr("backend.app.forecast.persistence.joblib.load", lambda *args, **kwargs: pytest.fail("unsafe deserialization attempted"))
    with pytest.raises(ValueError):
        store.load("business_a", "v1", expected_currency="USD")


def test_corrupt_checksum_rejected_before_deserialization(tmp_path, monkeypatch):
    store = registry(tmp_path)
    store.save_candidate(train())
    path = store.root / "business_a" / "v1" / "model.joblib"
    path.write_bytes(path.read_bytes() + b"corruption")
    monkeypatch.setattr("backend.app.forecast.persistence.joblib.load", lambda *args, **kwargs: pytest.fail("unsafe deserialization attempted"))
    with pytest.raises(ValueError, match="checksum"):
        store.load("business_a", "v1")


def test_invalid_correctly_hashed_trusted_artifact_is_rejected(tmp_path):
    store = registry(tmp_path)
    store.save_candidate(train())
    path = store.root / "business_a" / "v1" / "model.joblib"
    path.write_bytes(b"not a model")
    edit_manifest(store, lambda manifest: manifest.update(artifact_sha256=sha256(path.read_bytes()).hexdigest()))
    with pytest.raises(ValueError, match="invalid trusted"):
        store.load("business_a", "v1")


def test_promotion_failure_preserves_active_model_and_rollback(tmp_path):
    store = registry(tmp_path)
    for version in ("v1", "v2", "bad"):
        store.save_candidate(train(version=version))
    store.promote("business_a", "v1", expected_active_version=None)
    store.promote("business_a", "v2", expected_active_version="v1")
    bad = store.root / "business_a" / "bad" / "model.joblib"
    bad.write_bytes(b"broken")
    with pytest.raises(ValueError):
        store.promote("business_a", "bad", expected_active_version="v2")
    assert store.get_status("business_a").active_version == "v2"
    store.mark_failed("business_a", "bad", "artifact validation failed")
    assert "bad" in store.get_status("business_a").failed_versions
    assert store.rollback("business_a").model_version == "v1"
    assert store.get_status("business_a").active_version == "v1"
    assert store.get_status("business_a").previous_versions == ("v2",)


def test_concurrent_incumbent_change_rejects_stale_promotion(tmp_path):
    store = registry(tmp_path)
    for version in ("v1", "v2", "v3"):
        store.save_candidate(train(version=version))
    store.promote("business_a", "v1")
    store.promote("business_a", "v2", expected_active_version="v1")
    with pytest.raises(ValueError, match="changed during"):
        store.promote("business_a", "v3", expected_active_version="v1")
    assert store.get_status("business_a").active_version == "v2"


def test_failed_candidate_and_missing_rollback_are_explicit(tmp_path):
    store = registry(tmp_path)
    store.mark_failed("business_a", "bad", "training failure")
    assert store.get_status("business_a").active_version is None
    with pytest.raises(ValueError):
        store.promote("business_a", "bad")
    with pytest.raises(ValueError, match="no previous"):
        store.rollback("business_a")
    with pytest.raises(ValueError, match="immutable"):
        store.save_candidate(train(version="bad"))


@pytest.mark.parametrize("business_id,model_version", [("../outside", "v1"), ("business_a", "../v1"), ("a/b", "v1"), ("business_a", "/absolute")])
def test_registry_rejects_path_traversal(tmp_path, business_id, model_version):
    store = registry(tmp_path)
    with pytest.raises(ValueError):
        store.load(business_id, model_version)


@pytest.mark.parametrize("location", ["root", "business", "version", "manifest", "artifact"])
def test_registry_rejects_symlinks(tmp_path, location):
    store = registry(tmp_path)
    store.save_candidate(train())
    outside = tmp_path / "outside"
    if location == "root":
        link = tmp_path / "root_link"
        link.symlink_to(store.root, target_is_directory=True)
        with pytest.raises(ValueError, match="symlink"):
            LocalModelRegistry(link)
        return
    if location == "business":
        link = store.root / "business_b"
        link.symlink_to(store.root / "business_a", target_is_directory=True)
        with pytest.raises(ValueError, match="symlink"):
            store.load("business_b", "v1")
        return
    if location == "version":
        link = store.root / "business_a" / "v2"
        link.symlink_to(store.root / "business_a" / "v1", target_is_directory=True)
        with pytest.raises(ValueError, match="symlink"):
            store.load("business_a", "v2")
        return
    target = store.root / "business_a" / "v1" / ("manifest.json" if location == "manifest" else "model.joblib")
    target.rename(outside)
    target.symlink_to(outside)
    with pytest.raises(ValueError):
        store.load("business_a", "v1")


def test_failed_atomic_save_keeps_active_and_does_not_record_candidate(tmp_path, monkeypatch):
    store = registry(tmp_path)
    store.save_candidate(train())
    store.promote("business_a", "v1")
    monkeypatch.setattr("backend.app.forecast.persistence.joblib.dump", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("simulated write failure")))
    with pytest.raises(RuntimeError):
        store.save_candidate(train(version="v2"))
    state = store.get_status("business_a")
    assert state.active_version == "v1" and not state.candidate_versions
    assert not (store.root / "business_a" / "v2").exists()
    assert not tuple((store.root / "business_a").glob(".candidate-*"))


def test_retraining_decisions_are_atomic_business_scoped_json(tmp_path):
    store = registry(tmp_path)
    first = {"business_id": "business_a", "decision": "retained", "final_evaluation_end": "2026-02-01"}
    store.record_decision("business_a", first)
    store.record_decision("business_a", {"decision": "insufficient_new_data"})
    assert store.get_decisions("business_a") == (first, {"decision": "insufficient_new_data"})
    assert store.get_decisions("business_b") == ()
    with pytest.raises(ValueError, match="business identity"):
        store.record_decision("business_b", first)
    with pytest.raises(ValueError):
        store.record_decision("business_a", {"score": float("nan")})


def test_promotion_evidence_survives_manifest_and_reload(tmp_path):
    bundle = train()
    bundle = replace(bundle, metadata=bundle.metadata.model_copy(update={"promotion_evidence": {"independent_holdout": True, "evaluation_end": "2026-03-01"}}))
    store = registry(tmp_path)
    store.save_candidate(bundle)
    assert store.load("business_a", "v1").metadata.promotion_evidence == bundle.metadata.promotion_evidence


def test_active_and_previous_versions_cannot_be_marked_failed_candidates(tmp_path):
    store = registry(tmp_path)
    for version in ("v1", "v2"):
        store.save_candidate(train(version=version))
        store.promote("business_a", version)
    for version in ("v1", "v2"):
        with pytest.raises(ValueError, match="deployed model"):
            store.mark_failed("business_a", version, "not a candidate")
    assert store.get_status("business_a").active_version == "v2"


def test_registry_rejects_wrong_business_pointer_manifest(tmp_path):
    store = registry(tmp_path)
    store.save_candidate(train())
    path = store.root / "business_a" / "registry.json"
    state = json.loads(path.read_text())
    state["business_id"] = "business_b"
    path.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="business identity"):
        store.get_status("business_a")


def test_registry_rejects_fifo_without_blocking(tmp_path):
    import os
    store = registry(tmp_path)
    store.save_candidate(train())
    path = store.root / "business_a" / "v1" / "manifest.json"
    path.unlink()
    os.mkfifo(path)
    with pytest.raises(ValueError, match="regular file"):
        store.load("business_a", "v1")


def test_retraining_lock_allows_short_registry_operations_inside_context(tmp_path):
    store = registry(tmp_path)
    with store.retraining_lock("business_a"):
        assert store.get_status("business_a").active_version is None
        store.record_decision("business_a", {"decision": "reserved"})
        assert store.get_decisions("business_a") == ({"decision": "reserved"},)
    assert (store.root / "business_a" / ".retraining.lock").is_file()
    with store.retraining_lock("business_a"):
        assert len(store.get_decisions("business_a")) == 1


def test_retraining_lock_rejects_symlink(tmp_path):
    store = registry(tmp_path)
    store.get_status("business_a")
    outside = tmp_path / "outside.lock"
    outside.write_bytes(b"")
    (store.root / "business_a" / ".retraining.lock").symlink_to(outside)
    with pytest.raises(ValueError, match="unsafe"):
        with store.retraining_lock("business_a"):
            pytest.fail("unsafe retraining lock entered")
