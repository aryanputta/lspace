"""
LPAS NVIDIA Isaac Sim Environment Setup
Lunar South Pole PSR Terrain

Requires: Isaac Sim 2023.1+, Python 3.10
Run from Isaac Sim Python: ./python.sh lunar_south_pole_isaac.py
"""
from __future__ import annotations

import asyncio
import json
import math
import numpy as np
from pathlib import Path
from typing import Optional

import omni
import omni.kit.app
from omni.isaac.core import World
from omni.isaac.core.objects import DynamicCuboid, GroundPlane
from omni.isaac.core.utils.stage import add_reference_to_stage
from omni.isaac.core.utils.nucleus import get_assets_root_path
from omni.isaac.core.utils.prims import create_prim
from pxr import Gf, UsdGeom, UsdPhysics, UsdShade, Sdf

# Project root relative to Isaac Sim
PROJECT_ROOT = Path(__file__).parent.parent.parent
TERRAIN_DATA = PROJECT_ROOT / "terrain_data" / "processed"
GAZEBO_WORLDS = PROJECT_ROOT / "gazebo_worlds" / "lunar_south_pole"


class LunarPSREnvironment:
    """Isaac Sim environment for lunar south pole PSR rover simulation."""

    LUNAR_GRAVITY = -1.62  # m/s²
    REGOLITH_STATIC_FRICTION = 0.7
    REGOLITH_DYNAMIC_FRICTION = 0.55
    REGOLITH_RESTITUTION = 0.05

    def __init__(self, headless: bool = False):
        self.world = World(
            stage_units_in_meters=1.0,
            physics_dt=1.0 / 200.0,  # 200 Hz physics for wheel contact accuracy
            rendering_dt=1.0 / 30.0,
        )
        self._headless = headless
        self._terrain_prim_path = "/World/LunarTerrain"
        self._rover_prim_path = "/World/LPASRover"
        self._relay_station_path = "/World/RelayStation"
        self._setup_complete = False

    async def setup(self) -> None:
        """Initialize the complete lunar environment."""
        await self.world.initialize_simulation_context_async()
        self._configure_physics()
        self._configure_lighting()
        await self._load_terrain()
        await self._load_rover()
        await self._place_relay_station()
        self._add_boulders()
        self._add_crater_features()
        self._configure_sensors()
        self._setup_complete = True
        print("[LPAS Isaac] Environment setup complete.")

    def _configure_physics(self) -> None:
        """Set lunar gravity and regolith physics properties."""
        scene = self.world.scene
        physics_context = self.world.get_physics_context()
        physics_context.set_gravity(self.LUNAR_GRAVITY)
        physics_context.set_solver_type("TGS")  # Temporal Gauss-Seidel for stability
        physics_context.set_broadphase_type("GPU")
        physics_context.enable_ccd(True)  # Continuous collision for wheel contacts

        # Scene-level physics parameters
        physics_context._physics_scene.CreateGravityDirectionAttr().Set(
            Gf.Vec3f(0.0, 0.0, -1.0)
        )
        physics_context._physics_scene.CreateGravityMagnitudeAttr().Set(
            abs(self.LUNAR_GRAVITY)
        )
        print(f"[LPAS Isaac] Gravity set to {self.LUNAR_GRAVITY} m/s²")

    def _configure_lighting(self) -> None:
        """Configure lunar south pole lighting: low-angle sunlight + PSR darkness."""
        stage = omni.usd.get_context().get_stage()

        # Distant sun light (2° elevation angle, south pole geometry)
        sun_path = "/World/Lights/Sun"
        sun_prim = stage.DefinePrim(sun_path, "DistantLight")
        sun_prim.GetAttribute("inputs:intensity").Set(50000.0)
        sun_prim.GetAttribute("inputs:color").Set(Gf.Vec3f(1.0, 0.98, 0.95))
        sun_prim.GetAttribute("inputs:angle").Set(0.53)  # Solar disc angle (degrees)
        # Rotation: 2° elevation, azimuth variable
        sun_xform = UsdGeom.XformCommonAPI(sun_prim)
        sun_xform.SetRotate(Gf.Vec3f(-88.0, 0.0, 0.0))  # 2° above horizon

        # Ambient sky (very low for lunar vacuum — no atmosphere)
        sky_path = "/World/Lights/AmbientSky"
        sky_prim = stage.DefinePrim(sky_path, "SphereLight")
        sky_prim.GetAttribute("inputs:intensity").Set(50.0)  # Minimal ambient
        sky_prim.GetAttribute("inputs:color").Set(Gf.Vec3f(0.05, 0.05, 0.15))
        sky_prim.GetAttribute("inputs:radius").Set(10000.0)

        # PSR fill light (extremely dim, thermal IR glow simulation)
        psr_path = "/World/Lights/PSR_Fill"
        psr_prim = stage.DefinePrim(psr_path, "DomeLight")
        psr_prim.GetAttribute("inputs:intensity").Set(5.0)
        psr_prim.GetAttribute("inputs:color").Set(Gf.Vec3f(0.2, 0.1, 0.05))

        print("[LPAS Isaac] Lighting configured: low-angle sun (2° elevation)")

    async def _load_terrain(self) -> None:
        """Load lunar south pole DEM terrain heightmap."""
        stage = omni.usd.get_context().get_stage()

        # Check for processed heightmap
        heightmap_path = GAZEBO_WORLDS / "lunar_south_pole_dem.png"
        if not heightmap_path.exists():
            print(f"[LPAS Isaac] WARNING: Heightmap not found at {heightmap_path}")
            print("[LPAS Isaac] Run scripts/terrain_processing/process_dem_to_gazebo.py first")
            self._create_synthetic_terrain()
            return

        terrain_prim = stage.DefinePrim(self._terrain_prim_path, "Mesh")

        # Load heightmap and generate mesh
        from PIL import Image
        heightmap = np.array(Image.open(heightmap_path).convert("L"), dtype=np.float32)
        heightmap = (heightmap / 255.0) * 2000.0 - 1000.0  # Scale to ±1000m

        h, w = heightmap.shape
        terrain_scale = 50.0  # 50m per pixel → 25.6km × 25.6km for 512×512

        vertices, faces, normals = self._heightmap_to_mesh(heightmap, terrain_scale)

        mesh_geom = UsdGeom.Mesh(terrain_prim)
        mesh_geom.CreatePointsAttr(vertices.tolist())
        mesh_geom.CreateFaceVertexCountsAttr([3] * len(faces))
        mesh_geom.CreateFaceVertexIndicesAttr(faces.flatten().tolist())

        self._apply_regolith_material(terrain_prim)
        self._add_terrain_physics(terrain_prim)
        print(f"[LPAS Isaac] Terrain loaded: {w}×{h} heightmap, {terrain_scale}m/pixel")

    def _heightmap_to_mesh(
        self,
        heightmap: np.ndarray,
        scale: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Convert 2D heightmap array to triangle mesh."""
        h, w = heightmap.shape
        x = np.linspace(-w * scale / 2, w * scale / 2, w)
        y = np.linspace(-h * scale / 2, h * scale / 2, h)
        xx, yy = np.meshgrid(x, y)

        vertices = np.stack([xx.ravel(), yy.ravel(), heightmap.ravel()], axis=1)

        i, j = np.mgrid[0 : h - 1, 0 : w - 1]
        tl = i * w + j
        tr = i * w + (j + 1)
        bl = (i + 1) * w + j
        br = (i + 1) * w + (j + 1)
        faces = np.concatenate(
            [
                np.stack([tl, bl, tr], axis=-1).reshape(-1, 3),
                np.stack([tr, bl, br], axis=-1).reshape(-1, 3),
            ]
        )

        # Compute vertex normals
        normals = np.zeros_like(vertices)
        v0 = vertices[faces[:, 0]]
        v1 = vertices[faces[:, 1]]
        v2 = vertices[faces[:, 2]]
        fn = np.cross(v1 - v0, v2 - v0)
        np.add.at(normals, faces[:, 0], fn)
        np.add.at(normals, faces[:, 1], fn)
        np.add.at(normals, faces[:, 2], fn)
        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        normals /= np.maximum(norms, 1e-8)

        return vertices.astype(np.float32), faces.astype(np.int32), normals.astype(np.float32)

    def _create_synthetic_terrain(self) -> None:
        """Generate procedural lunar terrain when DEM is unavailable."""
        print("[LPAS Isaac] Generating synthetic lunar terrain (DEM fallback)")
        size = 256
        heightmap = self._generate_lunar_heightmap(size, seed=42)
        terrain_scale = 10.0  # 10m/pixel → 2.56km for fallback
        stage = omni.usd.get_context().get_stage()
        terrain_prim = stage.DefinePrim(self._terrain_prim_path, "Mesh")
        vertices, faces, normals = self._heightmap_to_mesh(heightmap, terrain_scale)
        mesh_geom = UsdGeom.Mesh(terrain_prim)
        mesh_geom.CreatePointsAttr(vertices.tolist())
        mesh_geom.CreateFaceVertexCountsAttr([3] * len(faces))
        mesh_geom.CreateFaceVertexIndicesAttr(faces.flatten().tolist())
        self._apply_regolith_material(terrain_prim)
        self._add_terrain_physics(terrain_prim)

    @staticmethod
    def _generate_lunar_heightmap(size: int, seed: int = 0) -> np.ndarray:
        """Fractal brownian motion heightmap with crater features."""
        rng = np.random.default_rng(seed)
        heightmap = np.zeros((size, size))

        # Multi-octave noise (simplified FBM)
        for octave in range(8):
            freq = 2 ** octave
            amplitude = 1.0 / freq
            noise = rng.normal(0, amplitude, (size // freq + 2, size // freq + 2))
            from scipy.ndimage import zoom
            from scipy.ndimage import gaussian_filter
            upsampled = zoom(noise, freq, order=1)[:size, :size]
            heightmap += upsampled

        # Normalize to [-50, 50] meters
        heightmap = (heightmap - heightmap.min()) / (heightmap.max() - heightmap.min())
        heightmap = heightmap * 100.0 - 50.0

        # Add crater bowl features
        for _ in range(5):
            cx = rng.integers(size // 4, 3 * size // 4)
            cy = rng.integers(size // 4, 3 * size // 4)
            cr = rng.integers(20, 60)
            depth = rng.uniform(5.0, 30.0)
            y_idx, x_idx = np.ogrid[:size, :size]
            dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
            rim_mask = np.exp(-((dist - cr) ** 2) / (2 * (cr * 0.15) ** 2))
            bowl_mask = np.where(dist < cr, (1 - (dist / cr) ** 2), 0)
            heightmap += rim_mask * depth * 0.3
            heightmap -= bowl_mask * depth

        return heightmap.astype(np.float32)

    def _apply_regolith_material(self, prim) -> None:
        """Apply lunar regolith surface material (low albedo, high friction)."""
        stage = omni.usd.get_context().get_stage()
        mat_path = "/World/Materials/LunarRegolith"

        material = UsdShade.Material.Define(stage, mat_path)
        pbr_shader = UsdShade.Shader.Define(stage, f"{mat_path}/PBRShader")
        pbr_shader.CreateIdAttr("UsdPreviewSurface")
        # Lunar regolith: very dark (albedo ~0.07), rough
        pbr_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(0.07, 0.065, 0.06)
        )
        pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.95)
        pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

        material.CreateSurfaceOutput().ConnectToSource(
            pbr_shader.ConnectableAPI(), "surface"
        )
        UsdShade.MaterialBindingAPI(prim).Bind(material)

    def _add_terrain_physics(self, prim) -> None:
        """Add physics collision with regolith friction properties."""
        UsdPhysics.CollisionAPI.Apply(prim)
        physics_material_path = "/World/Physics/RegolithMaterial"
        stage = omni.usd.get_context().get_stage()

        phys_mat = UsdShade.Material.Define(stage, physics_material_path)
        UsdPhysics.MaterialAPI.Apply(phys_mat.GetPrim())
        mat_api = UsdPhysics.MaterialAPI(phys_mat.GetPrim())
        mat_api.CreateStaticFrictionAttr().Set(self.REGOLITH_STATIC_FRICTION)
        mat_api.CreateDynamicFrictionAttr().Set(self.REGOLITH_DYNAMIC_FRICTION)
        mat_api.CreateRestitutionAttr().Set(self.REGOLITH_RESTITUTION)

        UsdShade.MaterialBindingAPI(prim).Bind(
            phys_mat, UsdShade.Tokens.weakerThanDescendants, "physics"
        )

    async def _load_rover(self) -> None:
        """Load LPAS rover USD asset."""
        rover_usd = Path(__file__).parent / "assets" / "lpas_rover.usd"
        if rover_usd.exists():
            add_reference_to_stage(str(rover_usd), self._rover_prim_path)
        else:
            print(f"[LPAS Isaac] Rover USD not found at {rover_usd}, creating placeholder")
            self._create_rover_placeholder()

        # Position rover at deployment site (near relay station, on crater rim)
        stage = omni.usd.get_context().get_stage()
        rover_prim = stage.GetPrimAtPath(self._rover_prim_path)
        if rover_prim:
            xform = UsdGeom.Xformable(rover_prim)
            xform.AddTranslateOp().Set(Gf.Vec3d(50.0, 0.0, 5.0))

    def _create_rover_placeholder(self) -> None:
        """Create a simple rover proxy for testing until USD asset is ready."""
        stage = omni.usd.get_context().get_stage()
        rover_prim = stage.DefinePrim(self._rover_prim_path, "Xform")

        # Body box
        body = stage.DefinePrim(f"{self._rover_prim_path}/Body", "Cube")
        UsdGeom.Cube(body).CreateSizeAttr(1.0)
        UsdGeom.XformCommonAPI(body).SetScale(Gf.Vec3f(0.62, 1.4, 0.48))
        UsdGeom.XformCommonAPI(body).SetTranslate(Gf.Vec3d(0, 0, 0.52))
        UsdPhysics.CollisionAPI.Apply(body)
        UsdPhysics.RigidBodyAPI.Apply(rover_prim)

    async def _place_relay_station(self) -> None:
        """Place communication relay station on crater rim."""
        stage = omni.usd.get_context().get_stage()
        relay_sdf = PROJECT_ROOT / "gazebo_worlds" / "models" / "comms_relay_station" / "model.sdf"

        relay_prim = stage.DefinePrim(self._relay_station_path, "Xform")
        # Position: 2km from rover deployment, on elevated terrain
        UsdGeom.XformCommonAPI(relay_prim).SetTranslate(Gf.Vec3d(2000.0, 0.0, 50.0))
        print("[LPAS Isaac] Relay station placed at (2000, 0, 50)m")

    def _add_boulders(self, count: int = 50) -> None:
        """Scatter lunar boulders across terrain."""
        rng = np.random.default_rng(seed=123)
        stage = omni.usd.get_context().get_stage()

        for i in range(count):
            boulder_path = f"/World/Boulders/Boulder_{i:03d}"
            boulder_prim = stage.DefinePrim(boulder_path, "Sphere")

            radius = rng.uniform(0.3, 2.5)  # 0.3m to 2.5m radius boulders
            x = rng.uniform(-500, 500)
            y = rng.uniform(-500, 500)

            UsdGeom.Sphere(boulder_prim).CreateRadiusAttr(radius)
            UsdGeom.XformCommonAPI(boulder_prim).SetTranslate(
                Gf.Vec3d(float(x), float(y), float(radius * 0.5))
            )
            UsdGeom.XformCommonAPI(boulder_prim).SetScale(
                Gf.Vec3f(
                    float(rng.uniform(0.8, 1.4)),
                    float(rng.uniform(0.8, 1.4)),
                    float(rng.uniform(0.5, 0.9)),
                )
            )
            UsdPhysics.CollisionAPI.Apply(boulder_prim)
            self._apply_regolith_material(boulder_prim)

    def _add_crater_features(self) -> None:
        """Add named PSR crater features with communication shadow markers."""
        craters = [
            {"name": "PSR_Alpha", "pos": (-200, 150), "radius": 80, "depth": 35},
            {"name": "PSR_Beta",  "pos": (300, -250), "radius": 120, "depth": 50},
            {"name": "PSR_Gamma", "pos": (-450, -100), "radius": 60, "depth": 25},
        ]

        stage = omni.usd.get_context().get_stage()
        for c in craters:
            # Add annotation sphere at crater center (for RViz/Isaac visualization)
            ann_path = f"/World/Craters/{c['name']}_marker"
            ann_prim = stage.DefinePrim(ann_path, "Sphere")
            UsdGeom.Sphere(ann_prim).CreateRadiusAttr(5.0)
            UsdGeom.XformCommonAPI(ann_prim).SetTranslate(
                Gf.Vec3d(float(c["pos"][0]), float(c["pos"][1]), float(c["depth"] * 0.5))
            )
            print(f"[LPAS Isaac] Crater {c['name']} placed at {c['pos']}, r={c['radius']}m")

    def _configure_sensors(self) -> None:
        """Configure ROS2 bridge for sensor data streaming."""
        try:
            import omni.isaac.ros2_bridge
            print("[LPAS Isaac] ROS2 bridge available — configuring sensor topics")
            # Camera, LIDAR, IMU topics configured in rover USD asset
        except ImportError:
            print("[LPAS Isaac] ROS2 bridge not available — sensors disabled")

    def run(self, duration_s: float = float("inf")) -> None:
        """Run the simulation."""
        if not self._setup_complete:
            raise RuntimeError("Call setup() before run()")

        print(f"[LPAS Isaac] Starting simulation (duration={duration_s}s)")
        t = 0.0
        while t < duration_s:
            self.world.step(render=not self._headless)
            t += self.world.get_physics_dt()

    def save_metrics(self, output_path: str) -> None:
        """Save simulation metrics to JSON."""
        metrics = {
            "gravity_m_s2": self.LUNAR_GRAVITY,
            "regolith_static_friction": self.REGOLITH_STATIC_FRICTION,
            "terrain_loaded": self._setup_complete,
        }
        with open(output_path, "w") as f:
            json.dump(metrics, f, indent=2)


async def main() -> None:
    env = LunarPSREnvironment(headless=False)
    await env.setup()
    env.run(duration_s=300.0)  # 5-minute demo run


if __name__ == "__main__":
    asyncio.ensure_future(main())
