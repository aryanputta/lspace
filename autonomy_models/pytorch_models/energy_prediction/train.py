"""
Training script for EnergyPredictor.

Loads simulation telemetry, normalises features, runs k-fold cross-validation,
and reports per-fold and aggregate metrics. Optionally computes SHAP feature
importance on the best fold model.

Usage:
    python train.py \
        --data_dir /data/energy_telemetry \
        --output_dir /runs/energy_pred \
        --epochs 100 \
        --batch_size 256 \
        --lr 1e-3 \
        --folds 5
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from torch.optim import AdamW
from torch.optim.lr_scheduler import OneCycleLR
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset, Subset
from torch.utils.tensorboard import SummaryWriter

from model import EnergyPredictor, INPUT_DIM, FeatureNormaliser


# Feature names for SHAP reporting
FEATURE_NAMES = [
    "path_distance",
    "terrain_roughness",
    "average_slope_deg",
    "payload_active",
    "battery_temp_c",
    "solar_irradiance",
    "average_speed",
    "wheel_slip_estimate",
    "comms_overhead",
    "elevation_change",
]


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class EnergyTelemetryDataset(Dataset):
    """
    Loads pre-extracted telemetry features from a NumPy archive.

    The archive should contain:
        X     : (N, INPUT_DIM)  feature vectors
        y     : (N,)            energy consumed (Wh)

    If the archive is not found, SyntheticEnergyDataset is used instead.
    """

    def __init__(self, npz_path: Path) -> None:
        data = np.load(str(npz_path), allow_pickle=False)
        self.X = torch.from_numpy(data["X"].astype(np.float32))
        self.y = torch.from_numpy(data["y"].astype(np.float32))

        assert self.X.shape[1] == INPUT_DIM, \
            f"Expected {INPUT_DIM} features, got {self.X.shape[1]}"

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int) -> tuple[Tensor, Tensor]:
        return self.X[idx], self.y[idx]


class SyntheticEnergyDataset(Dataset):
    """Physically plausible synthetic energy data for development and CI."""

    def __init__(self, n_samples: int = 20000, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)

        # Feature sampling (physically motivated ranges)
        dist = rng.uniform(5, 200, n_samples)                # path distance m
        roughness = rng.beta(1.5, 3.0, n_samples)            # 0-1
        slope = rng.normal(5.0, 8.0, n_samples).clip(-20, 20)  # degrees
        payload = rng.choice([0.0, 1.0], n_samples, p=[0.4, 0.6])
        batt_temp = rng.uniform(-40, 60, n_samples)          # Celsius
        solar = rng.uniform(0, 1370, n_samples)              # W/m²
        speed = rng.uniform(0.01, 0.1, n_samples)            # m/s
        slip = rng.beta(1.5, 5.0, n_samples)                 # 0-1
        comms = rng.choice([0.0, 1.0], n_samples, p=[0.6, 0.4])
        elev_change = dist * np.tan(np.radians(slope))

        X = np.stack(
            [dist, roughness, slope, payload, batt_temp, solar, speed, slip, comms, elev_change],
            axis=1,
        ).astype(np.float32)

        # Simplified energy model (Wh):
        #   propulsion: proportional to dist, slope penalty, roughness, slip
        #   thermal:    negative battery temp → heater load
        #   payload:    fixed overhead when active
        prop = dist * (0.002 + 0.0003 * roughness + 0.0001 * np.abs(slope))
        slope_gravity = dist * 0.001 * slope / 100.0    # uphill costs more
        slip_penalty = prop * slip * 0.4
        thermal = np.where(batt_temp < 0, -batt_temp * 0.05, 0)
        payload_cost = payload * 0.5 * dist / speed / 3600
        noise = rng.normal(0, 0.05, n_samples)

        y = (prop + slope_gravity + slip_penalty + thermal + payload_cost + noise).clip(0.1).astype(np.float32)

        self.X = torch.from_numpy(X)
        self.y = torch.from_numpy(y)

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int) -> tuple[Tensor, Tensor]:
        return self.X[idx], self.y[idx]


# ---------------------------------------------------------------------------
# Feature normalisation pipeline
# ---------------------------------------------------------------------------

def fit_normalisation(
    X: Tensor, model: EnergyPredictor
) -> tuple[Tensor, Tensor]:
    """Computes per-feature mean and std and initialises the model normaliser."""
    mean = X.mean(0)
    std = X.std(0).clamp(min=1e-6)
    model.normaliser.initialise_from_stats(mean, std)
    return mean, std


# ---------------------------------------------------------------------------
# Loss
# ---------------------------------------------------------------------------

class EnergyLoss(nn.Module):
    """
    NLL loss with heteroscedastic uncertainty + MAE regularisation.

    NLL = 0.5 * (log_var + (pred - gt)^2 / exp(log_var))
    Total = NLL + lambda_mae * MAE
    """

    def __init__(self, lambda_mae: float = 0.5) -> None:
        super().__init__()
        self.lambda_mae = lambda_mae

    def forward(
        self, energy_pred: Tensor, log_var: Tensor, energy_gt: Tensor
    ) -> tuple[Tensor, dict[str, float]]:
        # NLL
        nll = 0.5 * (log_var + (energy_pred - energy_gt) ** 2 / (log_var.exp() + 1e-8))
        nll_loss = nll.mean()

        # MAE
        mae_loss = (energy_pred - energy_gt).abs().mean()

        total = nll_loss + self.lambda_mae * mae_loss
        return total, {
            "nll": float(nll_loss.item()),
            "mae": float(mae_loss.item()),
        }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_regression_metrics(pred: Tensor, gt: Tensor) -> dict[str, float]:
    mae = float((pred - gt).abs().mean().item())
    rmse = float(((pred - gt) ** 2).mean().sqrt().item())
    # Mean absolute percentage error
    mape = float(((pred - gt).abs() / (gt.abs() + 1e-8)).mean().item() * 100)
    # R²
    ss_res = float(((pred - gt) ** 2).sum().item())
    ss_tot = float(((gt - gt.mean()) ** 2).sum().item())
    r2 = 1.0 - ss_res / (ss_tot + 1e-8)
    return {"mae_wh": mae, "rmse_wh": rmse, "mape_pct": mape, "r2": r2}


# ---------------------------------------------------------------------------
# Train / validate
# ---------------------------------------------------------------------------

def train_one_epoch(
    model: EnergyPredictor,
    loader: DataLoader,
    optimizer: AdamW,
    scheduler: OneCycleLR,
    criterion: EnergyLoss,
    scaler: GradScaler,
    device: torch.device,
) -> dict[str, float]:
    model.train()
    total_loss = 0.0
    preds_all, gts_all = [], []

    for X_batch, y_batch in loader:
        X_batch = X_batch.to(device, non_blocking=True)
        y_batch = y_batch.to(device, non_blocking=True)

        with autocast():
            energy_pred, log_var = model(X_batch)
            loss, _ = criterion(energy_pred, log_var, y_batch)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)
        scheduler.step()

        total_loss += loss.item()
        preds_all.append(energy_pred.detach().cpu())
        gts_all.append(y_batch.cpu())

    preds = torch.cat(preds_all)
    gts = torch.cat(gts_all)
    metrics = compute_regression_metrics(preds, gts)
    metrics["loss"] = total_loss / len(loader)
    return metrics


@torch.no_grad()
def validate_epoch(
    model: EnergyPredictor,
    loader: DataLoader,
    criterion: EnergyLoss,
    device: torch.device,
) -> dict[str, float]:
    model.eval()
    total_loss = 0.0
    preds_all, gts_all = [], []

    for X_batch, y_batch in loader:
        X_batch = X_batch.to(device, non_blocking=True)
        y_batch = y_batch.to(device, non_blocking=True)

        with autocast():
            energy_pred, log_var = model(X_batch)
            loss, _ = criterion(energy_pred, log_var, y_batch)

        total_loss += loss.item()
        preds_all.append(energy_pred.cpu())
        gts_all.append(y_batch.cpu())

    preds = torch.cat(preds_all)
    gts = torch.cat(gts_all)
    metrics = compute_regression_metrics(preds, gts)
    metrics["loss"] = total_loss / len(loader)
    return metrics


# ---------------------------------------------------------------------------
# SHAP feature importance
# ---------------------------------------------------------------------------

def compute_shap_importance(
    model: EnergyPredictor,
    X: Tensor,
    device: torch.device,
    n_background: int = 100,
    n_explain: int = 200,
) -> dict[str, float]:
    """
    Kernel SHAP approximation (permutation-based) for feature importance.
    Does not require the shap library — uses a simple permutation method.
    Requires: pip install shap (optional; falls back to permutation importance).
    """
    try:
        import shap

        model.eval()
        model.to(device)

        def model_fn(x_np: np.ndarray) -> np.ndarray:
            x_t = torch.from_numpy(x_np.astype(np.float32)).to(device)
            with torch.no_grad():
                energy, _ = model(x_t)
            return energy.cpu().numpy()

        background = X[:n_background].numpy()
        explain_data = X[n_background: n_background + n_explain].numpy()

        explainer = shap.KernelExplainer(model_fn, background)
        shap_values = explainer.shap_values(explain_data, nsamples=50)
        importance = np.abs(shap_values).mean(0)
        return {FEATURE_NAMES[i]: float(importance[i]) for i in range(len(FEATURE_NAMES))}

    except ImportError:
        # Permutation importance fallback
        model.eval()
        model.to(device)
        X_eval = X[:n_explain].to(device)
        with torch.no_grad():
            base_energy, _ = model(X_eval)

        importances: dict[str, float] = {}
        for feat_idx, feat_name in enumerate(FEATURE_NAMES):
            X_perm = X_eval.clone()
            perm = torch.randperm(X_eval.shape[0])
            X_perm[:, feat_idx] = X_eval[perm, feat_idx]
            with torch.no_grad():
                perm_energy, _ = model(X_perm)
            importance = float((perm_energy - base_energy).abs().mean().item())
            importances[feat_name] = importance

        return importances


# ---------------------------------------------------------------------------
# K-fold cross-validation
# ---------------------------------------------------------------------------

def kfold_train(args: argparse.Namespace) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    writer = SummaryWriter(log_dir=str(output_dir / "tensorboard"))

    # Data
    npz_path = Path(args.data_dir) / "energy_telemetry.npz"
    if npz_path.exists():
        dataset = EnergyTelemetryDataset(npz_path)
        print(f"Loaded {len(dataset)} real samples from {npz_path}")
    else:
        print("No telemetry archive found — using synthetic data.")
        dataset = SyntheticEnergyDataset(n_samples=args.synthetic_samples)

    n_total = len(dataset)
    fold_size = n_total // args.folds
    all_X = torch.stack([dataset[i][0] for i in range(n_total)])
    all_y = torch.stack([dataset[i][1] for i in range(n_total)])

    fold_results: list[dict[str, float]] = []
    best_fold_mae = float("inf")
    best_fold_idx = -1

    for fold in range(args.folds):
        print(f"\n{'='*60}")
        print(f"Fold {fold + 1}/{args.folds}")

        val_start = fold * fold_size
        val_end = val_start + fold_size
        val_indices = list(range(val_start, val_end))
        train_indices = list(range(0, val_start)) + list(range(val_end, n_total))

        train_ds = Subset(dataset, train_indices)
        val_ds = Subset(dataset, val_indices)

        train_loader = DataLoader(
            train_ds, batch_size=args.batch_size, shuffle=True,
            num_workers=args.num_workers, pin_memory=(device.type == "cuda"), drop_last=True,
        )
        val_loader = DataLoader(
            val_ds, batch_size=args.batch_size * 4, shuffle=False,
            num_workers=args.num_workers, pin_memory=(device.type == "cuda"),
        )

        model = EnergyPredictor().to(device)

        # Fit normalisation from training split only
        train_X = all_X[train_indices]
        fit_normalisation(train_X, model)

        criterion = EnergyLoss(lambda_mae=args.lambda_mae)
        optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=1e-5)
        scaler = GradScaler()
        scheduler = OneCycleLR(
            optimizer,
            max_lr=args.lr,
            steps_per_epoch=len(train_loader),
            epochs=args.epochs,
        )

        best_val_mae = float("inf")
        patience_counter = 0

        for epoch in range(args.epochs):
            train_m = train_one_epoch(
                model, train_loader, optimizer, scheduler, criterion, scaler, device
            )
            val_m = validate_epoch(model, val_loader, criterion, device)

            tag = f"fold{fold+1}"
            for k, v in train_m.items():
                writer.add_scalar(f"{tag}/train/{k}", v, epoch)
            for k, v in val_m.items():
                writer.add_scalar(f"{tag}/val/{k}", v, epoch)

            if val_m["mae_wh"] < best_val_mae:
                best_val_mae = val_m["mae_wh"]
                patience_counter = 0
                torch.save(
                    {"model_state_dict": model.state_dict(), "fold": fold, "val_metrics": val_m},
                    output_dir / f"fold_{fold+1}_best.pt",
                )
            else:
                patience_counter += 1
                if patience_counter >= args.patience:
                    break

            if (epoch + 1) % 10 == 0:
                print(
                    f"  E{epoch+1:3d}  train MAE={train_m['mae_wh']:.4f} Wh  "
                    f"val MAE={val_m['mae_wh']:.4f} Wh  R²={val_m['r2']:.4f}"
                )

        print(f"Fold {fold+1} best val MAE: {best_val_mae:.4f} Wh")
        fold_results.append({"fold": fold + 1, "best_val_mae": best_val_mae})

        if best_val_mae < best_fold_mae:
            best_fold_mae = best_val_mae
            best_fold_idx = fold

    # Aggregate summary
    maes = [r["best_val_mae"] for r in fold_results]
    summary = {
        "folds": args.folds,
        "mean_val_mae_wh": float(np.mean(maes)),
        "std_val_mae_wh": float(np.std(maes)),
        "best_fold": best_fold_idx + 1,
        "best_fold_mae_wh": best_fold_mae,
        "fold_results": fold_results,
    }
    print(f"\nCross-validation summary:")
    print(f"  Mean val MAE: {summary['mean_val_mae_wh']:.4f} ± {summary['std_val_mae_wh']:.4f} Wh")

    # SHAP importance on best fold model
    if args.compute_shap:
        print(f"\nComputing feature importance (fold {best_fold_idx + 1})...")
        best_model = EnergyPredictor().to(device)
        ckpt = torch.load(output_dir / f"fold_{best_fold_idx+1}_best.pt", map_location=device)
        best_model.load_state_dict(ckpt["model_state_dict"])
        fit_normalisation(all_X, best_model)

        importance = compute_shap_importance(best_model, all_X, device)
        sorted_imp = sorted(importance.items(), key=lambda t: t[1], reverse=True)
        print("Feature importance (higher = more important):")
        for feat, imp in sorted_imp:
            print(f"  {feat:30s}: {imp:.5f}")
        summary["feature_importance"] = dict(sorted_imp)

    with open(output_dir / "cv_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults saved to {output_dir}")

    writer.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train EnergyPredictor with k-fold CV")
    p.add_argument("--data_dir", type=str, required=True)
    p.add_argument("--output_dir", type=str, default="runs/energy_pred")
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--batch_size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--lambda_mae", type=float, default=0.5)
    p.add_argument("--patience", type=int, default=20)
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--synthetic_samples", type=int, default=20000)
    p.add_argument("--compute_shap", action="store_true",
                   help="Compute SHAP / permutation feature importance after training")
    return p.parse_args()


if __name__ == "__main__":
    kfold_train(parse_args())
