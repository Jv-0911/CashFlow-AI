import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

function checkWebglSupport(): boolean {
  if (typeof window === 'undefined') return true;
  try {
    const canvas = document.createElement('canvas');
    return !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
  } catch {
    return false;
  }
}

function checkReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Muted, matte color palette tokens for financial ribbons:
 * - Slate blue:        #607D98 (0x607D98)
 * - Muted steel blue:  #7896B0 (0x7896B0)
 * - Dusty indigo:      #666A91 (0x666A91)
 * - Soft muted mauve:  #9A758D (0x9A758D)
 * - Background anchor: #0B1018 (0x0B1018)
 */
const PALETTE = {
  slateBlue: 0x607d98,
  steelBlue: 0x7896b0,
  dustyIndigo: 0x666a91,
  softMauve: 0x9a758d,
  bgNavy: 0x0b1018,
};

interface RibbonConfig {
  baseY: number;
  amplitude1: number;
  amplitude2: number;
  freq1: number;
  freq2: number;
  speed: number;
  color: number;
  opacity: number;
  width: number;
  zDepth: number;
  phaseOffset: number;
  hasDipRecovery?: boolean;
}

export function HeroScene() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [webglSupported, setWebglSupported] = useState<boolean>(checkWebglSupport);
  const [isLowMotion, setIsLowMotion] = useState<boolean>(checkReducedMotion);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handleMotionChange = (e: MediaQueryListEvent) => {
      setIsLowMotion(e.matches);
    };
    mediaQuery.addEventListener('change', handleMotionChange);

    return () => {
      mediaQuery.removeEventListener('change', handleMotionChange);
    };
  }, []);

  useEffect(() => {
    if (!webglSupported) return;
    const container = containerRef.current;
    if (!container) return;

    let animationFrameId: number;
    let renderer: THREE.WebGLRenderer | null = null;

    try {
      // Scene setup
      const scene = new THREE.Scene();

      // Camera setup
      const camera = new THREE.PerspectiveCamera(
        42,
        container.clientWidth / container.clientHeight,
        0.1,
        100
      );
      camera.position.set(0, 0, 7.5);

      // Renderer setup
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: 'high-performance',
      });
      renderer.setSize(container.clientWidth, container.clientHeight);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      container.appendChild(renderer.domElement);

      const rootGroup = new THREE.Group();
      scene.add(rootGroup);

      // -------------------------------------------------------------
      // 1. Subtle Ledger Grid & Coordinate Markers (Decorative)
      // -------------------------------------------------------------
      const gridLinesGroup = new THREE.Group();
      rootGroup.add(gridLinesGroup);

      const gridMat = new THREE.LineBasicMaterial({
        color: 0x666a91,
        transparent: true,
        opacity: 0.08,
      });

      // 3 subtle horizontal datum lines
      [-1.4, 0.0, 1.4].forEach((yPos) => {
        const lineGeo = new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(-8, yPos, -1.5),
          new THREE.Vector3(8, yPos, -1.5),
        ]);
        const line = new THREE.Line(lineGeo, gridMat);
        gridLinesGroup.add(line);
      });

      // Safety reserve threshold indicator line (at y = -0.95)
      const thresholdMat = new THREE.LineDashedMaterial({
        color: PALETTE.softMauve,
        transparent: true,
        opacity: 0.16,
        dashSize: 0.25,
        gapSize: 0.15,
      });
      const thresholdGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-8, -0.95, -1.0),
        new THREE.Vector3(8, -0.95, -1.0),
      ]);
      const thresholdLine = new THREE.Line(thresholdGeo, thresholdMat);
      thresholdLine.computeLineDistances();
      gridLinesGroup.add(thresholdLine);

      // -------------------------------------------------------------
      // 2. Flowing Translucent Cash-Flow Ribbons
      // -------------------------------------------------------------
      const ribbonsData: RibbonConfig[] = [
        // Ribbon 1: Primary Runway Stream (features the dip & AI recovery trajectory)
        {
          baseY: -0.1,
          amplitude1: 0.38,
          amplitude2: 0.22,
          freq1: 0.42,
          freq2: 0.85,
          speed: 0.35,
          color: PALETTE.steelBlue,
          opacity: 0.32,
          width: 0.55,
          zDepth: 0.2,
          phaseOffset: 0.0,
          hasDipRecovery: true,
        },
        // Ribbon 2: Inflow Stream (higher trajectory, softly rising)
        {
          baseY: 0.65,
          amplitude1: 0.32,
          amplitude2: 0.18,
          freq1: 0.36,
          freq2: 0.72,
          speed: 0.28,
          color: PALETTE.slateBlue,
          opacity: 0.26,
          width: 0.45,
          zDepth: -0.4,
          phaseOffset: 1.8,
        },
        // Ribbon 3: Outflow & Operating Burn Stream (diverging downward)
        {
          baseY: -0.65,
          amplitude1: 0.28,
          amplitude2: 0.16,
          freq1: 0.48,
          freq2: 0.94,
          speed: 0.32,
          color: PALETTE.dustyIndigo,
          opacity: 0.28,
          width: 0.48,
          zDepth: -0.2,
          phaseOffset: 3.4,
        },
        // Ribbon 4: Capital Reserve Buffer (restrained mauve, background depth)
        {
          baseY: -0.35,
          amplitude1: 0.24,
          amplitude2: 0.14,
          freq1: 0.32,
          freq2: 0.65,
          speed: 0.22,
          color: PALETTE.softMauve,
          opacity: 0.2,
          width: 0.4,
          zDepth: -0.8,
          phaseOffset: 4.8,
        },
      ];

      const SEGMENTS = 140;
      const X_START = -8.5;
      const X_END = 8.5;
      const X_STEP = (X_END - X_START) / SEGMENTS;

      interface ActiveRibbon {
        geometry: THREE.BufferGeometry;
        material: THREE.Material;
        config: RibbonConfig;
        mesh: THREE.Mesh;
      }

      const activeRibbons: ActiveRibbon[] = ribbonsData.map((config) => {
        // Create ribbon plane geometry (SEGMENTS columns x 1 row)
        // 2 vertices per column: top and bottom edge of ribbon
        const vertexCount = (SEGMENTS + 1) * 2;
        const positions = new Float32Array(vertexCount * 3);
        const indices: number[] = [];

        // Build triangle strip indices
        for (let i = 0; i < SEGMENTS; i++) {
          const v0 = i * 2;
          const v1 = i * 2 + 1;
          const v2 = (i + 1) * 2;
          const v3 = (i + 1) * 2 + 1;

          indices.push(v0, v1, v2);
          indices.push(v1, v3, v2);
        }

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setIndex(indices);

        // Soft matte material without specular glow
        const material = new THREE.MeshBasicMaterial({
          color: config.color,
          transparent: true,
          opacity: config.opacity,
          side: THREE.DoubleSide,
          depthWrite: false,
        });

        const mesh = new THREE.Mesh(geometry, material);
        rootGroup.add(mesh);

        return { geometry, material, config, mesh };
      });

      // -------------------------------------------------------------
      // 3. Subtle Forecast Path & Confidence Band Visualization
      // -------------------------------------------------------------
      // High-precision single line tracing the deterministic forecast
      const forecastPointsCount = 160;
      const forecastPositions = new Float32Array(forecastPointsCount * 3);
      const forecastGeo = new THREE.BufferGeometry();
      forecastGeo.setAttribute('position', new THREE.BufferAttribute(forecastPositions, 3));

      const forecastLineMat = new THREE.LineBasicMaterial({
        color: PALETTE.steelBlue,
        transparent: true,
        opacity: 0.55,
      });
      const forecastLine = new THREE.Line(forecastGeo, forecastLineMat);
      rootGroup.add(forecastLine);

      // Translucent Confidence Corridor Band along the recovery segment
      const corridorSegments = 60;
      const corridorPositions = new Float32Array((corridorSegments + 1) * 2 * 3);
      const corridorIndices: number[] = [];

      for (let i = 0; i < corridorSegments; i++) {
        const v0 = i * 2;
        const v1 = i * 2 + 1;
        const v2 = (i + 1) * 2;
        const v3 = (i + 1) * 2 + 1;
        corridorIndices.push(v0, v1, v2);
        corridorIndices.push(v1, v3, v2);
      }

      const corridorGeo = new THREE.BufferGeometry();
      corridorGeo.setAttribute('position', new THREE.BufferAttribute(corridorPositions, 3));
      corridorGeo.setIndex(corridorIndices);

      const corridorMat = new THREE.MeshBasicMaterial({
        color: PALETTE.dustyIndigo,
        transparent: true,
        opacity: 0.12,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const corridorMesh = new THREE.Mesh(corridorGeo, corridorMat);
      rootGroup.add(corridorMesh);

      // -------------------------------------------------------------
      // Helper function: calculate y at position x with dip & recovery
      // -------------------------------------------------------------
      const evaluateForecastCurve = (x: number, time: number, cfg: RibbonConfig): number => {
        // Base harmonic wave
        let y =
          cfg.baseY +
          Math.sin(x * cfg.freq1 + time * cfg.speed + cfg.phaseOffset) * cfg.amplitude1 +
          Math.cos(x * cfg.freq2 - time * (cfg.speed * 0.7) + cfg.phaseOffset) * cfg.amplitude2;

        // If this is the primary forecast ribbon, inject the intentional dip and recovery signature
        if (cfg.hasDipRecovery) {
          // Dip between x = -2.2 and x = 0.2 (shortage detection zone)
          const dipCenter = -1.0;
          const dipWidth = 1.4;
          const distToDip = (x - dipCenter) / dipWidth;
          const dipFactor = Math.exp(-distToDip * distToDip) * -0.55;

          // Recovery climb for x > 0.5 (autonomous recovery trajectory)
          const recoveryFactor = x > 0 ? Math.min(1.0, (x - 0.2) * 0.2) * 0.5 : 0;

          y += dipFactor + recoveryFactor;
        }

        return y;
      };

      // -------------------------------------------------------------
      // Animation & Parallax Tracking
      // -------------------------------------------------------------
      let mouseX = 0;
      let mouseY = 0;
      let targetRotX = 0;
      let targetRotY = 0;

      const handleMouseMove = (event: MouseEvent) => {
        const rect = container.getBoundingClientRect();
        mouseX = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        mouseY = -(((event.clientY - rect.top) / rect.height) * 2 - 1);
      };

      window.addEventListener('mousemove', handleMouseMove);

      const handleResize = () => {
        if (!container || !renderer) return;
        const width = container.clientWidth;
        const height = container.clientHeight;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
      };

      window.addEventListener('resize', handleResize);

      const clock = new THREE.Clock();

      const updateGeometryPositions = (time: number) => {
        // Update each ribbon
        activeRibbons.forEach(({ geometry, config }) => {
          const posAttr = geometry.getAttribute('position') as THREE.BufferAttribute;
          const pos = posAttr.array as Float32Array;

          for (let i = 0; i <= SEGMENTS; i++) {
            const x = X_START + i * X_STEP;
            const centerY = evaluateForecastCurve(x, time, config);

            // Variable ribbon thickness creates organic ribbon width modulation
            const thickness =
              config.width * (0.8 + Math.sin(x * 0.4 + time * 0.2) * 0.2);

            const z =
              config.zDepth +
              Math.sin(x * 0.35 + time * 0.15 + config.phaseOffset) * 0.15;

            // Top vertex of ribbon segment
            const idxTop = i * 2 * 3;
            pos[idxTop] = x;
            pos[idxTop + 1] = centerY + thickness * 0.5;
            pos[idxTop + 2] = z;

            // Bottom vertex of ribbon segment
            const idxBottom = (i * 2 + 1) * 3;
            pos[idxBottom] = x;
            pos[idxBottom + 1] = centerY - thickness * 0.5;
            pos[idxBottom + 2] = z;
          }

          posAttr.needsUpdate = true;
        });

        // Update thin Forecast Path Line (following Ribbon 1 exactly)
        const primaryConfig = ribbonsData[0];
        const lineAttr = forecastGeo.getAttribute('position') as THREE.BufferAttribute;
        const linePos = lineAttr.array as Float32Array;
        const lineStep = (X_END - X_START) / (forecastPointsCount - 1);

        for (let i = 0; i < forecastPointsCount; i++) {
          const x = X_START + i * lineStep;
          const y = evaluateForecastCurve(x, time, primaryConfig);
          const z = primaryConfig.zDepth + 0.08;

          linePos[i * 3] = x;
          linePos[i * 3 + 1] = y;
          linePos[i * 3 + 2] = z;
        }
        lineAttr.needsUpdate = true;

        // Update Confidence Corridor Band (spanning x from -1.0 to +4.5)
        const corridorAttr = corridorGeo.getAttribute('position') as THREE.BufferAttribute;
        const corridorPos = corridorAttr.array as Float32Array;
        const cXStart = -1.0;
        const cXEnd = 4.8;
        const cXStep = (cXEnd - cXStart) / corridorSegments;

        for (let i = 0; i <= corridorSegments; i++) {
          const x = cXStart + i * cXStep;
          const y = evaluateForecastCurve(x, time, primaryConfig);
          const z = primaryConfig.zDepth + 0.04;

          // Band widens into the future (confidence uncertainty expansion)
          const progress = i / corridorSegments;
          const bandHalfHeight = 0.12 + progress * 0.38;

          const idxTop = i * 2 * 3;
          corridorPos[idxTop] = x;
          corridorPos[idxTop + 1] = y + bandHalfHeight;
          corridorPos[idxTop + 2] = z;

          const idxBottom = (i * 2 + 1) * 3;
          corridorPos[idxBottom] = x;
          corridorPos[idxBottom + 1] = y - bandHalfHeight;
          corridorPos[idxBottom + 2] = z;
        }
        corridorAttr.needsUpdate = true;
      };

      // Initial compute for static or first frame
      updateGeometryPositions(0);

      // Animation Loop
      const animate = () => {
        // Slow, fluid motion (0.35x speed factor for calm background)
        const elapsedTime = isLowMotion ? 0 : clock.getElapsedTime() * 0.35;

        if (!isLowMotion) {
          updateGeometryPositions(elapsedTime);
        }

        // Subdued mouse parallax (low amplitude to keep background calm)
        targetRotY += (mouseX * 0.04 - targetRotY) * 0.04;
        targetRotX += (mouseY * 0.03 - targetRotX) * 0.04;
        rootGroup.rotation.y = targetRotY;
        rootGroup.rotation.x = -targetRotX;

        renderer?.render(scene, camera);
        animationFrameId = requestAnimationFrame(animate);
      };

      animate();

      // Cleanup
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('resize', handleResize);
        cancelAnimationFrame(animationFrameId);

        gridLinesGroup.traverse((obj) => {
          if (obj instanceof THREE.Line) {
            obj.geometry.dispose();
          }
        });
        gridMat.dispose();
        thresholdMat.dispose();

        activeRibbons.forEach(({ geometry, material }) => {
          geometry.dispose();
          material.dispose();
        });

        forecastGeo.dispose();
        forecastLineMat.dispose();
        corridorGeo.dispose();
        corridorMat.dispose();

        if (renderer) {
          renderer.dispose();
          if (renderer.domElement.parentNode) {
            renderer.domElement.parentNode.removeChild(renderer.domElement);
          }
        }
      };
    } catch (err) {
      console.warn('Three.js failed to initialize, using CSS fallback:', err);
      setTimeout(() => {
        setWebglSupported(false);
      }, 0);
    }
  }, [isLowMotion, webglSupported]);

  return (
    <div className="hero-scene-container" ref={containerRef} aria-hidden="true">
      {/* Fallback SVG / CSS: Muted cash-flow curves and dip-recovery corridor */}
      {!webglSupported && (
        <div className="hero-scene-fallback">
          <svg
            className="fallback-flow-svg"
            viewBox="0 0 1200 600"
            preserveAspectRatio="none"
          >
            <defs>
              <linearGradient id="streamGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#607D98" stopOpacity="0.1" />
                <stop offset="40%" stopColor="#666A91" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#7896B0" stopOpacity="0.4" />
              </linearGradient>
              <linearGradient id="streamGrad2" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#9A758D" stopOpacity="0.25" />
                <stop offset="50%" stopColor="#666A91" stopOpacity="0.2" />
                <stop offset="100%" stopColor="#607D98" stopOpacity="0.1" />
              </linearGradient>
              <linearGradient id="corridorGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#666A91" stopOpacity="0.05" />
                <stop offset="100%" stopColor="#666A91" stopOpacity="0.18" />
              </linearGradient>
            </defs>

            {/* Faint ledger coordinate lines */}
            <line x1="0" y1="200" x2="1200" y2="200" stroke="#666A91" strokeOpacity="0.08" strokeWidth="1" />
            <line x1="0" y1="320" x2="1200" y2="320" stroke="#666A91" strokeOpacity="0.08" strokeWidth="1" />
            <line x1="0" y1="440" x2="1200" y2="440" stroke="#666A91" strokeOpacity="0.08" strokeWidth="1" />
            <line x1="0" y1="410" x2="1200" y2="410" stroke="#9A758D" strokeOpacity="0.18" strokeWidth="1" strokeDasharray="6 4" />

            {/* Translucent Confidence Corridor */}
            <path
              d="M 450,360 Q 650,330 950,220 L 950,340 Q 650,420 450,400 Z"
              fill="url(#corridorGrad)"
            />

            {/* Outflow stream */}
            <path
              d="M -50,350 Q 250,280 500,390 T 1050,440 T 1250,420"
              fill="none"
              stroke="url(#streamGrad2)"
              strokeWidth="38"
              strokeLinecap="round"
            />

            {/* Inflow stream */}
            <path
              d="M -50,230 Q 300,180 550,260 T 1000,190 T 1250,180"
              fill="none"
              stroke="url(#streamGrad1)"
              strokeWidth="42"
              strokeLinecap="round"
            />

            {/* Primary Forecast Path (with Dip & Recovery curve) */}
            <path
              d="M -50,290 C 250,270 380,380 520,380 C 680,380 820,270 1250,240"
              fill="none"
              stroke="#7896B0"
              strokeWidth="2.5"
              strokeOpacity="0.65"
            />
          </svg>
        </div>
      )}
      <div className="hero-scene-vignette" />
    </div>
  );
}
