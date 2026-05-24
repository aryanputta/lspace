"""
NX CAD → Gazebo/ROS2 mesh pipeline

Converts Siemens NX STEP/STL exports to formats usable in:
  - ROS2 URDF (STL/DAE mesh references)
  - Gazebo SDF (OBJ or STL)
  - NVIDIA Isaac Sim (USD/OBJ)

Workflow:
  NX CAD → export STEP → FreeCAD conversion → STL/DAE → URDF mesh refs

Real pipeline: Uses FreeCAD's headless Python API (available on Linux)
  pip install freecad-headless  OR  flatpak install org.freecadweb.FreeCAD

Usage:
  python nx_to_urdf_pipeline.py --step_dir cad/step_exports --output ros2_ws/src/...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("lpas.cad_pipeline")

# Expected NX assembly STEP exports
LPAS_COMPONENTS = [
    "chassis_body",
    "rocker_arm_left",
    "rocker_arm_right",
    "bogie_arm_left",
    "bogie_arm_right",
    "diff_bar",
    "wheel_assembly",         # single wheel — instanced 6×
    "solar_array_panel",      # single panel — instanced 2×
    "electronics_bay",
    "drill_mechanism",
    "spectrometer_housing",
    "uhf_antenna",
    "hga_dish",
    "hga_mast",
    "nav_cam_assembly",
    "hazcam",
    "lidar_housing",
    "science_bay",
]

MESH_DEST = Path(__file__).parent.parent.parent / \
    "ros2_ws" / "src" / "lunar_scout_description" / "meshes"

GAZEBO_MESH_DEST = Path(__file__).parent.parent.parent / "gazebo_worlds" / "models" / "lpas_rover"


@dataclass
class MeshProduct:
    component: str
    step_path: Optional[Path]
    stl_path: Optional[Path] = None
    dae_path: Optional[Path] = None
    obj_path: Optional[Path] = None
    usd_path: Optional[Path] = None
    scale: float = 1.0
    mass_kg: float = 0.0
    notes: str = ""


def check_freecad_available() -> bool:
    try:
        result = subprocess.run(
            ["freecad", "--version"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_blender_available() -> bool:
    try:
        result = subprocess.run(
            ["blender", "--version"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def step_to_stl_freecad(step_path: Path, stl_path: Path) -> bool:
    """Convert STEP file to STL using FreeCAD headless Python API."""
    if not check_freecad_available():
        log.warning("FreeCAD not available — skipping STEP→STL conversion")
        return False

    freecad_script = f"""
import FreeCAD
import Part
import Mesh

doc = FreeCAD.newDocument()
shape = Part.Shape()
shape.read('{step_path}')
solid = shape.Solids[0] if shape.Solids else shape
mesh = doc.addObject("Mesh::Feature", "Mesh")
mesh.Mesh = MeshPart.meshFromShape(solid, LinearDeflection=0.001, AngularDeflection=0.1)
mesh.Mesh.write('{stl_path}')
print(f"Exported: {stl_path}")
"""
    script_file = stl_path.with_suffix(".freecad_script.py")
    script_file.write_text(freecad_script)

    result = subprocess.run(
        ["freecadcmd", str(script_file)],
        capture_output=True, text=True, timeout=120
    )
    script_file.unlink(missing_ok=True)

    if result.returncode != 0:
        log.error(f"FreeCAD error: {result.stderr}")
        return False

    log.info(f"STL exported: {stl_path}")
    return True


def stl_to_dae_blender(stl_path: Path, dae_path: Path) -> bool:
    """Convert STL to COLLADA (.dae) using Blender for RViz material support."""
    if not check_blender_available():
        log.warning("Blender not available — skipping STL→DAE conversion")
        return False

    blender_script = f"""
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_mesh.stl(filepath='{stl_path}')
for obj in bpy.context.selected_objects:
    mat = bpy.data.materials.new(name="lpas_aluminium")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.7, 0.7, 0.72, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.5
    bsdf.inputs["Metallic"].default_value = 0.8
    obj.data.materials.append(mat)
bpy.ops.wm.collada_export(filepath='{dae_path}', use_texture_copies=False)
"""
    script_file = dae_path.with_suffix(".blender_script.py")
    script_file.write_text(blender_script)

    result = subprocess.run(
        ["blender", "--background", "--python", str(script_file)],
        capture_output=True, text=True, timeout=120
    )
    script_file.unlink(missing_ok=True)

    if result.returncode != 0:
        log.error(f"Blender error: {result.stderr}")
        return False

    log.info(f"DAE exported: {dae_path}")
    return True


def generate_placeholder_stl(output_path: Path, component: str) -> None:
    """Generate a minimal ASCII STL placeholder when NX export is unavailable."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Geometry configs per component type
    configs = {
        "chassis_body":       (0.70, 0.31, 0.24),
        "wheel_assembly":     (0.25, 0.25, 0.09),  # cylinder approx
        "rocker_arm_left":    (0.35, 0.02, 0.02),
        "bogie_arm_left":     (0.25, 0.02, 0.02),
        "solar_array_panel":  (0.50, 0.30, 0.003),
        "drill_mechanism":    (0.025, 0.025, 0.60),
        "electronics_bay":    (0.20, 0.15, 0.10),
        "nav_cam_assembly":   (0.05, 0.05, 0.06),
        "hga_dish":           (0.25, 0.25, 0.05),
        "lidar_housing":      (0.05, 0.05, 0.07),
    }
    hx, hy, hz = configs.get(component, (0.05, 0.05, 0.05))

    # Simple box STL
    vertices = [
        (-hx, -hy, 0),  (hx, -hy, 0),  (hx, hy, 0),  (-hx, hy, 0),
        (-hx, -hy, hz*2), (hx, -hy, hz*2), (hx, hy, hz*2), (-hx, hy, hz*2),
    ]
    faces = [
        (0,1,2),(0,2,3),(4,5,6),(4,6,7),  # bottom/top
        (0,1,5),(0,5,4),(2,3,7),(2,7,6),  # sides
        (1,2,6),(1,6,5),(0,3,7),(0,7,4),  # front/back
    ]

    with open(output_path, "w") as f:
        f.write(f"solid {component}\n")
        for tri in faces:
            v0, v1, v2 = [vertices[i] for i in tri]
            # Compute face normal
            e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
            e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
            n = (e1[1]*e2[2]-e1[2]*e2[1], e1[2]*e2[0]-e1[0]*e2[2], e1[0]*e2[1]-e1[1]*e2[0])
            mag = (n[0]**2 + n[1]**2 + n[2]**2) ** 0.5 + 1e-12
            f.write(f"  facet normal {n[0]/mag:.6f} {n[1]/mag:.6f} {n[2]/mag:.6f}\n")
            f.write("    outer loop\n")
            for v in (v0, v1, v2):
                f.write(f"      vertex {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
        f.write(f"endsolid {component}\n")

    log.info(f"Placeholder STL: {output_path}")


def generate_urdf_mesh_block(component: str, stl_rel_path: str) -> str:
    """Generate XACRO mesh reference block for URDF."""
    return f"""  <!-- {component} mesh (from NX export) -->
  <xacro:macro name="{component}_mesh" params="">
    <visual>
      <geometry>
        <mesh filename="package://lunar_scout_description/meshes/{stl_rel_path}"/>
      </geometry>
    </visual>
    <collision>
      <geometry>
        <mesh filename="package://lunar_scout_description/meshes/{stl_rel_path}"/>
      </geometry>
    </collision>
  </xacro:macro>
"""


def process_component(step_dir: Path, component: str) -> MeshProduct:
    step_path = step_dir / f"{component}.step"
    if not step_path.exists():
        step_path = step_dir / f"{component}.stp"

    product = MeshProduct(
        component=component,
        step_path=step_path if step_path.exists() else None,
    )

    MESH_DEST.mkdir(parents=True, exist_ok=True)
    stl_path = MESH_DEST / f"{component}.stl"
    dae_path = MESH_DEST / f"{component}.dae"

    if product.step_path and product.step_path.exists():
        log.info(f"Converting {component}: {product.step_path}")
        if step_to_stl_freecad(product.step_path, stl_path):
            product.stl_path = stl_path
            if stl_to_dae_blender(stl_path, dae_path):
                product.dae_path = dae_path
    else:
        log.warning(f"STEP not found for {component} — generating placeholder")
        generate_placeholder_stl(stl_path, component)
        product.stl_path = stl_path
        product.notes = "placeholder — replace with NX export"

    return product


def write_gazebo_model_config(products: list[MeshProduct]) -> None:
    """Write Gazebo model.config and SDF mesh references."""
    GAZEBO_MESH_DEST.mkdir(parents=True, exist_ok=True)

    config = """<?xml version="1.0"?>
<model>
  <name>LPAS Rover</name>
  <version>1.0</version>
  <sdf version="1.8">model.sdf</sdf>
  <description>Lunar PSR Autonomy Scout rover — NX mesh imports</description>
</model>
"""
    (GAZEBO_MESH_DEST / "model.config").write_text(config)

    sdf_meshes = "\n".join(
        f'    <mesh><uri>model://lpas_rover/meshes/{p.component}.stl</uri></mesh>'
        for p in products if p.stl_path
    )
    log.info(f"Gazebo model config written to {GAZEBO_MESH_DEST}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(description="NX CAD → Gazebo/ROS2 mesh pipeline")
    parser.add_argument("--step_dir", type=Path,
                        default=Path(__file__).parent.parent / "step_exports",
                        help="Directory containing NX STEP exports")
    parser.add_argument("--components", nargs="+",
                        default=LPAS_COMPONENTS, help="Components to process")
    parser.add_argument("--force_placeholder", action="store_true",
                        help="Generate placeholder STLs (no NX required)")
    args = parser.parse_args()

    log.info(f"LPAS NX→Gazebo pipeline: {len(args.components)} components")
    log.info(f"STEP directory: {args.step_dir}")
    log.info(f"Mesh destination: {MESH_DEST}")

    products: list[MeshProduct] = []
    for comp in args.components:
        product = process_component(args.step_dir, comp)
        products.append(product)

    write_gazebo_model_config(products)

    # Write URDF mesh include file
    urdf_include = "".join(
        generate_urdf_mesh_block(p.component, f"{p.component}.stl")
        for p in products
    )
    urdf_path = MESH_DEST.parent / "urdf" / "mesh_includes.xacro"
    urdf_path.parent.mkdir(parents=True, exist_ok=True)
    urdf_path.write_text(
        '<?xml version="1.0"?>\n<robot xmlns:xacro="http://www.ros.org/wiki/xacro">\n'
        + urdf_include + "\n</robot>\n"
    )
    log.info(f"URDF mesh includes: {urdf_path}")

    # Report
    ok = sum(1 for p in products if p.stl_path)
    placeholder = sum(1 for p in products if "placeholder" in p.notes)
    log.info(f"Pipeline complete: {ok}/{len(products)} STL exports "
             f"({placeholder} placeholders)")

    report = {
        "components": [
            {
                "name": p.component,
                "step": str(p.step_path) if p.step_path else None,
                "stl": str(p.stl_path) if p.stl_path else None,
                "dae": str(p.dae_path) if p.dae_path else None,
                "notes": p.notes,
            }
            for p in products
        ]
    }
    report_path = MESH_DEST.parent / "mesh_pipeline_report.json"
    report_path.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
