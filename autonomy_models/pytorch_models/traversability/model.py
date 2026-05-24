"""
Traversability estimation from Bird's Eye View (BEV) elevation maps.

Input: 200x200 local elevation map (20m x 20m at 0.1m/pixel from SLAM).
Output: 200x200 traversability score map [0=impassable, 1=easy].

The model computes a multi-factor traversability score from:
  - Local slope (gradient of elevation)
  - Terrain roughness (local variance of elevation)
  - PSR risk (persistent shadow region indicator channel)
  - Comms shadow penalty

Designed to run as a Nav2 costmap layer plugin: the score map is converted
to a cost map [0=free, 254=lethal] by the plugin wrapper.

Target: <10ms inference on Jetson AGX Orin (200x200 BEV is small).
"""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


# ---------------------------------------------------------------------------
# Input channels (BEV map)
# ---------------------------------------------------------------------------
# Channel 0: elevation (metres, relative to rover)
# Channel 1: elevation confidence (0-1, from SLAM uncertainty)
# Channel 2: PSR risk (0-1, precomputed from orbital illumination model)
# Channel 3: comms shadow (0-1, LOS quality)

IN_CHANNELS = 4
BEV_SIZE = 200   # pixels (20m / 0.1m per pixel)


# ---------------------------------------------------------------------------
# Differentiable slope and roughness kernels
# ---------------------------------------------------------------------------

def _sobel_kernels() -> tuple[Tensor, Tensor]:
    """Returns (Kx, Ky) Sobel gradient kernels for 0.1m/pixel resolution."""
    Kx = torch.tensor(
        [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32
    ).view(1, 1, 3, 3) / (8 * 0.1)  # normalise by 8*pixel_size
    Ky = Kx.transpose(-2, -1).clone()
    return Kx, Ky


class SlopeRoughnessExtractor(nn.Module):
    """
    Fixed (non-learnable) extractor for slope and roughness features.

    Slope: magnitude of elevation gradient (rad, approximated as atan(dz/ds))
    Roughness: local variance over 5x5 window (m²)

    Using fixed kernels here because slope and roughness have well-defined
    physical meanings; learning these would waste capacity and reduce
    interpretability for mission safety review.
    """

    def __init__(self, pixel_size: float = 0.1) -> None:
        super().__init__()
        Kx, Ky = _sobel_kernels()
        self.register_buffer("Kx", Kx)
        self.register_buffer("Ky", Ky)
        self.pixel_size = pixel_size

    def forward(self, elevation: Tensor) -> tuple[Tensor, Tensor]:
        """
        Args:
            elevation: (B, 1, H, W) elevation channel

        Returns:
            slope:     (B, 1, H, W) in radians
            roughness: (B, 1, H, W) local variance (m²)
        """
        gx = F.conv2d(elevation, self.Kx, padding=1)   # type: ignore[arg-type]
        gy = F.conv2d(elevation, self.Ky, padding=1)   # type: ignore[arg-type]
        slope = torch.atan(torch.sqrt(gx ** 2 + gy ** 2))

        # Roughness: local standard deviation via mean and mean-of-squares
        kernel = torch.ones(1, 1, 5, 5, device=elevation.device, dtype=elevation.dtype) / 25.0
        mu = F.conv2d(elevation, kernel, padding=2)
        mu2 = F.conv2d(elevation ** 2, kernel, padding=2)
        roughness = (mu2 - mu ** 2).clamp(min=0.0).sqrt()

        return slope, roughness


# ---------------------------------------------------------------------------
# Encoder block
# ---------------------------------------------------------------------------

class BEVEncoderBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, stride: int = 2) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, stride=stride, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
        )
        self.skip = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 1, stride=stride, bias=False),
            nn.BatchNorm2d(out_ch),
        ) if stride > 1 or in_ch != out_ch else nn.Identity()

    def forward(self, x: Tensor) -> Tensor:
        return self.conv(x) + self.skip(x)


# ---------------------------------------------------------------------------
# Decoder block with skip connection (U-Net style)
# ---------------------------------------------------------------------------

class BEVDecoderBlock(nn.Module):
    def __init__(self, in_ch: int, skip_ch: int, out_ch: int) -> None:
        super().__init__()
        self.up = nn.ConvTranspose2d(in_ch, in_ch // 2, kernel_size=2, stride=2)
        self.fuse = nn.Sequential(
            nn.Conv2d(in_ch // 2 + skip_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
        )

    def forward(self, x: Tensor, skip: Tensor) -> Tensor:
        x = self.up(x)
        if x.shape != skip.shape:
            x = F.interpolate(x, size=skip.shape[2:], mode="bilinear", align_corners=False)
        return self.fuse(torch.cat([x, skip], dim=1))


# ---------------------------------------------------------------------------
# Main model
# ---------------------------------------------------------------------------

class BEVTraversabilityNet(nn.Module):
    """
    U-Net style BEV traversability estimation.

    In addition to the learned encoder-decoder, the model fuses fixed
    physics-derived features (slope, roughness) at the bottleneck to ensure
    geometric safety constraints are always represented regardless of
    training data distribution.

    Args:
        in_channels:       BEV input channels (elevation, confidence, PSR, comms)
        base_ch:           base channel width (scales with depth)
        dropout:           spatial dropout rate in decoder (for MC Dropout use)
        max_safe_slope_deg: slope above which traversability is forced < 0.1
    """

    MAX_SAFE_SLOPE_DEG = 20.0  # degrees, hard-coded from rover spec

    def __init__(
        self,
        in_channels: int = IN_CHANNELS,
        base_ch: int = 32,
        dropout: float = 0.1,
        max_safe_slope_deg: float = MAX_SAFE_SLOPE_DEG,
    ) -> None:
        super().__init__()
        self.max_slope_rad = max_safe_slope_deg * (3.14159 / 180.0)

        self.slope_roughness = SlopeRoughnessExtractor(pixel_size=0.1)

        # Encoder:  BEV (B, in_ch+2, 200, 200) → ... → (B, 8*base_ch, 13, 13)
        in_ch_total = in_channels + 2          # +slope, +roughness
        self.enc1 = BEVEncoderBlock(in_ch_total, base_ch, stride=1)      # 200
        self.enc2 = BEVEncoderBlock(base_ch, base_ch * 2, stride=2)      # 100
        self.enc3 = BEVEncoderBlock(base_ch * 2, base_ch * 4, stride=2)  # 50
        self.enc4 = BEVEncoderBlock(base_ch * 4, base_ch * 8, stride=2)  # 25

        # Bottleneck
        self.bottleneck = nn.Sequential(
            nn.Conv2d(base_ch * 8, base_ch * 16, 3, padding=1, bias=False),
            nn.BatchNorm2d(base_ch * 16),
            nn.GELU(),
            nn.Dropout2d(dropout),
        )

        # Decoder with skip connections
        self.dec4 = BEVDecoderBlock(base_ch * 16, base_ch * 8, base_ch * 8)  # 25→50
        self.dec3 = BEVDecoderBlock(base_ch * 8, base_ch * 4, base_ch * 4)   # 50→100
        self.dec2 = BEVDecoderBlock(base_ch * 4, base_ch * 2, base_ch * 2)   # 100→200
        self.dec1 = BEVDecoderBlock(base_ch * 2, base_ch, base_ch)           # (200→200)

        self.out_conv = nn.Sequential(
            nn.Conv2d(base_ch, 16, 3, padding=1),
            nn.GELU(),
            nn.Conv2d(16, 1, 1),
            nn.Sigmoid(),
        )

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, (nn.Conv2d, nn.ConvTranspose2d)):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, bev: Tensor) -> Tensor:
        """
        Args:
            bev: (B, IN_CHANNELS, 200, 200)
                 ch0=elevation, ch1=confidence, ch2=psr_risk, ch3=comms_shadow

        Returns:
            traversability: (B, 1, 200, 200) in [0, 1]
        """
        elevation = bev[:, :1, :, :]
        slope, roughness = self.slope_roughness(elevation)

        # Concatenate physics features to input
        x = torch.cat([bev, slope, roughness], dim=1)

        # Encoder
        e1 = self.enc1(x)
        e2 = self.enc2(e1)
        e3 = self.enc3(e2)
        e4 = self.enc4(e3)

        # Bottleneck
        b = self.bottleneck(e4)

        # Decoder
        d4 = self.dec4(b, e4)
        d3 = self.dec3(d4, e3)
        d2 = self.dec2(d3, e2)
        d1 = self.dec1(d2, e1)

        trav = self.out_conv(d1)   # (B, 1, 200, 200) in [0,1]

        # Hard slope constraint: force traversability to near-zero for slopes > max_safe
        slope_penalty = (slope > self.max_slope_rad).float() * 0.95
        trav = trav * (1.0 - slope_penalty)

        return trav

    def to_nav2_costmap(self, trav: Tensor) -> Tensor:
        """
        Converts traversability [0,1] to Nav2 cost [0,254].

        0   = free space
        253 = near-lethal
        254 = lethal obstacle (traversability < 0.05)
        255 = unknown (not produced here)
        """
        cost = (1.0 - trav) * 253.0
        cost = cost.clamp(0, 253)
        lethal_mask = trav < 0.05
        cost[lethal_mask] = 254.0
        return cost.to(torch.uint8)

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_traversability_model(
    checkpoint: Optional[str] = None,
    device: str = "cpu",
) -> BEVTraversabilityNet:
    model = BEVTraversabilityNet()
    if checkpoint is not None:
        state = torch.load(checkpoint, map_location=device)
        model.load_state_dict(state["model_state_dict"])
    return model.to(device)


if __name__ == "__main__":
    model = BEVTraversabilityNet()
    bev = torch.randn(2, IN_CHANNELS, BEV_SIZE, BEV_SIZE)
    with torch.no_grad():
        trav = model(bev)
        cost = model.to_nav2_costmap(trav)
    print(f"BEV input:        {tuple(bev.shape)}")
    print(f"Traversability:   {tuple(trav.shape)}  range [{trav.min():.3f}, {trav.max():.3f}]")
    print(f"Nav2 costmap:     {tuple(cost.shape)}  range [{cost.min()}, {cost.max()}]")
    print(f"Parameters:       {model.count_parameters():,}")
