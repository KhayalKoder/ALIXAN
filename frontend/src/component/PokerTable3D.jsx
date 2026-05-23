import { Canvas, useFrame, useThree, extend } from "@react-three/fiber";
import { useRef, useMemo, useEffect } from "react";
import * as THREE from "three";

/**
 * Build the entire 3D scene imperatively (no R3F JSX intrinsics)
 * so the visual-edits Babel plugin can't inject unknown JSX props that
 * R3F applyProps would try to apply to three.js objects.
 */
function SceneObjects() {
  const { scene } = useThree();
  const refs = useRef({});

  useEffect(() => {
    const built = [];

    // ----- Outer leather rail -----
    const railGeo = new THREE.TorusGeometry(3.3, 0.45, 24, 80);
    const railMat = new THREE.MeshStandardMaterial({ color: "#2a1a14", roughness: 0.6, metalness: 0.2 });
    const rail = new THREE.Mesh(railGeo, railMat);
    rail.rotation.x = Math.PI / 2;
    rail.scale.set(1.6, 1, 1);
    scene.add(rail);
    built.push(rail);

    // ----- Gold trim -----
    const trimGeo = new THREE.TorusGeometry(3.05, 0.06, 16, 80);
    const trimMat = new THREE.MeshStandardMaterial({
      color: "#D4AF37",
      roughness: 0.3,
      metalness: 0.9,
      emissive: new THREE.Color("#5a4514"),
      emissiveIntensity: 0.5,
    });
    const trim = new THREE.Mesh(trimGeo, trimMat);
    trim.rotation.x = Math.PI / 2;
    trim.position.y = 0.16;
    trim.scale.set(1.6, 1, 1);
    scene.add(trim);
    built.push(trim);

    // ----- Felt -----
    const feltGeo = new THREE.CircleGeometry(3, 80);
    const feltMat = new THREE.MeshStandardMaterial({
      color: "#1a3d5e",
      roughness: 0.7,
      metalness: 0.05,
      emissive: new THREE.Color("#0a1a2c"),
      emissiveIntensity: 0.6,
    });
    const felt = new THREE.Mesh(feltGeo, feltMat);
    felt.rotation.x = -Math.PI / 2;
    felt.position.y = 0.05;
    felt.scale.set(1.6, 1, 1);
    scene.add(felt);
    built.push(felt);

    // ----- Center logo ring -----
    const ringGeo = new THREE.RingGeometry(0.6, 0.7, 80);
    const ringMat = new THREE.MeshStandardMaterial({
      color: "#D4AF37",
      emissive: new THREE.Color("#D4AF37"),
      emissiveIntensity: 0.4,
      transparent: true,
      opacity: 0.35,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.06;
    ring.scale.set(1.6, 1, 1);
    scene.add(ring);
    built.push(ring);

    // ----- Lights -----
    const amb = new THREE.AmbientLight(0xffffff, 0.35);
    scene.add(amb);
    built.push(amb);

    const dir = new THREE.DirectionalLight(0xffffff, 0.6);
    dir.position.set(6, 8, 4);
    scene.add(dir);
    built.push(dir);

    const spot = new THREE.SpotLight(0xfff5d6, 3.5, 30, 0.6, 0.5);
    spot.position.set(0, 8, 0);
    spot.target.position.set(0, 0, 0);
    scene.add(spot);
    scene.add(spot.target);
    built.push(spot);
    built.push(spot.target);

    const pt = new THREE.PointLight("#fff5d6", 2.5, 20);
    pt.position.set(0, 5, 0);
    scene.add(pt);
    refs.current.pt = pt;
    built.push(pt);

    // ----- Dust particles -----
    const dustGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(300 * 3);
    for (let i = 0; i < 300; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 14;
      positions[i * 3 + 1] = Math.random() * 5 + 1;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 10;
    }
    dustGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const dustMat = new THREE.PointsMaterial({
      size: 0.025,
      color: 0xd4af37,
      transparent: true,
      opacity: 0.4,
      sizeAttenuation: true,
    });
    const dust = new THREE.Points(dustGeo, dustMat);
    scene.add(dust);
    refs.current.dust = dust;
    built.push(dust);

    // Background color
    scene.background = new THREE.Color("#05060a");
    scene.fog = new THREE.Fog("#05060a", 8, 20);

    return () => {
      built.forEach((obj) => {
        scene.remove(obj);
        if (obj.geometry) obj.geometry.dispose?.();
        if (obj.material) {
          if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose?.());
          else obj.material.dispose?.();
        }
      });
    };
  }, [scene]);

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    if (refs.current.pt) {
      refs.current.pt.position.x = Math.sin(t * 0.3) * 0.5;
      refs.current.pt.position.z = Math.cos(t * 0.3) * 0.5;
    }
    if (refs.current.dust) {
      refs.current.dust.rotation.y = t * 0.02;
    }
  });

  return null;
}

export default function PokerTable3D() {
  return (
    <Canvas
      camera={{ position: [0, 5.6, 5.5], fov: 45 }}
      gl={{ antialias: true, alpha: false }}
      style={{ width: "100%", height: "100%" }}
      onCreated={({ camera }) => camera.lookAt(0, 0, 0)}
    >
      <SceneObjects />
    </Canvas>
  );
}

