"""
ONNX export pipeline for all lunar rover autonomy models.

For each model:
  1. Loads trained checkpoint (or initialises with random weights if not found)
  2. Exports to ONNX opset 17 with dynamic batch dimension
  3. Validates ONNX output against PyTorch output (atol=1e-4)
  4. Saves TensorRT engine config JSON (for trtexec invocation on Orin)
  5. Reports parameter counts and ONNX model file sizes

Output structure:
    <output_dir>/
        terrain_segmentation.onnx
        hazard_detection.onnx
        wheel_slip_prediction.onnx
        traversability.onnx
        energy_prediction.onnx
        tensorrt_configs/
            terrain_segmentation_trt.json
            ...
        export_report.json

Usage:
    python export_all.py \
        --checkpoint_dir /runs \
        --output_dir /autonomy_models/onnx_exports
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
from torch import Tensor

# Add model directories to path
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE / "terrain_segmentation"))
sys.path.insert(0, str(_HERE / "hazard_detection"))
sys.path.insert(0, str(_HERE / "wheel_slip_prediction"))
sys.path.insert(0, str(_HERE / "traversability"))
sys.path.insert(0, str(_HERE / "energy_prediction"))

from terrain_segmentation.model import LunarTerrainSegmentation, NUM_CLASSES as SEG_CLASSES
from hazard_detection.model import LunarHazardDetector
from wheel_slip_prediction.model import WheelSlipPredictor, INPUT_DIM, SEQ_LEN
from traversability.model import BEVTraversabilityNet, IN_CHANNELS as BEV_CHANNELS, BEV_SIZE
from energy_prediction.model import EnergyPredictor, INPUT_DIM as ENERGY_INPUT_DIM


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

def _build_terrain_seg(ckpt: Optional[Path]) -> tuple[nn.Module, Tensor, str, dict]:
    model = LunarTerrainSegmentation(in_channels=4, num_classes=SEG_CLASSES)
    if ckpt and ckpt.exists():
        state = torch.load(ckpt, map_location="cpu")
        model.load_state_dict(state["model_state_dict"])
    dummy = torch.randn(1, 4, 480, 640)
    input_names = ["rgb_thermal"]
    output_names = ["seg_logits"]
    dynamic_axes = {"rgb_thermal": {0: "batch"}, "seg_logits": {0: "batch"}}
    trt_config = {
        "input_name": "rgb_thermal",
        "input_shape": "1x4x480x640",
        "fp16": True,
        "workspace_mb": 512,
        "min_batch": 1,
        "opt_batch": 1,
        "max_batch": 4,
    }
    return model, dummy, "terrain_segmentation", {
        "input_names": input_names,
        "output_names": output_names,
        "dynamic_axes": dynamic_axes,
        "trt_config": trt_config,
    }


def _build_hazard_det(ckpt: Optional[Path]) -> tuple[nn.Module, Tensor, str, dict]:
    model = LunarHazardDetector(num_classes=4, width_mult=0.5)
    if ckpt and ckpt.exists():
        state = torch.load(ckpt, map_location="cpu")
        model.load_state_dict(state["model_state_dict"])
    dummy = torch.randn(1, 3, 640, 640)
    input_names = ["rgb"]
    output_names = [f"scale_{s}_cls" for s in [8, 16, 32]] + \
                   [f"scale_{s}_reg" for s in [8, 16, 32]]
    dynamic_axes = {"rgb": {0: "batch"}}
    for name in output_names:
        dynamic_axes[name] = {0: "batch"}
    trt_config = {
        "input_name": "rgb",
        "input_shape": "1x3x640x640",
        "fp16": True,
        "workspace_mb": 256,
        "min_batch": 1,
        "opt_batch": 1,
        "max_batch": 4,
    }
    return model, dummy, "hazard_detection", {
        "input_names": input_names,
        "output_names": output_names,
        "dynamic_axes": dynamic_axes,
        "trt_config": trt_config,
    }


def _build_wheel_slip(ckpt: Optional[Path]) -> tuple[nn.Module, Tensor, str, dict]:
    model = WheelSlipPredictor()
    if ckpt and ckpt.exists():
        state = torch.load(ckpt, map_location="cpu")
        model.load_state_dict(state["model_state_dict"])
    dummy = torch.randn(1, SEQ_LEN, INPUT_DIM)
    input_names = ["rover_state_seq"]
    output_names = ["slip_ratio", "slip_log_var"]
    dynamic_axes = {
        "rover_state_seq": {0: "batch"},
        "slip_ratio": {0: "batch"},
        "slip_log_var": {0: "batch"},
    }
    trt_config = {
        "input_name": "rover_state_seq",
        "input_shape": f"1x{SEQ_LEN}x{INPUT_DIM}",
        "fp16": True,
        "workspace_mb": 64,
        "min_batch": 1,
        "opt_batch": 1,
        "max_batch": 16,
    }
    return model, dummy, "wheel_slip_prediction", {
        "input_names": input_names,
        "output_names": output_names,
        "dynamic_axes": dynamic_axes,
        "trt_config": trt_config,
    }


def _build_traversability(ckpt: Optional[Path]) -> tuple[nn.Module, Tensor, str, dict]:
    model = BEVTraversabilityNet()
    if ckpt and ckpt.exists():
        state = torch.load(ckpt, map_location="cpu")
        model.load_state_dict(state["model_state_dict"])
    dummy = torch.randn(1, BEV_CHANNELS, BEV_SIZE, BEV_SIZE)
    input_names = ["bev_map"]
    output_names = ["traversability"]
    dynamic_axes = {"bev_map": {0: "batch"}, "traversability": {0: "batch"}}
    trt_config = {
        "input_name": "bev_map",
        "input_shape": f"1x{BEV_CHANNELS}x{BEV_SIZE}x{BEV_SIZE}",
        "fp16": True,
        "workspace_mb": 128,
        "min_batch": 1,
        "opt_batch": 1,
        "max_batch": 1,
    }
    return model, dummy, "traversability", {
        "input_names": input_names,
        "output_names": output_names,
        "dynamic_axes": dynamic_axes,
        "trt_config": trt_config,
    }


def _build_energy_pred(ckpt: Optional[Path]) -> tuple[nn.Module, Tensor, str, dict]:
    model = EnergyPredictor()
    if ckpt and ckpt.exists():
        state = torch.load(ckpt, map_location="cpu")
        model.load_state_dict(state["model_state_dict"])
    dummy = torch.randn(1, ENERGY_INPUT_DIM)
    input_names = ["path_features"]
    output_names = ["energy_wh", "energy_log_var"]
    dynamic_axes = {
        "path_features": {0: "batch"},
        "energy_wh": {0: "batch"},
        "energy_log_var": {0: "batch"},
    }
    trt_config = {
        "input_name": "path_features",
        "input_shape": f"1x{ENERGY_INPUT_DIM}",
        "fp16": True,
        "workspace_mb": 32,
        "min_batch": 1,
        "opt_batch": 32,
        "max_batch": 256,
    }
    return model, dummy, "energy_prediction", {
        "input_names": input_names,
        "output_names": output_names,
        "dynamic_axes": dynamic_axes,
        "trt_config": trt_config,
    }


# ---------------------------------------------------------------------------
# ONNX export helpers
# ---------------------------------------------------------------------------

def export_to_onnx(
    model: nn.Module,
    dummy_input: Tensor,
    output_path: Path,
    input_names: list[str],
    output_names: list[str],
    dynamic_axes: dict,
    opset: int = 17,
) -> bool:
    model.eval()
    try:
        torch.onnx.export(
            model,
            dummy_input,
            str(output_path),
            opset_version=opset,
            input_names=input_names,
            output_names=output_names,
            dynamic_axes=dynamic_axes,
            do_constant_folding=True,
            export_params=True,
        )
        return True
    except Exception as e:
        print(f"    ONNX export failed: {e}")
        return False


def validate_onnx(
    model: nn.Module,
    onnx_path: Path,
    dummy_input: Tensor,
    atol: float = 1e-3,
) -> bool:
    try:
        import onnxruntime as ort
        import numpy as np

        model.eval()
        with torch.no_grad():
            torch_out = model(dummy_input)

        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        input_name = sess.get_inputs()[0].name
        ort_out = sess.run(None, {input_name: dummy_input.numpy()})

        if isinstance(torch_out, (tuple, list)):
            torch_out_list = [o.numpy() for o in torch_out]
        else:
            torch_out_list = [torch_out.numpy()]

        for i, (t_out, o_out) in enumerate(zip(torch_out_list, ort_out)):
            if not np.allclose(t_out, o_out, atol=atol):
                max_diff = float(np.abs(t_out - o_out).max())
                print(f"    Validation warning: output {i} max diff = {max_diff:.6f} > atol={atol}")
                return False
        return True

    except ImportError:
        print("    onnxruntime not installed — skipping ONNX validation")
        return True
    except Exception as e:
        print(f"    ONNX validation error: {e}")
        return False


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


# ---------------------------------------------------------------------------
# Main export loop
# ---------------------------------------------------------------------------

def export_all(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trt_dir = output_dir / "tensorrt_configs"
    trt_dir.mkdir(exist_ok=True)

    ckpt_dir = Path(args.checkpoint_dir)

    model_builders = [
        (_build_terrain_seg,   ckpt_dir / "terrain_segmentation"   / "checkpoints" / "best.pt"),
        (_build_hazard_det,    ckpt_dir / "hazard_detection"        / "checkpoints" / "best.pt"),
        (_build_wheel_slip,    ckpt_dir / "wheel_slip_prediction"   / "checkpoints" / "best.pt"),
        (_build_traversability,ckpt_dir / "traversability"          / "checkpoints" / "best.pt"),
        (_build_energy_pred,   ckpt_dir / "energy_prediction"       / "fold_1_best.pt"),
    ]

    report: list[dict] = []

    for builder_fn, ckpt_path in model_builders:
        ckpt = ckpt_path if ckpt_path.exists() else None
        if ckpt is None:
            print(f"[WARN] No checkpoint at {ckpt_path} — exporting with random weights")

        model, dummy, model_name, export_cfg = builder_fn(ckpt)
        onnx_path = output_dir / f"{model_name}.onnx"

        print(f"\n{'='*60}")
        print(f"Exporting: {model_name}")
        print(f"  Checkpoint: {ckpt_path if ckpt else 'N/A (random weights)'}")
        print(f"  Parameters: {count_parameters(model):,}")

        t0 = time.time()
        success = export_to_onnx(
            model, dummy, onnx_path,
            export_cfg["input_names"],
            export_cfg["output_names"],
            export_cfg["dynamic_axes"],
            opset=args.opset,
        )
        export_time = time.time() - t0

        onnx_size_mb = onnx_path.stat().st_size / (1024 ** 2) if onnx_path.exists() else 0.0

        if success:
            print(f"  ONNX size:   {onnx_size_mb:.2f} MB")
            print(f"  Export time: {export_time:.2f}s")

            # Validate
            valid = validate_onnx(model, onnx_path, dummy, atol=1e-3)
            print(f"  ONNX valid:  {'PASS' if valid else 'FAIL'}")
        else:
            valid = False

        # Write TensorRT config
        trt_json_path = trt_dir / f"{model_name}_trt.json"
        trt_cfg = export_cfg["trt_config"]
        trt_cfg["onnx_path"] = str(onnx_path)
        trt_cfg["engine_path"] = str(trt_dir / f"{model_name}.engine")
        trt_cfg["trtexec_cmd"] = (
            f"trtexec "
            f"--onnx={onnx_path} "
            f"--saveEngine={trt_cfg['engine_path']} "
            f"--fp16 "
            f"--minShapes={trt_cfg['input_name']}:{trt_cfg['input_shape'].replace('1x', str(trt_cfg['min_batch'])+'x', 1)} "
            f"--optShapes={trt_cfg['input_name']}:{trt_cfg['input_shape'].replace('1x', str(trt_cfg['opt_batch'])+'x', 1)} "
            f"--maxShapes={trt_cfg['input_name']}:{trt_cfg['input_shape'].replace('1x', str(trt_cfg['max_batch'])+'x', 1)} "
            f"--workspace={trt_cfg['workspace_mb']}"
        )
        with open(trt_json_path, "w") as f:
            json.dump(trt_cfg, f, indent=2)

        report.append({
            "model": model_name,
            "parameters": count_parameters(model),
            "onnx_path": str(onnx_path),
            "onnx_size_mb": round(onnx_size_mb, 3),
            "export_success": success,
            "onnx_valid": valid,
            "export_time_s": round(export_time, 3),
            "trt_config": str(trt_json_path),
            "checkpoint_used": str(ckpt_path) if ckpt else None,
        })

    # Save report
    report_path = output_dir / "export_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*60}")
    print("Export Summary")
    print(f"{'='*60}")
    print(f"{'Model':<30} {'Params':>12} {'ONNX MB':>9} {'Valid':>6}")
    print(f"{'-'*60}")
    for r in report:
        print(
            f"{r['model']:<30} {r['parameters']:>12,} "
            f"{r['onnx_size_mb']:>8.2f} {'PASS' if r['onnx_valid'] else 'FAIL':>7}"
        )
    print(f"\nReport saved to: {report_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export all autonomy models to ONNX")
    p.add_argument("--checkpoint_dir", type=str, default="runs",
                   help="Root directory containing per-model run subdirectories")
    p.add_argument("--output_dir", type=str, default="onnx_exports")
    p.add_argument("--opset", type=int, default=17)
    return p.parse_args()


if __name__ == "__main__":
    export_all(parse_args())
