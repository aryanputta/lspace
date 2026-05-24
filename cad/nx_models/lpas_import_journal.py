"""
LPAS NX Import Journal — Run via: File → Execute → Journal in NX 1980
Imports all 28 STL meshes as component parts then assembles them.

Usage:
  1. Open NX
  2. File → Execute → Journal → browse to this file → OK
"""
import os
import math
import NXOpen
import NXOpen.UF
import NXOpen.Assemblies

# ── Paths ─────────────────────────────────────────────────────────────────────
STL_DIR     = r"C:\Users\aryan\Code\apps\lspace\ros2_ws\src\lunar_scout_description\meshes"
OUTPUT_DIR  = r"C:\Users\aryan\Code\apps\lspace\cad\nx_models\parts"
ASSEMBLY    = r"C:\Users\aryan\Code\apps\lspace\cad\nx_models\lpas_rover_assembly.prt"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── URDF-derived positions [x, y, z] in mm (URDF values × 1000) ──────────────
# coordinate frame: X=forward, Y=left, Z=up
COMPONENT_POSES = {
    "chassis_body":      ( 0.0,    0.0,   0.0),
    "electronics_bay":   ( 0.0,    0.0,  20.0),
    "science_bay":       ( 550.0,  0.0,  50.0),
    "solar_array_panel": ( 0.0,    0.0, 250.0),
    "thermal_radiator":  (-200.0,  0.0, 100.0),
    "mast_assembly":     ( 500.0,  0.0, 400.0),
    "hga_mast":          (-300.0,  0.0, 300.0),
    "hga_dish":          (-300.0,  0.0, 600.0),
    "lga_antenna":       ( 300.0, 300.0, 400.0),
    "uhf_antenna":       (-300.0, 300.0, 400.0),
    "nav_cam_assembly":  ( 500.0,  0.0, 500.0),
    "hazcam_front":      ( 700.0,  0.0, 200.0),
    "lidar_housing":     ( 400.0,  0.0, 350.0),
    "drill_assembly":    ( 600.0,  0.0,-200.0),
    "drill_mechanism":   ( 600.0,  0.0,-350.0),
    "spectrometer":      ( 500.0,100.0, 100.0),
    # Rocker-bogie suspension — x=±600 front/rear, y=±700 left/right, z=-350 wheel plane
    "rocker_arm_left":   ( 200.0,  700.0,-200.0),
    "rocker_arm_right":  ( 200.0, -700.0,-200.0),
    "bogie_arm_left":    (-300.0,  700.0,-250.0),
    "bogie_arm_right":   (-300.0, -700.0,-250.0),
    "diff_bar":          (   0.0,    0.0, -50.0),
    "wheel_fl":          ( 600.0,  700.0,-350.0),
    "wheel_fr":          ( 600.0, -700.0,-350.0),
    "wheel_ml":          (   0.0,  700.0,-350.0),
    "wheel_mr":          (   0.0, -700.0,-350.0),
    "wheel_rl":          (-600.0,  700.0,-350.0),
    "wheel_rr":          (-600.0, -700.0,-350.0),
    "wheel_assembly":    (   0.0,    0.0,-350.0),
}


def import_stl_as_part(session, stl_path, part_path):
    """Import one STL file, save as .prt, return the part tag."""
    try:
        # Close any stale part with same name
        for part in session.Parts:
            if part.FullPath.lower() == part_path.lower():
                part.Close(NXOpen.BasePart.CloseWholeTree.FalseValue,
                           NXOpen.BasePart.CloseModified.UseResponses, None)
                break

        # Create/open fresh part to receive the import
        newPart = session.Parts.NewDisplay(part_path, NXOpen.Part.Units.Millimeters)
        workPart = session.Parts.Work

        # Import STL body into the active part
        importBuilder = workPart.ImportManager.CreateStlImportBuilder()
        importBuilder.InputFileName = stl_path
        # Units.Meters = 0 (URDF/ROS2 STLs are in metres)
        importBuilder.UnitType = NXOpen.StlImportBuilder.Units.Meters
        importBuilder.Commit()
        importBuilder.Destroy()

        session.Parts.SaveAs(part_path)
        return workPart

    except Exception as e:
        print(f"  WARN: could not import {os.path.basename(stl_path)}: {e}")
        return None


def add_component(workPart, part_path, position_mm, name):
    """Add a component part to the active assembly at the given position."""
    try:
        x, y, z = position_mm
        origin = NXOpen.Point3d(x, y, z)
        xVec   = NXOpen.Vector3d(1.0, 0.0, 0.0)
        yVec   = NXOpen.Vector3d(0.0, 1.0, 0.0)

        comp = workPart.ComponentAssembly.AddComponent(
            part_path,
            "-1",       # use default reference set
            name,
            origin, xVec, yVec,
            -1,         # layer = -1 (original layer)
            None        # component set
        )
        return comp
    except Exception as e:
        print(f"  WARN: could not add component {name}: {e}")
        return None


def main():
    session  = NXOpen.Session.GetSession()
    ufSess   = NXOpen.UF.UFSession.GetUFSession()

    print("=" * 60)
    print("  LPAS NX Import Journal")
    print("=" * 60)

    # ── Step 1: Import each STL as its own .prt ───────────────────────────────
    print("\n[1/2] Importing STL components as NX parts...")
    stl_files = sorted(f for f in os.listdir(STL_DIR) if f.lower().endswith(".stl"))
    imported_parts = {}

    for stl_file in stl_files:
        name     = os.path.splitext(stl_file)[0]
        stl_path = os.path.join(STL_DIR, stl_file)
        prt_path = os.path.join(OUTPUT_DIR, name + ".prt")
        print(f"  Importing {stl_file}...")
        part = import_stl_as_part(session, stl_path, prt_path)
        if part:
            imported_parts[name] = prt_path
            print(f"    -> saved as {os.path.basename(prt_path)}")

    print(f"\n  {len(imported_parts)} parts imported to {OUTPUT_DIR}")

    # ── Step 2: Build master assembly ────────────────────────────────────────
    print("\n[2/2] Creating master assembly...")
    assembly = session.Parts.NewDisplay(ASSEMBLY, NXOpen.Part.Units.Millimeters)
    workPart = session.Parts.Work
    added = 0

    for name, prt_path in imported_parts.items():
        pos = COMPONENT_POSES.get(name, (0.0, 0.0, 0.0))
        print(f"  Adding {name} at {pos}...")
        comp = add_component(workPart, prt_path, pos, name)
        if comp:
            added += 1

    session.Parts.SaveAs(ASSEMBLY)
    print(f"\n  Assembly saved: {ASSEMBLY}")
    print(f"  {added} components added")
    print("\n  Done! Open lpas_rover_assembly.prt to edit the rover.")
    print("=" * 60)


main()
