# generate_placeholder_meshes.py — Generate placeholder ASCII STL meshes for LPAS lunar rover assembly components

import math
import os
import shutil

import numpy as np

MESHES_DIR = "/home/user/lspace/ros2_ws/src/lunar_scout_description/meshes"
EXPORT_DIR = "/home/user/lspace/cad/nx_models/mesh_exports"

COMPONENTS = [
    {"name": "chassis_body",       "type": "box",      "dims": (1.5, 0.9, 0.4)},
    {"name": "rocker_arm_left",    "type": "box",      "dims": (0.95, 0.08, 0.06)},
    {"name": "rocker_arm_right",   "type": "box",      "dims": (0.95, 0.08, 0.06)},
    {"name": "bogie_arm_left",     "type": "box",      "dims": (0.5, 0.07, 0.05)},
    {"name": "bogie_arm_right",    "type": "box",      "dims": (0.5, 0.07, 0.05)},
    {"name": "wheel_assembly",     "type": "cylinder", "dims": (0.25, 0.175)},
    {"name": "wheel_fl",           "type": "cylinder", "dims": (0.25, 0.175)},
    {"name": "wheel_fr",           "type": "cylinder", "dims": (0.25, 0.175)},
    {"name": "wheel_ml",           "type": "cylinder", "dims": (0.25, 0.175)},
    {"name": "wheel_mr",           "type": "cylinder", "dims": (0.25, 0.175)},
    {"name": "wheel_rl",           "type": "cylinder", "dims": (0.25, 0.175)},
    {"name": "wheel_rr",           "type": "cylinder", "dims": (0.25, 0.175)},
    {"name": "nav_cam_assembly",   "type": "box",      "dims": (0.15, 0.12, 0.10)},
    {"name": "hga_dish",           "type": "cylinder", "dims": (0.25, 0.02)},
    {"name": "solar_array_panel",  "type": "box",      "dims": (1.2, 0.8, 0.01)},
    {"name": "electronics_bay",    "type": "box",      "dims": (0.6, 0.4, 0.3)},
    {"name": "drill_assembly",     "type": "cylinder", "dims": (0.03, 1.0)},
    {"name": "mast_assembly",      "type": "cylinder", "dims": (0.04, 1.2)},
    {"name": "lga_antenna",        "type": "cylinder", "dims": (0.1, 0.05)},
]


def triangles_to_stl(name: str, triangles: list[tuple[np.ndarray, np.ndarray, np.ndarray]]) -> str:
    # triangles: list of (v0, v1, v2) each a 3-element array
    lines = [f"solid {name}"]
    for v0, v1, v2 in triangles:
        edge1 = v1 - v0
        edge2 = v2 - v0
        normal = np.cross(edge1, edge2)
        length = np.linalg.norm(normal)
        if length > 0.0:
            normal = normal / length
        else:
            normal = np.array([0.0, 0.0, 1.0])
        lines.append(f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}")
        lines.append("    outer loop")
        lines.append(f"      vertex {v0[0]:.6f} {v0[1]:.6f} {v0[2]:.6f}")
        lines.append(f"      vertex {v1[0]:.6f} {v1[1]:.6f} {v1[2]:.6f}")
        lines.append(f"      vertex {v2[0]:.6f} {v2[1]:.6f} {v2[2]:.6f}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {name}")
    return "\n".join(lines) + "\n"


def box_triangles(lx: float, ly: float, lz: float) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    # Centered at origin; 6 faces × 2 triangles = 12 triangles
    hx, hy, hz = lx / 2.0, ly / 2.0, lz / 2.0
    # Define 8 corners
    c = {
        "lll": np.array([-hx, -hy, -hz]),
        "rll": np.array([ hx, -hy, -hz]),
        "rrl": np.array([ hx,  hy, -hz]),
        "lrl": np.array([-hx,  hy, -hz]),
        "llu": np.array([-hx, -hy,  hz]),
        "rlu": np.array([ hx, -hy,  hz]),
        "rru": np.array([ hx,  hy,  hz]),
        "lru": np.array([-hx,  hy,  hz]),
    }
    tris = []
    # Bottom face (z = -hz), normal pointing -z
    tris.append((c["lll"], c["rrl"], c["rll"]))
    tris.append((c["lll"], c["lrl"], c["rrl"]))
    # Top face (z = +hz), normal pointing +z
    tris.append((c["llu"], c["rlu"], c["rru"]))
    tris.append((c["llu"], c["rru"], c["lru"]))
    # Front face (y = -hy), normal pointing -y
    tris.append((c["lll"], c["rll"], c["rlu"]))
    tris.append((c["lll"], c["rlu"], c["llu"]))
    # Back face (y = +hy), normal pointing +y
    tris.append((c["rrl"], c["lrl"], c["lru"]))
    tris.append((c["rrl"], c["lru"], c["rru"]))
    # Left face (x = -hx), normal pointing -x
    tris.append((c["lrl"], c["lll"], c["llu"]))
    tris.append((c["lrl"], c["llu"], c["lru"]))
    # Right face (x = +hx), normal pointing +x
    tris.append((c["rll"], c["rrl"], c["rru"]))
    tris.append((c["rll"], c["rru"], c["rlu"]))
    return tris


def cylinder_triangles(radius: float, height: float, n_sides: int = 16) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    # Centered at origin along Z axis; n_sides*4 triangles
    hz = height / 2.0
    angles = [2.0 * math.pi * i / n_sides for i in range(n_sides)]
    top_center = np.array([0.0, 0.0,  hz])
    bot_center = np.array([0.0, 0.0, -hz])
    top_ring = [np.array([radius * math.cos(a), radius * math.sin(a),  hz]) for a in angles]
    bot_ring = [np.array([radius * math.cos(a), radius * math.sin(a), -hz]) for a in angles]

    tris = []
    for i in range(n_sides):
        j = (i + 1) % n_sides
        # Top cap fan — winding outward when viewed from +z
        tris.append((top_center, top_ring[i], top_ring[j]))
        # Bottom cap fan — winding outward when viewed from -z
        tris.append((bot_center, bot_ring[j], bot_ring[i]))
        # Side quad split into two triangles
        tris.append((bot_ring[i], top_ring[i], top_ring[j]))
        tris.append((bot_ring[i], top_ring[j], bot_ring[j]))
    return tris


def generate_stl(component: dict) -> str:
    name = component["name"]
    prim = component["type"]
    dims = component["dims"]
    if prim == "box":
        tris = box_triangles(*dims)
    elif prim == "cylinder":
        tris = cylinder_triangles(*dims)
    else:
        raise ValueError(f"Unknown primitive type: {prim}")
    return triangles_to_stl(name, tris)


def main() -> None:
    os.makedirs(MESHES_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)

    generated = []
    for comp in COMPONENTS:
        stl_content = generate_stl(comp)
        filename = comp["name"] + ".stl"
        primary_path = os.path.join(MESHES_DIR, filename)
        export_path = os.path.join(EXPORT_DIR, filename)

        with open(primary_path, "w") as fh:
            fh.write(stl_content)
        shutil.copy2(primary_path, export_path)

        tri_count = stl_content.count("endfacet")
        prim_desc = comp["type"]
        if prim_desc == "box":
            size_str = "×".join(str(d) for d in comp["dims"]) + " m"
        else:
            size_str = f"r={comp['dims'][0]} h={comp['dims'][1]} m"
        generated.append((filename, prim_desc, size_str, tri_count))
        print(f"  {filename:<30}  {prim_desc:<8}  {size_str:<22}  {tri_count:>3} triangles")

    print()
    print(f"Generated {len(generated)} STL files")
    print(f"  Primary : {MESHES_DIR}")
    print(f"  Export  : {EXPORT_DIR}")


if __name__ == "__main__":
    main()
