"""
Training script for WheelSlipPredictor.

Loads sequences from ROS2 bag files (or pre-extracted HDF5 files),
applies sequence windowing, and trains with a combined MSE + uncertainty
calibration + physics-informed regularisation loss.

Physics-informed term enforces consistency with the Bekker soil interaction
model: predicted slip must respect the relationship between motor torque,
normal force, and soil shear strength parameters estimated from terrain class.

Usage:
    python train.py \
        --data_dir /data/slip_simulation \
        --output_dir /runs/wheel_slip \
        --epochs 80 \
        --batch_size 64 \
        --lr 3e-4
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
from torch.optim.lr_scheduler import CosineAnnealingLR, OneCycleLR
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset, random_split
from torch.utils.tensorboard import SummaryWriter

from model import WheelSlipPredictor, INPUT_DIM, SEQ_LEN, NUM_WHEELS


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class SlipSequenceDataset(Dataset):
    """
    Loads pre-extracted slip telemetry sequences from a NumPy archive.

    The archive should contain:
        X : (N, SEQ_LEN, INPUT_DIM)  input features
        y : (N, NUM_WHEELS)           ground-truth slip ratios [0,1]
        torques : (N, SEQ_LEN, NUM_WHEELS)  motor torques (for physics loss)
        normals : (N, NUM_WHEELS)           normal forces (N)
        terrain_ids : (N,)                  dominant terrain class

    To produce this from ROS2 bags, run the companion ros2_bag_extractor.py
    script (not included here; requires rclpy + rosbag2_py).
    """

    def __init__(
        self,
        data_path: Path,
        seq_len: int = SEQ_LEN,
        stride: int = 1,
    ) -> None:
        super().__init__()
        data = np.load(str(data_path), allow_pickle=False)
        self.X = torch.from_numpy(data["X"].astype(np.float32))
        self.y = torch.from_numpy(data["y"].astype(np.float32))
        self.torques = torch.from_numpy(data["torques"].astype(np.float32))
        self.normals = torch.from_numpy(data["normals"].astype(np.float32))
        self.terrain_ids = torch.from_numpy(data["terrain_ids"].astype(np.int64))

        assert self.X.shape[1] == seq_len, \
            f"Expected seq_len={seq_len}, got {self.X.shape[1]}"
        assert self.X.shape[2] == INPUT_DIM, \
            f"Expected input_dim={INPUT_DIM}, got {self.X.shape[2]}"

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int) -> dict[str, Tensor]:
        return {
            "x": self.X[idx],
            "y": self.y[idx],
            "torques": self.torques[idx],          # (SEQ_LEN, NUM_WHEELS)
            "normals": self.normals[idx],           # (NUM_WHEELS,)
            "terrain_id": self.terrain_ids[idx],
        }


class SyntheticSlipDataset(Dataset):
    """
    Generates synthetic slip data using simplified Bekker model for development.
    Allows training and validation without real ROS2 bags.
    """

    def __init__(self, n_samples: int = 10000, seq_len: int = SEQ_LEN) -> None:
        super().__init__()
        self.n = n_samples
        self.seq_len = seq_len
        rng = np.random.default_rng(42)

        # Synthetic feature sequences
        self.X = rng.standard_normal((n_samples, seq_len, INPUT_DIM)).astype(np.float32)

        # Simulate slip based on inclination (feature index 26) and torques (20:26)
        inclination = self.X[:, -1, 26]             # last timestep inclination
        torque_mean = self.X[:, -1, 20:26].mean(-1)
        base_slip = np.clip(
            0.05 + 0.3 * np.abs(inclination) / 45.0 + 0.1 * np.abs(torque_mean),
            0.0, 0.95,
        )
        self.y = np.clip(
            base_slip[:, None] + rng.standard_normal((n_samples, NUM_WHEELS)) * 0.03,
            0.0, 1.0,
        ).astype(np.float32)

        self.torques = self.X[:, :, 20:26]          # (N, T, W)
        self.normals = (
            np.ones((n_samples, NUM_WHEELS), dtype=np.float32) * 150.0
            + rng.standard_normal((n_samples, NUM_WHEELS)).astype(np.float32) * 20.0
        )
        self.terrain_ids = rng.integers(0, 8, size=n_samples).astype(np.int64)

        self.X = torch.from_numpy(self.X)
        self.y = torch.from_numpy(self.y)
        self.torques = torch.from_numpy(self.torques)
        self.normals = torch.from_numpy(self.normals)
        self.terrain_ids = torch.from_numpy(self.terrain_ids)

    def __len__(self) -> int:
        return self.n

    def __getitem__(self, idx: int) -> dict[str, Tensor]:
        return {
            "x": self.X[idx],
            "y": self.y[idx],
            "torques": self.torques[idx],
            "normals": self.normals[idx],
            "terrain_id": self.terrain_ids[idx],
        }


# ---------------------------------------------------------------------------
# Loss functions
# ---------------------------------------------------------------------------

# Bekker soil parameters per terrain class (simplified, order-of-magnitude)
# Format: (cohesion c [Pa], friction_angle phi [rad], k_phi, k_c, n)
BEKKER_PARAMS = {
    0: (200.0,  0.52, 800e3,  1.4e3, 1.0),   # flat_regolith
    1: (400.0,  0.61, 1400e3, 2.0e3, 1.1),   # rocky_terrain
    2: (200.0,  0.52, 800e3,  1.4e3, 1.0),   # crater_rim
    3: (150.0,  0.44, 600e3,  1.0e3, 0.9),   # crater_interior
    4: (800.0,  0.70, 2000e3, 3.0e3, 1.2),   # boulder (rarely traversed)
    5: (100.0,  0.35, 400e3,  0.8e3, 0.8),   # shadowed_psr (ice-mixed regolith)
    6: (200.0,  0.52, 800e3,  1.4e3, 1.0),   # sunlit_safe
    7: (200.0,  0.52, 800e3,  1.4e3, 1.0),   # comms_shadow
}


def bekker_shear_stress(
    slip: Tensor,
    torques: Tensor,
    normals: Tensor,
    terrain_ids: Tensor,
    wheel_radius: float = 0.25,
    wheel_width: float = 0.15,
) -> Tensor:
    """
    Approximates Bekker shear stress limit and penalises predictions that
    imply physically impossible torque-slip combinations.

    Returns a per-sample scalar penalty (lower = more physically consistent).
    """
    # Average torques over last 3 timesteps
    tau = torques[:, -3:, :].mean(1)                  # (B, W)
    force = tau / wheel_radius                          # drawbar pull approx (N)

    # Contact area approximation: A = width * length, length ≈ sqrt(sinkage)
    A = wheel_width * wheel_radius * 0.5               # rough estimate (m²)

    # Cohesion-weighted slip limit (Janosi-Hanamoto):  tau_max = (c + sigma*tan(phi)) * (1 - exp(-j/k))
    # j = slip * s  (shear displacement ~ slip * contact_length)
    contact_len = wheel_radius * 0.5
    j = slip.clamp(0, 1) * contact_len                 # (B, W)

    # Use dominant terrain class for cohesion lookup
    c_vals = torch.zeros(len(terrain_ids), dtype=torch.float32, device=slip.device)
    for tc, params in BEKKER_PARAMS.items():
        mask = terrain_ids == tc
        if mask.any():
            c_vals[mask] = params[0]
    c_vals = c_vals.unsqueeze(1)                       # (B, 1)

    sigma = normals / A                                 # normal stress (Pa)
    friction_phi = torch.full_like(c_vals, 0.52)       # approx avg tan(phi)
    tau_max = (c_vals + sigma * friction_phi.tan()) * (1 - (-j / 0.02).exp())

    # Predicted traction force
    pred_force = tau_max * A

    # Penalty: predicted force should be consistent with applied torque
    penalty = F.mse_loss(pred_force, force.abs().clamp(0, pred_force.max() + 1))
    return penalty


class SlipLoss(nn.Module):
    """
    Combined loss:
      L = MSE(slip_pred, slip_gt)
        + lambda_unc * NLL(slip_pred, log_var, slip_gt)   [uncertainty calibration]
        + lambda_phys * Bekker_penalty                     [physics regularisation]
    """

    def __init__(
        self,
        lambda_unc: float = 0.5,
        lambda_phys: float = 0.01,
    ) -> None:
        super().__init__()
        self.lambda_unc = lambda_unc
        self.lambda_phys = lambda_phys

    def forward(
        self,
        slip_pred: Tensor,
        log_var: Tensor,
        slip_gt: Tensor,
        torques: Tensor,
        normals: Tensor,
        terrain_ids: Tensor,
    ) -> tuple[Tensor, dict[str, float]]:
        # MSE
        mse = F.mse_loss(slip_pred, slip_gt)

        # Negative log-likelihood with heteroscedastic uncertainty
        # NLL = 0.5 * (log_var + (pred - gt)^2 / exp(log_var))
        nll = 0.5 * (log_var + (slip_pred - slip_gt) ** 2 / (log_var.exp() + 1e-8))
        nll_loss = nll.mean()

        # Physics penalty
        phys = bekker_shear_stress(slip_pred, torques, normals, terrain_ids)

        total = mse + self.lambda_unc * nll_loss + self.lambda_phys * phys
        components = {
            "mse": float(mse.item()),
            "nll": float(nll_loss.item()),
            "phys": float(phys.item()),
        }
        return total, components


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(slip_pred: Tensor, slip_gt: Tensor) -> dict[str, float]:
    with torch.no_grad():
        mae = (slip_pred - slip_gt).abs().mean()
        rmse = ((slip_pred - slip_gt) ** 2).mean().sqrt()
        # R² per wheel, averaged
        ss_res = ((slip_pred - slip_gt) ** 2).sum(0)
        ss_tot = ((slip_gt - slip_gt.mean(0)) ** 2).sum(0)
        r2 = (1.0 - ss_res / (ss_tot + 1e-8)).mean()
        return {
            "mae": float(mae.item()),
            "rmse": float(rmse.item()),
            "r2": float(r2.item()),
        }


# ---------------------------------------------------------------------------
# Train / validate loops
# ---------------------------------------------------------------------------

def train_one_epoch(
    model: WheelSlipPredictor,
    loader: DataLoader,
    optimizer: AdamW,
    criterion: SlipLoss,
    scaler: GradScaler,
    device: torch.device,
    epoch: int,
    writer: SummaryWriter,
) -> dict[str, float]:
    model.train()
    total_loss = 0.0
    all_preds, all_gts = [], []
    t0 = time.time()

    for step, batch in enumerate(loader):
        x = batch["x"].to(device, non_blocking=True)
        y = batch["y"].to(device, non_blocking=True)
        torques = batch["torques"].to(device, non_blocking=True)
        normals = batch["normals"].to(device, non_blocking=True)
        terrain_ids = batch["terrain_id"].to(device, non_blocking=True)

        with autocast():
            slip_pred, log_var = model(x)
            loss, components = criterion(slip_pred, log_var, y, torques, normals, terrain_ids)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)

        total_loss += loss.item()
        all_preds.append(slip_pred.detach().cpu())
        all_gts.append(y.cpu())

        if step % 50 == 0:
            global_step = epoch * len(loader) + step
            for k, v in components.items():
                writer.add_scalar(f"train/component_{k}", v, global_step)

    all_preds = torch.cat(all_preds, dim=0)
    all_gts = torch.cat(all_gts, dim=0)
    metrics = compute_metrics(all_preds, all_gts)
    metrics["loss"] = total_loss / len(loader)
    metrics["epoch_time"] = time.time() - t0
    return metrics


@torch.no_grad()
def validate(
    model: WheelSlipPredictor,
    loader: DataLoader,
    criterion: SlipLoss,
    device: torch.device,
) -> dict[str, float]:
    model.eval()
    total_loss = 0.0
    all_preds, all_gts = [], []

    for batch in loader:
        x = batch["x"].to(device, non_blocking=True)
        y = batch["y"].to(device, non_blocking=True)
        torques = batch["torques"].to(device, non_blocking=True)
        normals = batch["normals"].to(device, non_blocking=True)
        terrain_ids = batch["terrain_id"].to(device, non_blocking=True)

        with autocast():
            slip_pred, log_var = model(x)
            loss, _ = criterion(slip_pred, log_var, y, torques, normals, terrain_ids)

        total_loss += loss.item()
        all_preds.append(slip_pred.cpu())
        all_gts.append(y.cpu())

    all_preds = torch.cat(all_preds, dim=0)
    all_gts = torch.cat(all_gts, dim=0)
    metrics = compute_metrics(all_preds, all_gts)
    metrics["loss"] = total_loss / len(loader)
    return metrics


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def train(args: argparse.Namespace) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = output_dir / "checkpoints"
    ckpt_dir.mkdir(exist_ok=True)
    writer = SummaryWriter(log_dir=str(output_dir / "tensorboard"))

    # Data
    data_dir = Path(args.data_dir)
    npz_path = data_dir / "slip_sequences.npz"

    if npz_path.exists():
        full_dataset = SlipSequenceDataset(npz_path)
    else:
        print("No slip_sequences.npz found — using synthetic data for development.")
        full_dataset = SyntheticSlipDataset(n_samples=args.synthetic_samples)

    n_val = max(1, int(len(full_dataset) * 0.15))
    n_train = len(full_dataset) - n_val
    train_ds, val_ds = random_split(
        full_dataset, [n_train, n_val],
        generator=torch.Generator().manual_seed(42),
    )

    train_loader = DataLoader(
        train_ds, batch_size=args.batch_size, shuffle=True,
        num_workers=args.num_workers, pin_memory=(device.type == "cuda"), drop_last=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=args.batch_size * 2, shuffle=False,
        num_workers=args.num_workers, pin_memory=(device.type == "cuda"),
    )
    print(f"Train: {n_train}  Val: {n_val}")

    # Model
    model = WheelSlipPredictor(
        mc_dropout_rate=args.dropout,
    ).to(device)
    print(f"Parameters: {model.count_parameters():,}")

    criterion = SlipLoss(lambda_unc=args.lambda_unc, lambda_phys=args.lambda_phys)
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=1e-5)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.lr * 0.01)
    scaler = GradScaler()

    best_val_mae = float("inf")
    patience_counter = 0

    for epoch in range(args.epochs):
        lr = scheduler.get_last_lr()[0]
        print(f"\nEpoch {epoch + 1}/{args.epochs}  lr={lr:.2e}")

        train_m = train_one_epoch(model, train_loader, optimizer, criterion, scaler, device, epoch, writer)
        scheduler.step()

        print(
            f"  Train | loss={train_m['loss']:.4f}  "
            f"MAE={train_m['mae']:.4f}  RMSE={train_m['rmse']:.4f}  "
            f"R²={train_m['r2']:.4f}  t={train_m['epoch_time']:.1f}s"
        )
        for k, v in train_m.items():
            if k != "epoch_time":
                writer.add_scalar(f"train/{k}", v, epoch)

        val_m = validate(model, val_loader, criterion, device)
        print(
            f"  Val   | loss={val_m['loss']:.4f}  "
            f"MAE={val_m['mae']:.4f}  RMSE={val_m['rmse']:.4f}  "
            f"R²={val_m['r2']:.4f}"
        )
        for k, v in val_m.items():
            writer.add_scalar(f"val/{k}", v, epoch)

        if val_m["mae"] < best_val_mae:
            best_val_mae = val_m["mae"]
            patience_counter = 0
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "best_val_mae": best_val_mae,
                    "val_metrics": val_m,
                    "args": vars(args),
                },
                ckpt_dir / "best.pt",
            )
            print(f"  ** New best val MAE: {best_val_mae:.5f} **")
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                print(f"Early stopping after {args.patience} epochs without improvement.")
                break

    writer.close()
    with open(output_dir / "train_config.json", "w") as f:
        json.dump(vars(args), f, indent=2)
    print(f"\nDone. Best val MAE: {best_val_mae:.5f}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train WheelSlipPredictor")
    p.add_argument("--data_dir", type=str, required=True)
    p.add_argument("--output_dir", type=str, default="runs/wheel_slip")
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--batch_size", type=int, default=64)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--dropout", type=float, default=0.2)
    p.add_argument("--lambda_unc", type=float, default=0.5,
                   help="Weight for NLL uncertainty calibration loss")
    p.add_argument("--lambda_phys", type=float, default=0.01,
                   help="Weight for Bekker physics regularisation")
    p.add_argument("--patience", type=int, default=15)
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--synthetic_samples", type=int, default=10000,
                   help="Samples to generate when no real data found")
    return p.parse_args()


if __name__ == "__main__":
    train(parse_args())
