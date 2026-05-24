"""
Terrain segmentation model for NASA lunar rover autonomy.

DeepLabV3+ with MobileNetV3-Large backbone, adapted for 4-channel input
(RGB + optional thermal IR) and 8-class lunar terrain output.

Target: <50ms inference on Jetson AGX Orin (TensorRT FP16).
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from typing import Optional


# ---------------------------------------------------------------------------
# Class definitions
# ---------------------------------------------------------------------------

TERRAIN_CLASSES = {
    0: "flat_regolith",
    1: "rocky_terrain",
    2: "crater_rim",
    3: "crater_interior",
    4: "boulder",
    5: "shadowed_psr",
    6: "sunlit_safe",
    7: "comms_shadow",
}
NUM_CLASSES = 8


# ---------------------------------------------------------------------------
# Utility blocks
# ---------------------------------------------------------------------------

class ConvBNReLU(nn.Sequential):
    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        kernel_size: int = 3,
        stride: int = 1,
        padding: int = 1,
        groups: int = 1,
        dilation: int = 1,
    ) -> None:
        padding = dilation if dilation > 1 else padding
        super().__init__(
            nn.Conv2d(
                in_ch, out_ch, kernel_size, stride=stride,
                padding=padding, groups=groups, dilation=dilation, bias=False,
            ),
            nn.BatchNorm2d(out_ch, momentum=0.01, eps=1e-3),
            nn.ReLU6(inplace=True),
        )


class DepthwiseSeparable(nn.Sequential):
    def __init__(self, in_ch: int, out_ch: int, stride: int = 1) -> None:
        super().__init__(
            ConvBNReLU(in_ch, in_ch, 3, stride=stride, groups=in_ch),
            ConvBNReLU(in_ch, out_ch, 1, padding=0),
        )


# ---------------------------------------------------------------------------
# Squeeze-and-Excitation attention (channel attention)
# ---------------------------------------------------------------------------

class SEBlock(nn.Module):
    def __init__(self, channels: int, reduction: int = 4) -> None:
        super().__init__()
        reduced = max(channels // reduction, 8)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Linear(channels, reduced, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(reduced, channels, bias=False),
            nn.Hardsigmoid(inplace=True),
        )

    def forward(self, x: Tensor) -> Tensor:
        b, c, _, _ = x.shape
        s = self.pool(x).view(b, c)
        s = self.fc(s).view(b, c, 1, 1)
        return x * s


# ---------------------------------------------------------------------------
# MobileNetV3 inverted residual bottleneck
# ---------------------------------------------------------------------------

class InvertedResidual(nn.Module):
    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        kernel_size: int,
        stride: int,
        expand_ratio: int,
        use_se: bool,
        dilation: int = 1,
    ) -> None:
        super().__init__()
        self.use_res = stride == 1 and in_ch == out_ch
        hidden = int(in_ch * expand_ratio)

        layers: list[nn.Module] = []
        if expand_ratio != 1:
            layers.append(ConvBNReLU(in_ch, hidden, 1, padding=0))

        layers.append(
            ConvBNReLU(
                hidden, hidden, kernel_size,
                stride=stride, groups=hidden, dilation=dilation,
                padding=dilation if dilation > 1 else kernel_size // 2,
            )
        )
        if use_se:
            layers.append(SEBlock(hidden))

        layers.append(nn.Conv2d(hidden, out_ch, 1, bias=False))
        layers.append(nn.BatchNorm2d(out_ch, momentum=0.01, eps=1e-3))

        self.block = nn.Sequential(*layers)

    def forward(self, x: Tensor) -> Tensor:
        out = self.block(x)
        if self.use_res:
            out = out + x
        return out


# ---------------------------------------------------------------------------
# MobileNetV3-Large backbone (stride-16 output for DeepLab)
# ---------------------------------------------------------------------------
# We produce two feature maps:
#   low_level  – after stage 2 (stride 4, 24 channels)
#   high_level – after stage 5 (stride 16, with last two stages using
#                dilation=2 to preserve resolution at cost of receptive field)

_BACKBONE_CFG = [
    # (in, out, k, s, expand, se)
    (16,  16,  3, 1, 1,  False),   # stage 1
    (16,  24,  3, 2, 4,  False),   # stage 2 → stride 4  (low-level)
    (24,  24,  3, 1, 3,  False),
    (24,  40,  5, 2, 3,  True),    # stage 3 → stride 8
    (40,  40,  5, 1, 3,  True),
    (40,  40,  5, 1, 3,  True),
    (40,  80,  3, 2, 6,  False),   # stage 4 → stride 16 (high-level start)
    (80,  80,  3, 1, 2,  False),
    (80,  80,  3, 1, 2,  False),
    (80,  80,  3, 1, 2,  False),
    (80,  112, 5, 1, 6,  True),
    (112, 112, 5, 1, 6,  True),
    (112, 160, 5, 1, 6,  True),    # stage 5 → kept at stride 16 via dilation
    (160, 160, 5, 1, 6,  True),
    (160, 160, 5, 1, 6,  True),
]

_LOW_LEVEL_IDX = 2   # output after stage 2 (stride 4)
_HIGH_LEVEL_IDX = 14  # final stage


class MobileNetV3Backbone(nn.Module):
    def __init__(self, in_channels: int = 3) -> None:
        super().__init__()
        self.stem = ConvBNReLU(in_channels, 16, 3, stride=2, padding=1)
        self.layers = nn.ModuleList()
        for i, (inc, outc, k, s, exp, se) in enumerate(_BACKBONE_CFG):
            # Stages 12-14 replace stride-2 with dilation to keep stride-16
            dil = 2 if i >= 12 else 1
            stride = 1 if i >= 12 else s
            self.layers.append(
                InvertedResidual(inc, outc, k, stride, exp, se, dilation=dil)
            )

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
        x = self.stem(x)
        low_level: Optional[Tensor] = None
        for i, layer in enumerate(self.layers):
            x = layer(x)
            if i == _LOW_LEVEL_IDX:
                low_level = x
        return low_level, x  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Atrous Spatial Pyramid Pooling (ASPP)
# ---------------------------------------------------------------------------

class ASPP(nn.Module):
    def __init__(self, in_ch: int = 160, out_ch: int = 256) -> None:
        super().__init__()
        self.conv1x1 = ConvBNReLU(in_ch, out_ch, 1, padding=0)
        self.dilated6 = ConvBNReLU(in_ch, out_ch, 3, dilation=6, padding=6)
        self.dilated12 = ConvBNReLU(in_ch, out_ch, 3, dilation=12, padding=12)
        self.dilated18 = ConvBNReLU(in_ch, out_ch, 3, dilation=18, padding=18)
        self.pool = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(in_ch, out_ch, 1, bias=False),
            nn.BatchNorm2d(out_ch, momentum=0.01, eps=1e-3),
            nn.ReLU(inplace=True),
        )
        self.project = ConvBNReLU(out_ch * 5, out_ch, 1, padding=0)
        self.dropout = nn.Dropout2d(0.1)

    def forward(self, x: Tensor) -> Tensor:
        _, _, h, w = x.shape
        pooled = F.interpolate(self.pool(x), size=(h, w), mode="bilinear", align_corners=False)
        feats = torch.cat(
            [self.conv1x1(x), self.dilated6(x), self.dilated12(x),
             self.dilated18(x), pooled],
            dim=1,
        )
        return self.dropout(self.project(feats))


# ---------------------------------------------------------------------------
# Spatial attention gate (applied on skip connections)
# ---------------------------------------------------------------------------

class SpatialAttention(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.conv = nn.Conv2d(2, 1, kernel_size=7, padding=3, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: Tensor) -> Tensor:
        avg = x.mean(dim=1, keepdim=True)
        mx = x.amax(dim=1, keepdim=True)
        att = self.sigmoid(self.conv(torch.cat([avg, mx], dim=1)))
        return x * att


# ---------------------------------------------------------------------------
# DeepLabV3+ decoder
# ---------------------------------------------------------------------------

class DeepLabV3PlusDecoder(nn.Module):
    def __init__(self, low_level_ch: int = 24, aspp_ch: int = 256) -> None:
        super().__init__()
        # Project low-level features to 48 channels (standard ratio)
        self.low_project = ConvBNReLU(low_level_ch, 48, 1, padding=0)
        self.spatial_att = SpatialAttention()
        self.fuse = nn.Sequential(
            ConvBNReLU(aspp_ch + 48, 256, 3, padding=1),
            nn.Dropout2d(0.1),
            ConvBNReLU(256, 256, 3, padding=1),
        )

    def forward(self, low: Tensor, aspp: Tensor) -> Tensor:
        low = self.low_project(low)
        low = self.spatial_att(low)
        aspp_up = F.interpolate(aspp, size=low.shape[2:], mode="bilinear", align_corners=False)
        return self.fuse(torch.cat([aspp_up, low], dim=1))


# ---------------------------------------------------------------------------
# Full model
# ---------------------------------------------------------------------------

class LunarTerrainSegmentation(nn.Module):
    """
    DeepLabV3+ with MobileNetV3-Large backbone for 8-class lunar terrain
    segmentation.

    Args:
        in_channels: 3 (RGB) or 4 (RGB + thermal IR).
        num_classes: number of output segmentation classes.
        pretrained_backbone: unused at runtime; flag for training scripts.
    """

    def __init__(
        self,
        in_channels: int = 4,
        num_classes: int = NUM_CLASSES,
    ) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.num_classes = num_classes

        self.backbone = MobileNetV3Backbone(in_channels=in_channels)
        self.aspp = ASPP(in_ch=160, out_ch=256)
        self.decoder = DeepLabV3PlusDecoder(low_level_ch=24, aspp_ch=256)
        self.classifier = nn.Conv2d(256, num_classes, 1)

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.trunc_normal_(m.weight, std=0.02)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: Tensor) -> Tensor:
        """
        Args:
            x: (B, C, H, W) where C=3 or 4, H=480, W=640.

        Returns:
            logits: (B, num_classes, H, W) — same spatial resolution as input.
        """
        _, _, h, w = x.shape
        low, high = self.backbone(x)
        aspp_out = self.aspp(high)
        decoded = self.decoder(low, aspp_out)
        logits = self.classifier(decoded)
        return F.interpolate(logits, size=(h, w), mode="bilinear", align_corners=False)

    @torch.no_grad()
    def predict(self, x: Tensor) -> tuple[Tensor, Tensor]:
        """Returns (class_map, confidence_map) from softmax probabilities."""
        probs = F.softmax(self(x), dim=1)
        conf, cls = probs.max(dim=1)
        return cls, conf

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

def build_terrain_segmentation_model(
    in_channels: int = 4,
    num_classes: int = NUM_CLASSES,
    checkpoint: Optional[str] = None,
    device: str = "cpu",
) -> LunarTerrainSegmentation:
    model = LunarTerrainSegmentation(in_channels=in_channels, num_classes=num_classes)
    if checkpoint is not None:
        state = torch.load(checkpoint, map_location=device)
        model.load_state_dict(state["model_state_dict"])
    return model.to(device)


if __name__ == "__main__":
    model = LunarTerrainSegmentation(in_channels=4, num_classes=8)
    x = torch.randn(1, 4, 480, 640)
    with torch.no_grad():
        out = model(x)
    print(f"Output shape: {out.shape}")           # (1, 8, 480, 640)
    print(f"Parameters: {model.count_parameters():,}")
