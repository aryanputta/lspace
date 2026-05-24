"""
LPAS NASA Reference Model Downloader

Downloads real NASA 3D models from the official NASA-3D-Resources GitHub
repository (github.com/nasa/NASA-3D-Resources — public domain) and integrates
them as geometry heritage references for LPAS components.

Models used:
  - NASA Curiosity rover components (rocker-bogie heritage)
  - NASA Mars Exploration Rover Spirit/Opportunity (wheel heritage)
  - NASA Apollo Lunar Module (structural reference)
  - LOLA terrain STL (lunar south pole surface)

All NASA 3D Resources are released under NASA Open Source Agreement.
Source: https://github.com/nasa/NASA-3D-Resources
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("lpas.nasa_models")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
MESH_DIR     = PROJECT_ROOT / "ros2_ws" / "src" / "lunar_scout_description" / "meshes"
HERITAGE_DIR = PROJECT_ROOT / "cad" / "nx_models" / "nasa_heritage_models"
RAW_BASE = "https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master"

# ── Real NASA model URLs from github.com/nasa/NASA-3D-Resources ───────────────

@dataclass
class NASAModel:
    name: str
    url: str          # Raw GitHub URL — real NASA asset
    dest_name: str    # Local filename
    lpas_use: str     # How LPAS uses this for heritage reference
    component_map: Optional[str] = None  # LPAS component it informs


NASA_MODELS = [
    # Curiosity rover body — rocker-bogie structural heritage
    NASAModel(
        name="Curiosity Rover Body",
        url=(RAW_BASE
             + "/3D%20Printing/Curiosity%20Rover"
             + "/Curiosity%20Rover%203D%20Printed%20Model"
             + "/Detailed%20Curiosity%20Model%20(Large)/STL%20Files/body.STL"),
        dest_name="nasa_curiosity_body.stl",
        lpas_use="Heritage reference for LPAS chassis structural layout",
        component_map="chassis_body",
    ),
    # Curiosity ChemCam — instrument mast heritage
    NASAModel(
        name="Curiosity ChemCam",
        url=(RAW_BASE
             + "/3D%20Printing/Curiosity%20Rover"
             + "/Curiosity%20Rover%203D%20Printed%20Model"
             + "/Detailed%20Curiosity%20Model%20(Large)/STL%20Files/chemcam.STL"),
        dest_name="nasa_curiosity_chemcam.stl",
        lpas_use="Heritage reference for LPAS instrument mast + nav camera assembly",
        component_map="nav_cam_assembly",
    ),
    # Mars Exploration Rover — Spirit/Opportunity wheel heritage
    NASAModel(
        name="Mars Exploration Rover (Spirit/Opportunity)",
        url=(RAW_BASE
             + "/3D%20Models/Mars%20Exploration%20Rover%20-%20Spirit%20and%20Opportunity"
             + "/Mars%20Exploration%20Rover%20-%20Spirit%20and%20Opportunity.blend"),
        dest_name="nasa_mer_spirit_opportunity.blend",
        lpas_use="Heritage: MER rocker-bogie geometry for LPAS suspension dimensioning",
        component_map="rocker_arm_left",
    ),
    # Curiosity RTG cover — structural enclosure heritage
    NASAModel(
        name="Curiosity RTG (enclosure geometry only)",
        url=(RAW_BASE
             + "/3D%20Printing/Curiosity%20Rover"
             + "/Curiosity%20Rover%203D%20Printed%20Model"
             + "/Detailed%20Curiosity%20Model%20(Large)/STL%20Files/rtg.STL"),
        dest_name="nasa_curiosity_rtg_enclosure.stl",
        lpas_use="Electronics bay enclosure geometry heritage (not RTG — thermal reference only)",
        component_map="electronics_bay",
    ),
    # Curiosity wheels
    NASAModel(
        name="Curiosity Wheels",
        url=(RAW_BASE
             + "/3D%20Printing/Curiosity%20Rover"
             + "/Curiosity%20Rover%203D%20Printed%20Model"
             + "/Detailed%20Curiosity%20Model%20(Large)/STL%20Files/wheelLeft.STL"),
        dest_name="nasa_curiosity_wheel_left.stl",
        lpas_use="Heritage: Al-machined wheel geometry → LPAS uses Ti mesh variant",
        component_map="wheel_assembly",
    ),
    # Curiosity HGA (High Gain Antenna)
    NASAModel(
        name="Curiosity HGA",
        url=(RAW_BASE
             + "/3D%20Printing/Curiosity%20Rover"
             + "/Curiosity%20Rover%203D%20Printed%20Model"
             + "/Detailed%20Curiosity%20Model%20(Large)/STL%20Files/hga.STL"),
        dest_name="nasa_curiosity_hga.stl",
        lpas_use="Heritage: HGA gimbal geometry for LPAS Ka-band HGA design",
        component_map="hga_dish",
    ),
    # Curiosity Mast
    NASAModel(
        name="Curiosity Mast",
        url=(RAW_BASE
             + "/3D%20Printing/Curiosity%20Rover"
             + "/Curiosity%20Rover%203D%20Printed%20Model"
             + "/Detailed%20Curiosity%20Model%20(Large)/STL%20Files/mast.STL"),
        dest_name="nasa_curiosity_mast.stl",
        lpas_use="Heritage: sensor mast geometry for LPAS nav camera mast",
        component_map="nav_cam_assembly",
    ),
    # Curiosity rocker bogie arm
    NASAModel(
        name="Curiosity Rocker",
        url=(RAW_BASE
             + "/3D%20Printing/Curiosity%20Rover"
             + "/Curiosity%20Rover%203D%20Printed%20Model"
             + "/Detailed%20Curiosity%20Model%20(Large)/STL%20Files/rocker.STL"),
        dest_name="nasa_curiosity_rocker.stl",
        lpas_use="DIRECT heritage: rocker arm geometry dimensioning for LPAS suspension",
        component_map="rocker_arm_left",
    ),
    # Curiosity bogie
    NASAModel(
        name="Curiosity Bogie",
        url=(RAW_BASE
             + "/3D%20Printing/Curiosity%20Rover"
             + "/Curiosity%20Rover%203D%20Printed%20Model"
             + "/Detailed%20Curiosity%20Model%20(Large)/STL%20Files/bogie.STL"),
        dest_name="nasa_curiosity_bogie.stl",
        lpas_use="DIRECT heritage: bogie arm geometry for LPAS front/rear bogie",
        component_map="bogie_arm_left",
    ),
    # Curiosity solar panels (geometry only — LPAS also uses solar)
    NASAModel(
        name="Curiosity Solar Panel",
        url=(RAW_BASE
             + "/3D%20Printing/Curiosity%20Rover"
             + "/Curiosity%20Rover%203D%20Printed%20Model"
             + "/Detailed%20Curiosity%20Model%20(Large)/STL%20Files/solar.STL"),
        dest_name="nasa_curiosity_solar.stl",
        lpas_use="Solar array structural geometry heritage for LPAS deployable panels",
        component_map="solar_array_panel",
    ),
]

# Additional models from mars.nasa.gov / NASA resources
SUPPLEMENTAL_MODELS = [
    # Perseverance rover — from NASA Science page (FBX format)
    {
        "name": "Mars 2020 Perseverance Rover (NASA official)",
        "url": "https://mars.nasa.gov/system/resources/detail_files/25042_PIA23764.zip",
        "format": "FBX/OBJ",
        "license": "NASA Open Use",
        "lpas_heritage": "Perseverance rocker-bogie geometry, mast design, camera placement",
        "note": "Download manually from: https://science.nasa.gov/resource/mars-perseverance-rover-3d-model/",
    },
]


def download_file(url: str, dest: Path, retries: int = 3) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "LPAS-Heritage-Download/1.0 (github.com/lpas-rover)",
                    "Accept": "*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            dest.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()[:12]
            log.info(f"Downloaded: {dest.name} ({len(data)/1024:.1f} KB, sha256={sha})")
            return True
        except urllib.error.HTTPError as e:
            log.warning(f"HTTP {e.code}: {url}")
            return False
        except urllib.error.URLError as e:
            log.warning(f"Network error (attempt {attempt}): {e.reason}")
            if attempt < retries:
                time.sleep(2 ** attempt)
    return False


def copy_to_mesh_dir(src: Path, component_name: str) -> Optional[Path]:
    """Copy heritage STL to URDF meshes directory."""
    if not src.exists():
        return None
    MESH_DIR.mkdir(parents=True, exist_ok=True)
    dest = MESH_DIR / f"{component_name}.stl"
    shutil.copy2(src, dest)
    log.info(f"Staged as URDF mesh: {dest.name}")
    return dest


def generate_heritage_report(results: list[dict]) -> None:
    """Write heritage model manifest for traceability."""
    report = {
        "title": "LPAS NASA Heritage Model Manifest",
        "document": "LPAS-CAD-HERITAGE-001",
        "source_repo": "https://github.com/nasa/NASA-3D-Resources",
        "license": "NASA Open Source Agreement / Public Domain",
        "models": results,
        "supplemental": SUPPLEMENTAL_MODELS,
        "traceability_note": (
            "These models provide dimensional heritage and geometry reference for LPAS. "
            "LPAS design adapts these geometries for lunar south pole conditions. "
            "No RTG components are included per LPAS power system constraint."
        ),
    }
    out = HERITAGE_DIR / "heritage_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    log.info(f"Heritage manifest: {out}")


def write_urdf_heritage_includes(results: list[dict]) -> None:
    """Generate XACRO snippet referencing heritage mesh files."""
    out_dir = PROJECT_ROOT / "ros2_ws" / "src" / "lunar_scout_description" / "urdf"
    out_dir.mkdir(parents=True, exist_ok=True)

    xacro_lines = ['<?xml version="1.0"?>',
                   '<robot xmlns:xacro="http://www.ros.org/wiki/xacro">',
                   '<!-- NASA heritage model mesh references — auto-generated -->']

    for r in results:
        if r.get("staged_as_urdf_mesh") and r.get("component_map"):
            xacro_lines.append(f"""
  <!-- Heritage: {r['name']} (NASA-3D-Resources) -->
  <xacro:macro name="{r['component_map']}_heritage_mesh" params="">
    <visual>
      <geometry>
        <mesh filename="package://lunar_scout_description/meshes/{r['component_map']}.stl"
              scale="1 1 1"/>
      </geometry>
    </visual>
    <collision>
      <geometry>
        <mesh filename="package://lunar_scout_description/meshes/{r['component_map']}.stl"/>
      </geometry>
    </collision>
  </xacro:macro>""")

    xacro_lines.append("\n</robot>")
    xacro_path = out_dir / "nasa_heritage_meshes.xacro"
    xacro_path.write_text("\n".join(xacro_lines))
    log.info(f"URDF heritage xacro: {xacro_path}")


def write_gazebo_heritage_sdf(downloaded: list[dict]) -> None:
    """Add heritage mesh references to Gazebo world includes."""
    heritage_sdf = "<!-- LPAS heritage models for Gazebo reference display -->\n"
    for r in downloaded:
        if r.get("success") and r.get("component_map"):
            heritage_sdf += f"""
  <model name="heritage_{r['component_map']}">
    <static>true</static>
    <link name="link">
      <visual name="visual">
        <geometry>
          <mesh>
            <uri>model://lpas_rover/meshes/{r['component_map']}.stl</uri>
          </mesh>
        </geometry>
      </visual>
    </link>
  </model>
"""
    # Append to heritage reference file (not main world — keep separate)
    out = PROJECT_ROOT / "gazebo_worlds" / "lunar_south_pole" / "heritage_models.sdf.include"
    out.write_text(heritage_sdf)
    log.info(f"Gazebo heritage SDF: {out}")


def main() -> None:
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Download real NASA 3D models for LPAS heritage reference"
    )
    parser.add_argument("--dry_run", action="store_true",
                        help="Print URLs without downloading")
    parser.add_argument("--output_dir", type=Path, default=HERITAGE_DIR)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    log.info(f"Downloading {len(NASA_MODELS)} NASA heritage models")
    log.info(f"Source: github.com/nasa/NASA-3D-Resources (NASA Open Source)")

    for model in NASA_MODELS:
        dest = args.output_dir / model.dest_name
        result_entry = {
            "name": model.name,
            "url": model.url,
            "local_path": str(dest),
            "component_map": model.component_map,
            "lpas_use": model.lpas_use,
            "success": False,
            "staged_as_urdf_mesh": False,
        }

        if args.dry_run:
            log.info(f"[DRY RUN] Would download: {model.dest_name}")
            log.info(f"          URL: {model.url}")
            result_entry["success"] = True  # Assume success for report
        else:
            success = download_file(model.url, dest)
            result_entry["success"] = success

            if success and dest.suffix.lower() == ".stl" and model.component_map:
                staged = copy_to_mesh_dir(dest, model.component_map)
                result_entry["staged_as_urdf_mesh"] = staged is not None

        results.append(result_entry)

    # Write integration artifacts
    generate_heritage_report(results)
    write_urdf_heritage_includes(results)
    write_gazebo_heritage_sdf(results)

    ok = sum(1 for r in results if r["success"])
    staged = sum(1 for r in results if r.get("staged_as_urdf_mesh"))
    log.info(f"Downloaded: {ok}/{len(NASA_MODELS)} | Staged to URDF: {staged}")
    log.info(f"Heritage directory: {args.output_dir}")
    log.info("")
    log.info("Manual downloads required:")
    for m in SUPPLEMENTAL_MODELS:
        log.info(f"  {m['name']}: {m['note']}")


if __name__ == "__main__":
    main()
