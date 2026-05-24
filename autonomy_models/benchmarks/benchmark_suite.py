"""
Comprehensive inference benchmark suite for all lunar rover autonomy models.

Loads ONNX-exported models and measures:
  - Latency: mean, P50, P95, P99 (ms) over N warmup + M timed runs
  - Throughput: effective FPS
  - Accuracy: mIoU (terrain seg), mAP@0.5 (hazard detection),
               MAE (slip prediction, energy prediction)

Tests on:
  - CPU (always)
  - CUDA (if available)
  - TensorRT (if onnxruntime-tensorrt provider available)

Outputs:
  benchmark_report.json  — machine-readable full results
  benchmark_report.md    — human-readable table summary

Usage:
    python benchmark_suite.py \
        --onnx_dir /autonomy_models/onnx_exports \
        --output_dir /autonomy_models/benchmarks \
        --warmup 50 \
        --runs 200
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False
    print("[WARN] onnxruntime not installed. Install with: pip install onnxruntime-gpu")


# ---------------------------------------------------------------------------
# Model input/output metadata
# ---------------------------------------------------------------------------

MODEL_SPECS: dict[str, dict[str, Any]] = {
    "terrain_segmentation": {
        "onnx_file": "terrain_segmentation.onnx",
        "input_shape": (1, 4, 480, 640),
        "dtype": np.float32,
        "target_latency_ms": 50.0,
        "target_fps": 20.0,
        "task": "segmentation",
        "num_classes": 8,
        "class_names": [
            "flat_regolith", "rocky_terrain", "crater_rim", "crater_interior",
            "boulder", "shadowed_psr", "sunlit_safe", "comms_shadow",
        ],
    },
    "hazard_detection": {
        "onnx_file": "hazard_detection.onnx",
        "input_shape": (1, 3, 640, 640),
        "dtype": np.float32,
        "target_latency_ms": 33.3,   # >30 FPS
        "target_fps": 30.0,
        "task": "detection",
        "num_classes": 4,
        "class_names": ["boulder", "deep_crater", "steep_slope_region", "comms_obstruction"],
    },
    "wheel_slip_prediction": {
        "onnx_file": "wheel_slip_prediction.onnx",
        "input_shape": (1, 10, 27),
        "dtype": np.float32,
        "target_latency_ms": 5.0,
        "target_fps": 200.0,
        "task": "regression",
        "output_keys": ["slip_ratio", "slip_log_var"],
    },
    "traversability": {
        "onnx_file": "traversability.onnx",
        "input_shape": (1, 4, 200, 200),
        "dtype": np.float32,
        "target_latency_ms": 10.0,
        "target_fps": 100.0,
        "task": "map_regression",
    },
    "energy_prediction": {
        "onnx_file": "energy_prediction.onnx",
        "input_shape": (1, 10),
        "dtype": np.float32,
        "target_latency_ms": 1.0,
        "target_fps": 1000.0,
        "task": "regression",
        "output_keys": ["energy_wh", "energy_log_var"],
    },
}


# ---------------------------------------------------------------------------
# OnnxRuntime session factory
# ---------------------------------------------------------------------------

def get_available_providers() -> list[str]:
    if not HAS_ORT:
        return []
    available = ort.get_available_providers()
    providers = []
    if "CPUExecutionProvider" in available:
        providers.append("CPUExecutionProvider")
    if "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")
    if "TensorrtExecutionProvider" in available:
        providers.append("TensorrtExecutionProvider")
    return providers


def create_session(onnx_path: Path, provider: str) -> Optional[Any]:
    if not HAS_ORT:
        return None
    try:
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.log_severity_level = 3  # suppress warnings

        provider_opts: list[tuple | str]
        if provider == "TensorrtExecutionProvider":
            provider_opts = [(provider, {
                "trt_fp16_enable": True,
                "trt_engine_cache_enable": True,
                "trt_engine_cache_path": str(onnx_path.parent / "trt_cache"),
            })]
        elif provider == "CUDAExecutionProvider":
            provider_opts = [(provider, {"device_id": 0})]
        else:
            provider_opts = [provider]

        return ort.InferenceSession(str(onnx_path), sess_options=opts, providers=provider_opts)
    except Exception as e:
        print(f"    Failed to create {provider} session: {e}")
        return None


# ---------------------------------------------------------------------------
# Latency benchmark
# ---------------------------------------------------------------------------

def benchmark_latency(
    session: Any,
    input_shape: tuple[int, ...],
    dtype: Any,
    warmup: int = 50,
    runs: int = 200,
) -> dict[str, float]:
    """
    Runs warmup + timed inference passes.
    Returns latency statistics in milliseconds.
    """
    input_name = session.get_inputs()[0].name
    data = np.random.randn(*input_shape).astype(dtype)

    # Warmup
    for _ in range(warmup):
        session.run(None, {input_name: data})

    # Timed runs
    latencies_ms = np.zeros(runs, dtype=np.float64)
    for i in range(runs):
        t0 = time.perf_counter()
        session.run(None, {input_name: data})
        latencies_ms[i] = (time.perf_counter() - t0) * 1000.0

    fps = 1000.0 / latencies_ms.mean()

    return {
        "mean_ms": float(latencies_ms.mean()),
        "std_ms": float(latencies_ms.std()),
        "min_ms": float(latencies_ms.min()),
        "max_ms": float(latencies_ms.max()),
        "p50_ms": float(np.percentile(latencies_ms, 50)),
        "p95_ms": float(np.percentile(latencies_ms, 95)),
        "p99_ms": float(np.percentile(latencies_ms, 99)),
        "fps": round(fps, 2),
    }


# ---------------------------------------------------------------------------
# Accuracy benchmarks (using synthetic ground truth)
# ---------------------------------------------------------------------------

def compute_miou(
    session: Any,
    input_shape: tuple[int, ...],
    num_classes: int,
    n_samples: int = 50,
) -> dict[str, float]:
    """
    Computes mIoU on synthetic data with known ground truth.
    For real evaluation, replace synthetic data with actual val set.
    """
    input_name = session.get_inputs()[0].name
    confusion = np.zeros((num_classes, num_classes), dtype=np.int64)

    rng = np.random.default_rng(0)
    B, C, H, W = input_shape

    for _ in range(n_samples):
        data = rng.standard_normal(input_shape).astype(np.float32)
        # Synthetic labels: smoothed random class map
        gt = rng.integers(0, num_classes, size=(H, W)).astype(np.int64)

        logits = session.run(None, {input_name: data})[0]   # (B, num_classes, H, W)
        pred = logits[0].argmax(0).astype(np.int64)         # (H, W)

        # Build confusion
        combined = gt.ravel() * num_classes + pred.ravel()
        counts = np.bincount(combined, minlength=num_classes ** 2)
        confusion += counts.reshape(num_classes, num_classes)

    tp = confusion.diagonal().astype(float)
    fn = confusion.sum(1).astype(float) - tp
    fp = confusion.sum(0).astype(float) - tp
    iou = tp / (tp + fn + fp + 1e-10)
    return {"mIoU": float(iou.mean()), "per_class_iou": iou.tolist()}


def compute_map50(
    session: Any,
    input_shape: tuple[int, ...],
    num_classes: int,
    n_samples: int = 50,
) -> dict[str, float]:
    """
    Approximates mAP@0.5 using synthetic detections and randomly generated
    ground truth boxes.  For real evaluation replace with actual val set.
    """
    input_name = session.get_inputs()[0].name
    rng = np.random.default_rng(0)

    all_precisions = []
    for _ in range(n_samples):
        data = rng.standard_normal(input_shape).astype(np.float32)
        outputs = session.run(None, {input_name: data})

        # Decode first-scale classification output (logits)
        # outputs[0] is scale_8_cls: (B, num_classes, H, W)
        cls_map = outputs[0][0]  # (num_classes, H, W)
        scores = 1.0 / (1.0 + np.exp(-cls_map))  # sigmoid
        max_scores = scores.max(0).ravel()  # (H*W,)

        # Treat each spatial position as a detection candidate
        conf_thresh = 0.25
        positive_preds = (max_scores > conf_thresh).sum()
        total_preds = len(max_scores)

        # Synthetic GT: random fraction of grid cells are positive
        gt_positive = int(total_preds * rng.uniform(0.01, 0.05))

        if positive_preds > 0:
            # Precision approximation
            precision = min(1.0, gt_positive / (positive_preds + 1e-8))
        else:
            precision = 0.0
        all_precisions.append(precision)

    map50 = float(np.mean(all_precisions))
    return {"mAP50": map50}


def compute_mae_regression(
    session: Any,
    input_shape: tuple[int, ...],
    n_samples: int = 200,
) -> dict[str, float]:
    """
    Computes MAE on synthetic regression targets.
    Replace with real held-out data for deployment metrics.
    """
    input_name = session.get_inputs()[0].name
    rng = np.random.default_rng(0)

    all_preds, all_gts = [], []
    for _ in range(n_samples):
        data = rng.standard_normal(input_shape).astype(np.float32)
        output = session.run(None, {input_name: data})[0]   # first output
        all_preds.append(output.ravel())

        # Synthetic GT drawn from same distribution as output
        gt = rng.standard_normal(output.shape).astype(np.float32)
        all_gts.append(gt.ravel())

    all_preds_np = np.concatenate(all_preds)
    all_gts_np = np.concatenate(all_gts)
    mae = float(np.abs(all_preds_np - all_gts_np).mean())
    return {"MAE": mae}


# ---------------------------------------------------------------------------
# Per-model accuracy dispatch
# ---------------------------------------------------------------------------

def run_accuracy_benchmark(
    session: Any,
    model_name: str,
    spec: dict,
) -> dict[str, float]:
    task = spec.get("task", "regression")
    shape = spec["input_shape"]
    nc = spec.get("num_classes", 1)

    try:
        if task == "segmentation":
            return compute_miou(session, shape, nc, n_samples=20)
        elif task == "detection":
            return compute_map50(session, shape, nc, n_samples=20)
        elif task in ("regression", "map_regression"):
            return compute_mae_regression(session, shape, n_samples=100)
        else:
            return {}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# ONNX model size
# ---------------------------------------------------------------------------

def get_onnx_info(onnx_path: Path) -> dict[str, Any]:
    size_mb = onnx_path.stat().st_size / (1024 ** 2)
    info: dict[str, Any] = {"size_mb": round(size_mb, 3)}

    try:
        import onnx
        model = onnx.load(str(onnx_path))
        info["opset"] = model.opset_import[0].version
        info["nodes"] = len(model.graph.node)
        info["inputs"] = [
            {"name": i.name, "shape": [d.dim_value for d in i.type.tensor_type.shape.dim]}
            for i in model.graph.input
        ]
    except ImportError:
        pass
    except Exception as e:
        info["onnx_parse_error"] = str(e)

    return info


# ---------------------------------------------------------------------------
# Main benchmark loop
# ---------------------------------------------------------------------------

def run_benchmarks(args: argparse.Namespace) -> None:
    onnx_dir = Path(args.onnx_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    available_providers = get_available_providers()
    print(f"Available ORT providers: {available_providers}")

    providers_to_test = ["CPUExecutionProvider"]
    if "CUDAExecutionProvider" in available_providers:
        providers_to_test.append("CUDAExecutionProvider")
    if "TensorrtExecutionProvider" in available_providers and not args.skip_trt:
        providers_to_test.append("TensorrtExecutionProvider")

    full_results: dict[str, Any] = {
        "metadata": {
            "date": __import__("datetime").datetime.utcnow().isoformat(),
            "warmup_runs": args.warmup,
            "timed_runs": args.runs,
            "providers_tested": providers_to_test,
            "onnx_dir": str(onnx_dir),
        },
        "models": {},
    }

    for model_name, spec in MODEL_SPECS.items():
        onnx_path = onnx_dir / spec["onnx_file"]
        print(f"\n{'='*65}")
        print(f"Model: {model_name}")

        model_result: dict[str, Any] = {
            "onnx_path": str(onnx_path),
            "onnx_exists": onnx_path.exists(),
            "spec": {k: v for k, v in spec.items() if k not in ("dtype",)},
            "benchmarks": {},
            "accuracy": {},
        }

        if not onnx_path.exists():
            print(f"  [SKIP] ONNX not found: {onnx_path}")
            full_results["models"][model_name] = model_result
            continue

        model_result["onnx_info"] = get_onnx_info(onnx_path)
        print(f"  ONNX size: {model_result['onnx_info']['size_mb']:.2f} MB")

        for provider in providers_to_test:
            print(f"  Provider: {provider}")
            session = create_session(onnx_path, provider)
            if session is None:
                model_result["benchmarks"][provider] = {"error": "session_creation_failed"}
                continue

            lat = benchmark_latency(
                session,
                spec["input_shape"],
                spec["dtype"],
                warmup=args.warmup,
                runs=args.runs,
            )
            model_result["benchmarks"][provider] = lat

            meets_latency = lat["p95_ms"] <= spec["target_latency_ms"]
            meets_fps = lat["fps"] >= spec["target_fps"]
            status = "PASS" if (meets_latency and meets_fps) else "FAIL"

            print(
                f"    mean={lat['mean_ms']:.2f}ms  p95={lat['p95_ms']:.2f}ms  "
                f"fps={lat['fps']:.1f}  target={spec['target_latency_ms']:.0f}ms "
                f"[{status}]"
            )

        # Accuracy benchmark on CPU
        if HAS_ORT and onnx_path.exists():
            cpu_session = create_session(onnx_path, "CPUExecutionProvider")
            if cpu_session is not None:
                print(f"  Accuracy (CPU, synthetic data):")
                acc = run_accuracy_benchmark(cpu_session, model_name, spec)
                model_result["accuracy"] = acc
                for k, v in acc.items():
                    if k != "per_class_iou":
                        print(f"    {k}: {v:.4f}")

        full_results["models"][model_name] = model_result

    # Save JSON report
    json_path = output_dir / "benchmark_report.json"
    with open(json_path, "w") as f:
        json.dump(full_results, f, indent=2)
    print(f"\nJSON report saved to: {json_path}")

    # Generate Markdown report
    md_path = output_dir / "benchmark_report.md"
    write_markdown_report(full_results, md_path, providers_to_test)
    print(f"Markdown report saved to: {md_path}")


# ---------------------------------------------------------------------------
# Markdown report generator
# ---------------------------------------------------------------------------

def write_markdown_report(
    results: dict[str, Any],
    out_path: Path,
    providers: list[str],
) -> None:
    meta = results["metadata"]
    lines: list[str] = []

    lines.append("# Lunar Rover Autonomy Models — Benchmark Report\n")
    lines.append(f"**Date:** {meta['date']}  ")
    lines.append(f"**Warmup runs:** {meta['warmup_runs']}  ")
    lines.append(f"**Timed runs:** {meta['timed_runs']}  \n")

    # --- Latency table ---
    lines.append("## Inference Latency\n")

    # Build header dynamically
    provider_headers = "  ".join(
        f"| {p.replace('ExecutionProvider','').replace('CPU','CPU').replace('CUDA','CUDA').replace('Tensorrt','TRT')} mean (ms) | P95 (ms) | FPS | Target |"
        for p in providers
    )
    header = f"| Model | Size (MB) {provider_headers}"
    lines.append(header)
    sep = "|---|---|" + "|---|---|---|---|" * len(providers)
    lines.append(sep)

    for model_name, mdata in results["models"].items():
        if not mdata["onnx_exists"]:
            lines.append(f"| {model_name} | N/A | *ONNX not found* |")
            continue

        size_mb = mdata.get("onnx_info", {}).get("size_mb", "—")
        spec = mdata["spec"]
        row = f"| {model_name} | {size_mb} "
        for p in providers:
            bench = mdata["benchmarks"].get(p, {})
            if "error" in bench:
                row += f"| — | — | — | — |"
            elif bench:
                mean_ms = bench.get("mean_ms", 0)
                p95_ms = bench.get("p95_ms", 0)
                fps = bench.get("fps", 0)
                target = spec.get("target_latency_ms", "—")
                meets = "✓" if p95_ms <= float(target) else "✗"
                row += f"| {mean_ms:.2f} | {p95_ms:.2f} | {fps:.1f} | {target} {meets} |"
            else:
                row += f"| — | — | — | — |"
        lines.append(row)

    lines.append("")

    # --- Accuracy table ---
    lines.append("## Model Accuracy (Synthetic Validation Data)\n")
    lines.append("> **Note:** Accuracy computed on synthetic data. Replace with real validation set for deployment metrics.\n")
    lines.append("| Model | Task | Metric | Value |")
    lines.append("|---|---|---|---|")

    for model_name, mdata in results["models"].items():
        acc = mdata.get("accuracy", {})
        task = mdata.get("spec", {}).get("task", "—")
        if not acc:
            lines.append(f"| {model_name} | {task} | — | N/A |")
            continue
        for metric, value in acc.items():
            if metric == "per_class_iou":
                continue
            if isinstance(value, float):
                lines.append(f"| {model_name} | {task} | {metric} | {value:.4f} |")

    lines.append("")

    # --- Per-class IoU for segmentation ---
    seg_data = results["models"].get("terrain_segmentation", {})
    per_class = seg_data.get("accuracy", {}).get("per_class_iou")
    if per_class:
        lines.append("## Terrain Segmentation — Per-class IoU\n")
        class_names = seg_data["spec"].get("class_names", [str(i) for i in range(len(per_class))])
        lines.append("| Class | IoU |")
        lines.append("|---|---|")
        for name, iou in zip(class_names, per_class):
            lines.append(f"| {name} | {iou:.4f} |")
        lines.append("")

    # --- Model sizes ---
    lines.append("## Model Parameter Counts\n")
    lines.append("| Model | ONNX Nodes | ONNX Size (MB) |")
    lines.append("|---|---|---|")
    for model_name, mdata in results["models"].items():
        info = mdata.get("onnx_info", {})
        nodes = info.get("nodes", "—")
        size = info.get("size_mb", "—")
        lines.append(f"| {model_name} | {nodes} | {size} |")

    lines.append("")
    lines.append("---")
    lines.append("*Generated by benchmark_suite.py — NASA Lunar Rover Autonomy Stack*")

    with open(out_path, "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark all lunar rover autonomy models")
    p.add_argument(
        "--onnx_dir",
        "--models_dir",
        dest="onnx_dir",
        type=str,
        default="../onnx_exports",
        help="Directory containing exported ONNX models",
    )
    p.add_argument("--output_dir", type=str, default=".",
                   help="Directory to write benchmark reports")
    p.add_argument("--warmup", type=int, default=50,
                   help="Number of warmup inference passes")
    p.add_argument("--runs", type=int, default=200,
                   help="Number of timed inference passes per model per provider")
    p.add_argument("--skip_trt", action="store_true",
                   help="Skip TensorRT provider even if available")
    return p.parse_args()


if __name__ == "__main__":
    run_benchmarks(parse_args())
