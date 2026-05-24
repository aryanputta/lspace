"""
Dataset for lunar terrain segmentation.

Loads paired (RGB, optional thermal IR, label mask) image sets.
Supports train / val / test splits and mission-realistic augmentation.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Callable, Literal, Optional

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch import Tensor
from torch.utils.data import DataLoader, Dataset

# ---------------------------------------------------------------------------
# Lunar scene normalisation statistics
# (derived from Apollo Metric Camera + Lunar Reconnaissance Orbiter imagery)
# ---------------------------------------------------------------------------

LUNAR_RGB_MEAN = [0.412, 0.398, 0.380]
LUNAR_RGB_STD = [0.198, 0.192, 0.188]
LUNAR_THERMAL_MEAN = [0.301]      # normalised 8-bit thermal IR (80-400 K range)
LUNAR_THERMAL_STD = [0.215]

IGNORE_INDEX = 255   # mask value for unlabelled / invalid pixels
NUM_CLASSES = 8


# ---------------------------------------------------------------------------
# Per-pixel normalisation
# ---------------------------------------------------------------------------

def _normalise(
    img: Tensor,
    mean: list[float],
    std: list[float],
) -> Tensor:
    m = torch.tensor(mean, dtype=torch.float32).view(-1, 1, 1)
    s = torch.tensor(std,  dtype=torch.float32).view(-1, 1, 1)
    return (img - m) / s


# ---------------------------------------------------------------------------
# Augmentation helpers
# ---------------------------------------------------------------------------

def _random_horizontal_flip(
    image: Tensor, mask: Tensor, p: float = 0.5
) -> tuple[Tensor, Tensor]:
    if random.random() < p:
        image = torch.flip(image, dims=[-1])
        mask = torch.flip(mask, dims=[-1])
    return image, mask


def _random_crop(
    image: Tensor,
    mask: Tensor,
    crop_h: int,
    crop_w: int,
) -> tuple[Tensor, Tensor]:
    _, h, w = image.shape
    top = random.randint(0, max(0, h - crop_h))
    left = random.randint(0, max(0, w - crop_w))
    image = image[:, top:top + crop_h, left:left + crop_w]
    mask = mask[top:top + crop_h, left:left + crop_w]
    return image, mask


def _lunar_illumination_jitter(
    rgb: Tensor,
    brightness_range: tuple[float, float] = (0.5, 1.8),
    contrast_range: tuple[float, float] = (0.6, 1.6),
    shadow_prob: float = 0.2,
) -> Tensor:
    """
    Simulates extreme lunar illumination conditions:
    - high sun angle: saturated bright regolith
    - low sun angle: long shadows, high-contrast terminator
    - PSR shadowing: near-zero ambient illumination in patches
    """
    # Brightness
    b = random.uniform(*brightness_range)
    rgb = rgb * b

    # Contrast (around mean)
    c = random.uniform(*contrast_range)
    mean = rgb.mean(dim=[1, 2], keepdim=True)
    rgb = (rgb - mean) * c + mean

    # PSR-style shadow patch (random dark rectangle)
    if random.random() < shadow_prob:
        _, h, w = rgb.shape
        sh = random.randint(h // 8, h // 3)
        sw = random.randint(w // 8, w // 3)
        top = random.randint(0, h - sh)
        left = random.randint(0, w - sw)
        shadow_factor = random.uniform(0.02, 0.15)
        rgb[:, top:top + sh, left:left + sw] *= shadow_factor

    return rgb.clamp(0.0, 1.0)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class LunarTerrainDataset(Dataset):
    """
    Directory layout expected::

        data_dir/
            train.json   (or val.json / test.json)
            images/
                rgb/        <frame_id>.png   (H x W x 3, uint8)
                thermal/    <frame_id>.png   (H x W,   uint8, optional)
            labels/
                <frame_id>.png               (H x W,   uint8, 0-7 or 255)

    JSON manifest format::

        [
          {"id": "frame_000001", "has_thermal": true},
          ...
        ]

    Args:
        data_dir:        root dataset directory.
        split:           one of "train", "val", "test".
        use_thermal:     include thermal channel when available.
        output_size:     (H, W) resize target; None → keep original.
        augment:         apply training augmentation.
        crop_size:       random crop dimensions during training.
    """

    def __init__(
        self,
        data_dir: str | Path,
        split: Literal["train", "val", "test"] = "train",
        use_thermal: bool = True,
        output_size: Optional[tuple[int, int]] = (480, 640),
        augment: bool = True,
        crop_size: Optional[tuple[int, int]] = (400, 560),
    ) -> None:
        super().__init__()
        self.data_dir = Path(data_dir)
        self.split = split
        self.use_thermal = use_thermal
        self.output_size = output_size
        self.augment = augment and split == "train"
        self.crop_size = crop_size

        manifest_path = self.data_dir / f"{split}.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path) as f:
            self.samples: list[dict] = json.load(f)

    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, Tensor]:
        sample = self.samples[idx]
        frame_id: str = sample["id"]
        has_thermal: bool = sample.get("has_thermal", False) and self.use_thermal

        # Load RGB
        rgb_path = self.data_dir / "images" / "rgb" / f"{frame_id}.png"
        rgb = self._load_image_as_tensor(rgb_path, mode="RGB")   # (3, H, W) float [0,1]

        # Load thermal
        if has_thermal:
            th_path = self.data_dir / "images" / "thermal" / f"{frame_id}.png"
            thermal = self._load_image_as_tensor(th_path, mode="L")  # (1, H, W) float [0,1]
        else:
            thermal = None

        # Load label mask
        label_path = self.data_dir / "labels" / f"{frame_id}.png"
        mask = self._load_mask_as_tensor(label_path)              # (H, W) int64

        # Resize to output_size
        if self.output_size is not None:
            rgb = self._resize_image(rgb, self.output_size)
            mask = self._resize_mask(mask, self.output_size)
            if thermal is not None:
                thermal = self._resize_image(thermal, self.output_size)

        # Augment (training only)
        if self.augment:
            rgb = _lunar_illumination_jitter(rgb)
            if thermal is not None:
                # mild brightness jitter on thermal
                t_factor = random.uniform(0.85, 1.15)
                thermal = (thermal * t_factor).clamp(0, 1)

            # Stack for joint spatial augmentation
            if thermal is not None:
                combined = torch.cat([rgb, thermal], dim=0)  # (4, H, W)
            else:
                combined = rgb

            combined, mask = _random_horizontal_flip(combined, mask)
            if self.crop_size is not None:
                combined, mask = _random_crop(combined, mask, *self.crop_size)

            if thermal is not None:
                rgb, thermal = combined[:3], combined[3:]
            else:
                rgb = combined

        # Normalise
        rgb = _normalise(rgb, LUNAR_RGB_MEAN, LUNAR_RGB_STD)
        if thermal is not None:
            thermal = _normalise(thermal, LUNAR_THERMAL_MEAN, LUNAR_THERMAL_STD)

        # Assemble 4-channel input (pad with zeros if no thermal)
        if thermal is not None:
            image = torch.cat([rgb, thermal], dim=0)  # (4, H, W)
        else:
            pad = torch.zeros(1, rgb.shape[1], rgb.shape[2], dtype=torch.float32)
            image = torch.cat([rgb, pad], dim=0)      # (4, H, W) — thermal channel = 0

        return {
            "image": image,
            "mask": mask,
            "frame_id": frame_id,
            "has_thermal": torch.tensor(has_thermal, dtype=torch.bool),
        }

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_image_as_tensor(path: Path, mode: str) -> Tensor:
        img = Image.open(path).convert(mode)
        arr = np.array(img, dtype=np.float32) / 255.0
        t = torch.from_numpy(arr)
        if t.ndim == 2:
            t = t.unsqueeze(0)      # (1, H, W)
        else:
            t = t.permute(2, 0, 1)  # (C, H, W)
        return t

    @staticmethod
    def _load_mask_as_tensor(path: Path) -> Tensor:
        img = Image.open(path).convert("L")
        arr = np.array(img, dtype=np.int64)
        return torch.from_numpy(arr)

    @staticmethod
    def _resize_image(img: Tensor, size: tuple[int, int]) -> Tensor:
        return F.interpolate(
            img.unsqueeze(0), size=size, mode="bilinear", align_corners=False
        ).squeeze(0)

    @staticmethod
    def _resize_mask(mask: Tensor, size: tuple[int, int]) -> Tensor:
        # nearest neighbour to preserve class ids
        return F.interpolate(
            mask.unsqueeze(0).unsqueeze(0).float(),
            size=size, mode="nearest",
        ).squeeze().long()


# ---------------------------------------------------------------------------
# DataLoader factory
# ---------------------------------------------------------------------------

def build_dataloaders(
    data_dir: str | Path,
    batch_size: int = 8,
    num_workers: int = 4,
    use_thermal: bool = True,
    output_size: tuple[int, int] = (480, 640),
    crop_size: tuple[int, int] = (400, 560),
    pin_memory: bool = True,
) -> dict[str, DataLoader]:
    loaders: dict[str, DataLoader] = {}
    for split in ("train", "val", "test"):
        manifest = Path(data_dir) / f"{split}.json"
        if not manifest.exists():
            continue
        ds = LunarTerrainDataset(
            data_dir=data_dir,
            split=split,  # type: ignore[arg-type]
            use_thermal=use_thermal,
            output_size=output_size,
            augment=(split == "train"),
            crop_size=crop_size if split == "train" else None,
        )
        loaders[split] = DataLoader(
            ds,
            batch_size=batch_size,
            shuffle=(split == "train"),
            num_workers=num_workers,
            pin_memory=pin_memory,
            drop_last=(split == "train"),
        )
    return loaders


# ---------------------------------------------------------------------------
# Synthetic manifest generator (development / CI use)
# ---------------------------------------------------------------------------

def create_synthetic_manifest(
    out_dir: str | Path,
    n_train: int = 500,
    n_val: int = 100,
    n_test: int = 50,
) -> None:
    """Creates dummy JSON manifests without real image files (for unit tests)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for split, n in [("train", n_train), ("val", n_val), ("test", n_test)]:
        samples = [
            {"id": f"frame_{i:06d}", "has_thermal": (i % 3 != 0)}
            for i in range(n)
        ]
        with open(out_dir / f"{split}.json", "w") as f:
            json.dump(samples, f, indent=2)
