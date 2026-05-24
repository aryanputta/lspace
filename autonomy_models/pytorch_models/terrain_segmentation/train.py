"""
Training script for LunarTerrainSegmentation.

Mixed-precision training with AdamW + cosine LR, Dice+CrossEntropy loss,
mIoU tracking, TensorBoard logging, and best-checkpoint saving.

Usage:
    python train.py \
        --data_dir /data/lunar_terrain \
        --output_dir /runs/terrain_seg \
        --epochs 100 \
        --batch_size 8 \
        --lr 1e-3
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.cuda.amp import GradScaler, autocast
from torch.utils.tensorboard import SummaryWriter

from model import LunarTerrainSegmentation, NUM_CLASSES, TERRAIN_CLASSES
from dataset import build_dataloaders


# ---------------------------------------------------------------------------
# Loss
# ---------------------------------------------------------------------------

class DiceLoss(nn.Module):
    """
    Soft Dice loss over non-ignored pixels.
    Handles class imbalance better than pure cross-entropy for sparse classes
    like boulder and shadowed_psr.
    """

    def __init__(self, num_classes: int, ignore_index: int = 255, smooth: float = 1.0) -> None:
        super().__init__()
        self.num_classes = num_classes
        self.ignore_index = ignore_index
        self.smooth = smooth

    def forward(self, logits: Tensor, targets: Tensor) -> Tensor:
        probs = F.softmax(logits, dim=1)
        valid = targets != self.ignore_index
        targets_safe = targets.clone()
        targets_safe[~valid] = 0

        one_hot = F.one_hot(targets_safe, self.num_classes).permute(0, 3, 1, 2).float()
        mask = valid.unsqueeze(1).float()
        one_hot = one_hot * mask
        probs = probs * mask

        dims = (0, 2, 3)
        intersection = (probs * one_hot).sum(dims)
        union = probs.sum(dims) + one_hot.sum(dims)
        dice = (2.0 * intersection + self.smooth) / (union + self.smooth)
        return 1.0 - dice.mean()


class CombinedSegLoss(nn.Module):
    """0.4 * CrossEntropy + 0.6 * Dice."""

    def __init__(
        self,
        num_classes: int,
        ignore_index: int = 255,
        class_weights: Optional[Tensor] = None,
    ) -> None:
        super().__init__()
        self.ce = nn.CrossEntropyLoss(
            weight=class_weights, ignore_index=ignore_index, label_smoothing=0.05
        )
        self.dice = DiceLoss(num_classes, ignore_index=ignore_index)

    def forward(self, logits: Tensor, targets: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        ce_loss = self.ce(logits, targets)
        dice_loss = self.dice(logits, targets)
        total = 0.4 * ce_loss + 0.6 * dice_loss
        return total, ce_loss, dice_loss


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class SegmentationMetrics:
    """Accumulates confusion matrix and computes per-class and mean IoU."""

    def __init__(self, num_classes: int, ignore_index: int = 255) -> None:
        self.num_classes = num_classes
        self.ignore_index = ignore_index
        self.confusion = torch.zeros(num_classes, num_classes, dtype=torch.long)

    def update(self, preds: Tensor, targets: Tensor) -> None:
        preds = preds.view(-1).cpu()
        targets = targets.view(-1).cpu()
        valid = targets != self.ignore_index
        preds, targets = preds[valid], targets[valid]
        combined = targets * self.num_classes + preds
        counts = torch.bincount(combined, minlength=self.num_classes ** 2)
        self.confusion += counts.reshape(self.num_classes, self.num_classes)

    def iou_per_class(self) -> dict[str, float]:
        tp = self.confusion.diagonal().float()
        fn = self.confusion.sum(1).float() - tp
        fp = self.confusion.sum(0).float() - tp
        iou = tp / (tp + fn + fp + 1e-10)
        return {TERRAIN_CLASSES[i]: float(iou[i]) for i in range(self.num_classes)}

    def mean_iou(self) -> float:
        iou = list(self.iou_per_class().values())
        return float(sum(iou) / len(iou))

    def pixel_accuracy(self) -> float:
        correct = float(self.confusion.diagonal().sum())
        total = float(self.confusion.sum())
        return correct / (total + 1e-10)

    def reset(self) -> None:
        self.confusion.zero_()


# ---------------------------------------------------------------------------
# Class frequency weights
# ---------------------------------------------------------------------------

def compute_class_weights(
    data_dir: Path, num_classes: int, ignore_index: int = 255
) -> Tensor:
    """
    Computes inverse-frequency weights from the training manifest labels.
    Falls back to uniform if labels cannot be read.
    """
    import json
    from PIL import Image
    import numpy as np

    manifest_path = data_dir / "train.json"
    if not manifest_path.exists():
        return torch.ones(num_classes)

    with open(manifest_path) as f:
        samples = json.load(f)

    counts = np.zeros(num_classes, dtype=np.float64)
    labels_dir = data_dir / "labels"

    for s in samples[:200]:  # subsample for speed
        lp = labels_dir / f"{s['id']}.png"
        if not lp.exists():
            continue
        arr = np.array(Image.open(lp).convert("L"))
        for c in range(num_classes):
            counts[c] += (arr == c).sum()

    if counts.sum() == 0:
        return torch.ones(num_classes)

    freq = counts / counts.sum()
    weights = 1.0 / (freq + 1e-6)
    weights = weights / weights.sum() * num_classes
    return torch.tensor(weights, dtype=torch.float32)


# ---------------------------------------------------------------------------
# Training step
# ---------------------------------------------------------------------------

def train_one_epoch(
    model: LunarTerrainSegmentation,
    loader: torch.utils.data.DataLoader,
    optimizer: AdamW,
    criterion: CombinedSegLoss,
    scaler: GradScaler,
    device: torch.device,
    epoch: int,
    writer: SummaryWriter,
    grad_clip: float = 1.0,
) -> dict[str, float]:
    model.train()
    metrics = SegmentationMetrics(NUM_CLASSES)
    total_loss = ce_sum = dice_sum = 0.0
    t0 = time.time()

    for step, batch in enumerate(loader):
        images = batch["image"].to(device, non_blocking=True)
        masks = batch["mask"].to(device, non_blocking=True)

        with autocast():
            logits = model(images)
            loss, ce_l, dice_l = criterion(logits, masks)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)

        preds = logits.detach().argmax(dim=1)
        metrics.update(preds, masks)

        total_loss += loss.item()
        ce_sum += ce_l.item()
        dice_sum += dice_l.item()

        global_step = epoch * len(loader) + step
        if step % 20 == 0:
            writer.add_scalar("train/loss_step", loss.item(), global_step)

    n = len(loader)
    return {
        "loss": total_loss / n,
        "ce_loss": ce_sum / n,
        "dice_loss": dice_sum / n,
        "mIoU": metrics.mean_iou(),
        "pixel_acc": metrics.pixel_accuracy(),
        "epoch_time": time.time() - t0,
    }


# ---------------------------------------------------------------------------
# Validation step
# ---------------------------------------------------------------------------

@torch.no_grad()
def validate(
    model: LunarTerrainSegmentation,
    loader: torch.utils.data.DataLoader,
    criterion: CombinedSegLoss,
    device: torch.device,
) -> dict[str, float]:
    model.eval()
    metrics = SegmentationMetrics(NUM_CLASSES)
    total_loss = 0.0

    for batch in loader:
        images = batch["image"].to(device, non_blocking=True)
        masks = batch["mask"].to(device, non_blocking=True)

        with autocast():
            logits = model(images)
            loss, _, _ = criterion(logits, masks)

        total_loss += loss.item()
        preds = logits.argmax(dim=1)
        metrics.update(preds, masks)

    iou_per_class = metrics.iou_per_class()
    result: dict[str, float] = {
        "loss": total_loss / len(loader),
        "mIoU": metrics.mean_iou(),
        "pixel_acc": metrics.pixel_accuracy(),
    }
    result.update({f"iou/{k}": v for k, v in iou_per_class.items()})
    return result


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def save_checkpoint(
    path: Path,
    model: LunarTerrainSegmentation,
    optimizer: AdamW,
    scheduler: CosineAnnealingLR,
    epoch: int,
    best_miou: float,
    val_metrics: dict[str, float],
) -> None:
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "best_miou": best_miou,
            "val_metrics": val_metrics,
        },
        path,
    )


def load_checkpoint(
    path: Path,
    model: LunarTerrainSegmentation,
    optimizer: Optional[AdamW] = None,
    scheduler: Optional[CosineAnnealingLR] = None,
    device: str = "cpu",
) -> tuple[int, float]:
    ckpt = torch.load(path, map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    if optimizer is not None and "optimizer_state_dict" in ckpt:
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
    if scheduler is not None and "scheduler_state_dict" in ckpt:
        scheduler.load_state_dict(ckpt["scheduler_state_dict"])
    return ckpt.get("epoch", 0), ckpt.get("best_miou", 0.0)


# ---------------------------------------------------------------------------
# Main training loop
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
    loaders = build_dataloaders(
        data_dir=args.data_dir,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        use_thermal=not args.rgb_only,
        output_size=(480, 640),
        crop_size=(400, 560),
        pin_memory=(device.type == "cuda"),
    )
    assert "train" in loaders, "Training manifest not found."

    # Model
    in_ch = 3 if args.rgb_only else 4
    model = LunarTerrainSegmentation(in_channels=in_ch, num_classes=NUM_CLASSES).to(device)
    print(f"Model parameters: {model.count_parameters():,}")

    # Class weights from training distribution
    class_weights: Optional[Tensor] = None
    if args.use_class_weights:
        class_weights = compute_class_weights(
            Path(args.data_dir), NUM_CLASSES
        ).to(device)
        print(f"Class weights: {class_weights.tolist()}")

    criterion = CombinedSegLoss(NUM_CLASSES, class_weights=class_weights).to(device)

    optimizer = AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.lr * 0.01)
    scaler = GradScaler()

    start_epoch = 0
    best_miou = 0.0

    if args.resume:
        resume_path = Path(args.resume)
        if resume_path.exists():
            start_epoch, best_miou = load_checkpoint(
                resume_path, model, optimizer, scheduler, str(device)
            )
            print(f"Resumed from epoch {start_epoch}, best mIoU {best_miou:.4f}")

    # Early stopping state
    patience_counter = 0

    for epoch in range(start_epoch, args.epochs):
        print(f"\nEpoch {epoch + 1}/{args.epochs}  lr={scheduler.get_last_lr()[0]:.2e}")

        train_metrics = train_one_epoch(
            model, loaders["train"], optimizer, criterion, scaler, device, epoch, writer
        )
        scheduler.step()

        print(
            f"  Train | loss={train_metrics['loss']:.4f}  "
            f"mIoU={train_metrics['mIoU']:.4f}  "
            f"pxAcc={train_metrics['pixel_acc']:.4f}  "
            f"t={train_metrics['epoch_time']:.1f}s"
        )
        for k, v in train_metrics.items():
            if k != "epoch_time":
                writer.add_scalar(f"train/{k}", v, epoch)

        if "val" in loaders:
            val_metrics = validate(model, loaders["val"], criterion, device)
            val_miou = val_metrics["mIoU"]
            print(
                f"  Val   | loss={val_metrics['loss']:.4f}  "
                f"mIoU={val_miou:.4f}  "
                f"pxAcc={val_metrics['pixel_acc']:.4f}"
            )
            for k, v in val_metrics.items():
                writer.add_scalar(f"val/{k}", v, epoch)

            # Best checkpoint
            if val_miou > best_miou:
                best_miou = val_miou
                patience_counter = 0
                save_checkpoint(
                    ckpt_dir / "best.pt",
                    model, optimizer, scheduler, epoch, best_miou, val_metrics,
                )
                print(f"  ** New best mIoU: {best_miou:.4f} — saved checkpoint **")
            else:
                patience_counter += 1
                if patience_counter >= args.patience:
                    print(f"Early stopping triggered after {args.patience} non-improving epochs.")
                    break

        # Periodic checkpoint every N epochs
        if (epoch + 1) % args.save_every == 0:
            save_checkpoint(
                ckpt_dir / f"epoch_{epoch + 1:04d}.pt",
                model, optimizer, scheduler, epoch, best_miou,
                val_metrics if "val" in loaders else {},
            )

    writer.close()

    # Save training config
    with open(output_dir / "train_config.json", "w") as f:
        json.dump(vars(args), f, indent=2)

    print(f"\nTraining complete. Best val mIoU: {best_miou:.4f}")
    print(f"Checkpoints saved to: {ckpt_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train LunarTerrainSegmentation")
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default="runs/terrain_seg")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight_decay", type=float, default=1e-4)
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--patience", type=int, default=20,
                        help="Early stopping patience (epochs without val mIoU improvement)")
    parser.add_argument("--save_every", type=int, default=10,
                        help="Save a checkpoint every N epochs in addition to best")
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to checkpoint to resume from")
    parser.add_argument("--rgb_only", action="store_true",
                        help="Use 3-channel RGB input (no thermal)")
    parser.add_argument("--use_class_weights", action="store_true",
                        help="Compute inverse-frequency class weights")
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())
