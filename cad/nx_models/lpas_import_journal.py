"""
LPAS NX Import Journal — NASA Heritage Models
Run via: File → Execute → Journal in NX 1980

Imports real NASA Curiosity rover STL meshes (from NASA-3D-Resources,
public domain) plus LPAS-specific components, then assembles them.

Steps:
  1. Each STL → saved as individual .prt in cad/nx_models/parts/
  2. Master assembly created with all components positioned
"""
import os
import NXOpen
import NXOpen.UF

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE         = r"C:\Users\aryan\Code\apps\lspace\cad\nx_models"
HERITAGE_DIR = BASE + r"\nasa_heritage_models"
OUTPUT_DIR   = BASE + r"\parts"
ASSEMBLY     = BASE + r"\lpas_rover_assembly.prt"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Models to import ──────────────────────────────────────────────────────────
# Each entry: (stl_filename, part_name, [x_mm, y_mm, z_mm])
# Positions are URDF joint values × 1000 (metres → mm), X=fwd, Y=left, Z=up
MODELS = [
    # ── Real NASA Curiosity rover STLs (NASA-3D-Resources, public domain) ─────
    # Part 1: Curiosity body — heritage reference for LPAS chassis layout
    ("nasa_curiosity_body.stl",       "curiosity_body",       [   0,    0,    0]),
    # Part 2: All instruments, mast, HGA, rocker arms, bogie, solar panels
    ("nasa_curiosity_bogie.stl",      "curiosity_components", [   0,    0,    0]),
    # Part 3: Joint pins and hub connectors
    ("nasa_curiosity_pins_hubs.stl",  "curiosity_pins_hubs",  [   0,    0,    0]),
    # Part 4: All 6 wheels
    ("nasa_curiosity_wheel_left.stl", "curiosity_wheels",     [   0,    0, -350]),

    # ── MER Spirit/Opportunity (converted from .blend, if available) ──────────
    ("nasa_mer_spirit_opportunity.stl", "mer_spirit_opportunity", [2000, 0, 0]),

    # ── Perseverance rover (if downloaded) ────────────────────────────────────
    # ("nasa_perseverance_rover.stl", "perseverance_rover", [1500, 0, 0]),
]


def import_stl(session, stl_path, prt_path):
    """Import one STL into a new NX part and save it. Returns part or None."""
    if not os.path.isfile(stl_path):
        print(f"  SKIP: not found — {stl_path}")
        return None

    size_mb = os.path.getsize(stl_path) / 1e6
    print(f"  Importing {os.path.basename(stl_path)} ({size_mb:.1f} MB)...")

    try:
        # Close if already open
        for part in list(session.Parts):
            if part.FullPath and part.FullPath.lower() == prt_path.lower():
                part.Close(
                    NXOpen.BasePart.CloseWholeTree.FalseValue,
                    NXOpen.BasePart.CloseModified.UseResponses,
                    None,
                )
                break

        # Create a new empty part to receive the import
        session.Parts.NewDisplay(prt_path, NXOpen.Part.Units.Millimeters)
        workPart = session.Parts.Work

        # Import STL body
        builder = workPart.ImportManager.CreateStlImportBuilder()
        builder.InputFileName     = stl_path
        # STLs from NASA-3D-Resources printing files are in mm
        # (verify by checking model size after import — Curiosity body is ~1000mm long)
        builder.UnitType          = NXOpen.StlImportBuilder.Units.Millimeters
        builder.Commit()
        builder.Destroy()

        session.Parts.SaveAs(prt_path)
        print(f"    -> saved as {os.path.basename(prt_path)}")
        return workPart

    except Exception as exc:
        print(f"  ERROR importing {os.path.basename(stl_path)}: {exc}")
        return None


def add_to_assembly(workPart, prt_path, position, name):
    """Add a component .prt to the active assembly at position (mm)."""
    if not os.path.isfile(prt_path):
        return None
    try:
        x, y, z = position
        comp = workPart.ComponentAssembly.AddComponent(
            prt_path,
            "-1",
            name,
            NXOpen.Point3d(x, y, z),
            NXOpen.Vector3d(1, 0, 0),
            NXOpen.Vector3d(0, 1, 0),
            -1,
            None,
        )
        print(f"  + {name} at ({x}, {y}, {z}) mm")
        return comp
    except Exception as exc:
        print(f"  WARN adding {name}: {exc}")
        return None


def main():
    session = NXOpen.Session.GetSession()

    print("=" * 60)
    print("  LPAS NX Heritage Import Journal")
    print("  NASA Curiosity + LPAS rover components")
    print("=" * 60)

    # ── Step 1: Import each STL as its own .prt ───────────────────────────────
    print("\n[1/2] Importing STL models as NX parts...")
    imported = {}

    for stl_file, part_name, position in MODELS:
        stl_path = os.path.join(HERITAGE_DIR, stl_file)
        prt_path = os.path.join(OUTPUT_DIR, part_name + ".prt")
        part = import_stl(session, stl_path, prt_path)
        if part:
            imported[part_name] = (prt_path, position)

    print(f"\n  {len(imported)}/{len(MODELS)} parts imported to:")
    print(f"  {OUTPUT_DIR}")

    # ── Step 2: Build master assembly ────────────────────────────────────────
    print("\n[2/2] Creating master assembly...")
    session.Parts.NewDisplay(ASSEMBLY, NXOpen.Part.Units.Millimeters)
    workPart = session.Parts.Work
    added = 0

    for part_name, (prt_path, position) in imported.items():
        comp = add_to_assembly(workPart, prt_path, position, part_name)
        if comp:
            added += 1

    session.Parts.SaveAs(ASSEMBLY)

    print(f"\n  Assembly saved: {ASSEMBLY}")
    print(f"  {added} components added")
    print()
    print("  NASA models loaded:")
    print("    curiosity_body      — Curiosity rover chassis (heritage ref)")
    print("    curiosity_components — All Curiosity instruments, mast, HGA, suspension")
    print("    curiosity_wheels    — Curiosity wheel assembly")
    print()
    print("  To edit: double-click any component in the assembly tree")
    print("  To add Perseverance: run scripts/download_perseverance.py then re-run journal")
    print("=" * 60)


main()
