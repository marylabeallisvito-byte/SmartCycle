"use client";

/* ============================================================
   SmartCycle — 3D Client Profile Visualization

   A light but visually striking Three.js particle + geometry
   visualization that reacts to the client's psychological profile:

     • Risk Tolerance  → color palette
       Conservative: cyan/blue
       Moderate:     purple/blue
       Aggressive:   gold/red

     • Anxiety Level   → animation dynamics
       Low:    slow, smooth rotation
       Medium: moderate pulse
       High:   fast jitter, turbulent particles

   Built with @react-three/fiber + @react-three/drei.
   Rendered in a compact card — a creative alternative to
   a static table of client attributes.
============================================================ */

import { Suspense, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Sphere, Line, Text } from "@react-three/drei";
import * as THREE from "three";

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

interface Props {
  riskTolerance: "conservative" | "moderate" | "aggressive";
  anxietyLevel: "low" | "medium" | "high";
  clientName: string;
  className?: string;
}

// ═══════════════════════════════════════════════════════════════
// Color palettes by risk tolerance
// ═══════════════════════════════════════════════════════════════

const PALETTES: Record<
  string,
  { primary: string; secondary: string; accent: string; core: string }
> = {
  conservative: {
    primary: "#00d4ff",
    secondary: "#3b82f6",
    accent: "#10b981",
    core: "#1e40af",
  },
  moderate: {
    primary: "#8b5cf6",
    secondary: "#6366f1",
    accent: "#3b82f6",
    core: "#4c1d95",
  },
  aggressive: {
    primary: "#f59e0b",
    secondary: "#ef4444",
    accent: "#ec4899",
    core: "#b91c1c",
  },
};

// ═══════════════════════════════════════════════════════════════
// Speed config by anxiety level
// ═══════════════════════════════════════════════════════════════

const ANXIETY_SPEEDS: Record<string, { rotation: number; jitter: number; pulse: number }> = {
  low:    { rotation: 0.15, jitter: 0.02, pulse: 0.3 },
  medium: { rotation: 0.35, jitter: 0.06, pulse: 0.7 },
  high:   { rotation: 0.60, jitter: 0.15, pulse: 1.4 },
};

// ═══════════════════════════════════════════════════════════════
// 3D Scene: Animated geometry + particle cloud
// ═══════════════════════════════════════════════════════════════

function ProfileGeometry({
  riskTolerance,
  anxietyLevel,
}: {
  riskTolerance: string;
  anxietyLevel: string;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);

  const palette = PALETTES[riskTolerance] ?? PALETTES.moderate;
  const speed = ANXIETY_SPEEDS[anxietyLevel] ?? ANXIETY_SPEEDS.medium;

  const primaryColor = useMemo(() => new THREE.Color(palette.primary), [palette.primary]);
  const secondaryColor = useMemo(() => new THREE.Color(palette.secondary), [palette.secondary]);
  const coreColor = useMemo(() => new THREE.Color(palette.core), [palette.core]);

  // ── Generate orbiting particles ──
  const particlePositions = useMemo(() => {
    const count = 120;
    const positions = new Float32Array(count * 3);
    const radius = 2.2;
    for (let i = 0; i < count; i++) {
      const phi = Math.acos(2 * Math.random() - 1);
      const theta = Math.random() * Math.PI * 2;
      const r = radius + (Math.random() - 0.5) * 0.8;
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
    }
    return positions;
  }, []);

  // ── Ring points ──
  const ringPoints = useMemo(() => {
    const segments = 80;
    const pts: [number, number, number][] = [];
    const r = 1.8;
    for (let i = 0; i <= segments; i++) {
      const angle = (i / segments) * Math.PI * 2;
      const tilt = 0.4;
      pts.push([
        Math.cos(angle) * r,
        Math.sin(angle) * r * tilt,
        Math.sin(angle) * r * 0.7,
      ]);
    }
    return pts;
  }, []);

  // ── Animation loop ──
  useFrame((_, delta) => {
    if (!groupRef.current) return;
    const t = performance.now() * 0.001;

    // Whole group rotates
    groupRef.current.rotation.y += speed.rotation * delta;
    groupRef.current.rotation.x += speed.rotation * 0.3 * delta;

    // Core pulsates
    if (coreRef.current) {
      const pulse = 1 + Math.sin(t * speed.pulse * 3) * 0.08 * speed.pulse;
      coreRef.current.scale.setScalar(pulse);
    }

    // Ring tilts with jitter
    if (ringRef.current) {
      ringRef.current.rotation.z += speed.jitter * delta;
      ringRef.current.rotation.x = Math.sin(t * 0.8) * 0.3 * speed.jitter * 2;
    }
  });

  return (
    <group ref={groupRef}>
      {/* ── Central core icosahedron ── */}
      <mesh ref={coreRef}>
        <icosahedronGeometry args={[0.55, 1]} />
        <meshPhysicalMaterial
          color={coreColor}
          emissive={primaryColor}
          emissiveIntensity={0.4}
          roughness={0.3}
          metalness={0.5}
          transparent
          opacity={0.85}
          wireframe={false}
        />
      </mesh>

      {/* ── Wireframe shell ── */}
      <mesh>
        <icosahedronGeometry args={[0.85, 2]} />
        <meshBasicMaterial
          color={secondaryColor}
          wireframe
          transparent
          opacity={0.15}
        />
      </mesh>

      {/* ── Outer ring ── */}
      <mesh ref={ringRef}>
        <torusGeometry args={[1.5, 0.02, 16, 100]} />
        <meshBasicMaterial color={primaryColor} transparent opacity={0.6} />
      </mesh>

      {/* ── Orbital line ── */}
      <Line
        points={ringPoints}
        color={secondaryColor}
        lineWidth={0.5}
        transparent
        opacity={0.25}
      />

      {/* ── Particle cloud ── */}
      <points>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[particlePositions, 3]}
            count={particlePositions.length / 3}
            array={particlePositions}
            itemSize={3}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.04}
          color={primaryColor}
          transparent
          opacity={0.7}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>

      {/* ── Ambient glow sphere ── */}
      <Sphere args={[1.05, 32, 32]}>
        <meshBasicMaterial
          color={primaryColor}
          transparent
          opacity={0.04}
          depthWrite={false}
        />
      </Sphere>
    </group>
  );
}

// ═══════════════════════════════════════════════════════════════
// Labels for risk & anxiety
// ═══════════════════════════════════════════════════════════════

function labelForRisk(risk: string): { text: string; color: string } {
  switch (risk) {
    case "conservative": return { text: "保守型", color: "#10b981" };
    case "moderate":     return { text: "稳健型", color: "#8b5cf6" };
    case "aggressive":   return { text: "进取型", color: "#f59e0b" };
    default:             return { text: risk, color: "#94a3b8" };
  }
}

function labelForAnxiety(anxiety: string): { text: string; color: string } {
  switch (anxiety) {
    case "low":    return { text: "冷静 · Calm", color: "#10b981" };
    case "medium": return { text: "关注 · Attentive", color: "#f59e0b" };
    case "high":   return { text: "焦虑 · Anxious", color: "#ef4444" };
    default:       return { text: anxiety, color: "#94a3b8" };
  }
}

// ═══════════════════════════════════════════════════════════════
// Public component
// ═══════════════════════════════════════════════════════════════

export default function Client3DProfile({
  riskTolerance,
  anxietyLevel,
  clientName,
  className = "",
}: Props) {
  const riskInfo = labelForRisk(riskTolerance);
  const anxietyInfo = labelForAnxiety(anxietyLevel);

  return (
    <div className={`surface-card overflow-hidden ${className}`}>
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-4 pt-4">
        <div>
          <h3 className="text-sm font-semibold text-[#e2e8f0]">
            客户画像 · Client Profile
          </h3>
          <p className="text-2xs text-[#64748b]">{clientName}</p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-2xs font-medium`}
            style={{ color: anxietyInfo.color }}
          >
            {anxietyInfo.text}
          </span>
          <span
            className="h-1.5 w-1.5 rounded-full animate-pulse"
            style={{ backgroundColor: anxietyInfo.color }}
          />
        </div>
      </div>

      {/* ── 3D Canvas ── */}
      <div className="relative h-[260px] w-full">
        <Canvas
          camera={{ position: [0, 0.2, 4.2], fov: 45 }}
          gl={{ antialias: true, alpha: true }}
          dpr={[1, 1.5]}
        >
          <ambientLight intensity={0.4} />
          <pointLight position={[3, 2, 3]} intensity={0.8} color={riskInfo.color} />
          <pointLight position={[-3, -1, -2]} intensity={0.3} color="#00d4ff" />
          <Suspense fallback={null}>
            <ProfileGeometry
              riskTolerance={riskTolerance}
              anxietyLevel={anxietyLevel}
            />
          </Suspense>
          <OrbitControls
            enableZoom={false}
            enablePan={false}
            autoRotate
            autoRotateSpeed={0.4}
            maxPolarAngle={Math.PI * 0.7}
            minPolarAngle={Math.PI * 0.3}
          />
        </Canvas>

        {/* ── Overlay labels ── */}
        <div className="pointer-events-none absolute bottom-3 left-0 right-0 flex justify-center gap-4">
          <span
            className="rounded-full border px-3 py-1 text-2xs font-medium backdrop-blur-sm"
            style={{
              borderColor: riskInfo.color + "40",
              backgroundColor: riskInfo.color + "15",
              color: riskInfo.color,
            }}
          >
            {riskInfo.text}
          </span>
          <span
            className="rounded-full border px-3 py-1 text-2xs font-medium backdrop-blur-sm"
            style={{
              borderColor: anxietyInfo.color + "40",
              backgroundColor: anxietyInfo.color + "15",
              color: anxietyInfo.color,
            }}
          >
            {anxietyInfo.text}
          </span>
        </div>
      </div>

      {/* ── Legend ── */}
      <div className="flex items-center justify-center gap-6 border-t border-[#1e2948] px-4 py-2.5">
        <LegendDot color={riskInfo.color} label="Risk Tolerance" value={riskInfo.text} />
        <LegendDot color={anxietyInfo.color} label="Anxiety" value={anxietyInfo.text} />
      </div>
    </div>
  );
}

function LegendDot({
  color,
  label,
  value,
}: {
  color: string;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      <span className="text-2xs text-[#64748b]">{label}:</span>
      <span className="text-2xs font-medium text-[#e2e8f0]">{value}</span>
    </div>
  );
}
