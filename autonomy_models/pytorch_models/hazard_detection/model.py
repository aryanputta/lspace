"""
Real-time hazard detection for NASA lunar rover autonomy.

YOLOv8-inspired single-stage detector with a custom CSPDarkNet backbone,
PANNet neck, and decoupled detection head. Targets >30 FPS on Jetson AGX Orin
in TensorRT FP16 mode.

Detections:
  0: boulder            — physical obstacle, avoid
  1: deep_crater        — high drop risk, avoid
  2: steep_slope_region — traverse with caution or reroute
  3: comms_obstruction  — line-of-sight blocker, plan around
"""

from __future__ import annotations

import math
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


NUM_HAZARD_CLASSES = 4
HAZARD_CLASS_NAMES = ["boulder", "deep_crater", "steep_slope_region", "comms_obstruction"]

# Detection anchors are not used (anchor-free, as in YOLOv8)
# Strides correspond to P3/P4/P5 feature map levels
STRIDES = [8, 16, 32]


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

class ConvBNSiLU(nn.Sequential):
    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        kernel_size: int = 3,
        stride: int = 1,
        padding: Optional[int] = None,
        groups: int = 1,
        dilation: int = 1,
    ) -> None:
        if padding is None:
            padding = (kernel_size // 2) * dilation
        super().__init__(
            nn.Conv2d(
                in_ch, out_ch, kernel_size, stride=stride,
                padding=padding, groups=groups, dilation=dilation, bias=False,
            ),
            nn.BatchNorm2d(out_ch, momentum=0.03, eps=1e-3),
            nn.SiLU(inplace=True),
        )


class Bottleneck(nn.Module):
    """Standard residual bottleneck as used in YOLOv8 C2f."""

    def __init__(self, ch: int, shortcut: bool = True, expansion: float = 0.5) -> None:
        super().__init__()
        hidden = int(ch * expansion)
        self.cv1 = ConvBNSiLU(ch, hidden, kernel_size=3)
        self.cv2 = ConvBNSiLU(hidden, ch, kernel_size=3)
        self.use_residual = shortcut

    def forward(self, x: Tensor) -> Tensor:
        return x + self.cv2(self.cv1(x)) if self.use_residual else self.cv2(self.cv1(x))


class C2f(nn.Module):
    """
    CSP-style module with n bottlenecks.

    Splits features into two paths, processes one through stacked bottlenecks,
    then concatenates all intermediate features before projection.
    This increases gradient flow while controlling parameter count.
    """

    def __init__(self, in_ch: int, out_ch: int, n: int = 1, shortcut: bool = True) -> None:
        super().__init__()
        hidden = out_ch // 2
        self.cv1 = ConvBNSiLU(in_ch, 2 * hidden, kernel_size=1, padding=0)
        self.bottlenecks = nn.ModuleList(
            [Bottleneck(hidden, shortcut=shortcut) for _ in range(n)]
        )
        self.cv2 = ConvBNSiLU((2 + n) * hidden, out_ch, kernel_size=1, padding=0)

    def forward(self, x: Tensor) -> Tensor:
        y = list(self.cv1(x).chunk(2, dim=1))
        for bn in self.bottlenecks:
            y.append(bn(y[-1]))
        return self.cv2(torch.cat(y, dim=1))


class SPPF(nn.Module):
    """
    Spatial Pyramid Pooling - Fast.

    Three sequential 5x5 max-pools approximate multi-scale pooling with
    minimal latency — important for sub-50ms target on Orin.
    """

    def __init__(self, in_ch: int, out_ch: int, pool_size: int = 5) -> None:
        super().__init__()
        hidden = in_ch // 2
        self.cv1 = ConvBNSiLU(in_ch, hidden, kernel_size=1, padding=0)
        self.pool = nn.MaxPool2d(pool_size, stride=1, padding=pool_size // 2)
        self.cv2 = ConvBNSiLU(hidden * 4, out_ch, kernel_size=1, padding=0)

    def forward(self, x: Tensor) -> Tensor:
        x = self.cv1(x)
        p1 = self.pool(x)
        p2 = self.pool(p1)
        p3 = self.pool(p2)
        return self.cv2(torch.cat([x, p1, p2, p3], dim=1))


# ---------------------------------------------------------------------------
# CSPDarkNet backbone
# ---------------------------------------------------------------------------
# Produces feature maps P3 (stride 8), P4 (stride 16), P5 (stride 32)

class CSPDarkNet(nn.Module):
    def __init__(self, in_channels: int = 3, width_mult: float = 0.5) -> None:
        super().__init__()

        def w(x: int) -> int:
            return max(int(x * width_mult), 1)

        # Stem: 3 → 32 (stride 2)
        self.stem = ConvBNSiLU(in_channels, w(64), kernel_size=3, stride=2)

        # Stage 1: stride 4
        self.stage1 = nn.Sequential(
            ConvBNSiLU(w(64), w(128), kernel_size=3, stride=2),
            C2f(w(128), w(128), n=3, shortcut=True),
        )

        # Stage 2: stride 8 (P3)
        self.stage2 = nn.Sequential(
            ConvBNSiLU(w(128), w(256), kernel_size=3, stride=2),
            C2f(w(256), w(256), n=6, shortcut=True),
        )

        # Stage 3: stride 16 (P4)
        self.stage3 = nn.Sequential(
            ConvBNSiLU(w(256), w(512), kernel_size=3, stride=2),
            C2f(w(512), w(512), n=6, shortcut=True),
        )

        # Stage 4: stride 32 (P5) + SPPF
        self.stage4 = nn.Sequential(
            ConvBNSiLU(w(512), w(1024), kernel_size=3, stride=2),
            C2f(w(1024), w(1024), n=3, shortcut=True),
            SPPF(w(1024), w(1024)),
        )

        self.out_channels = (w(256), w(512), w(1024))

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        x = self.stem(x)
        x = self.stage1(x)
        p3 = self.stage2(x)
        p4 = self.stage3(p3)
        p5 = self.stage4(p4)
        return p3, p4, p5


# ---------------------------------------------------------------------------
# PANNet neck (Path Aggregation Network)
# ---------------------------------------------------------------------------

class PANNeck(nn.Module):
    """
    Bidirectional feature fusion: top-down (FPN) then bottom-up (PAN).
    Fuses P3/P4/P5 into three output scales for multi-scale detection.
    """

    def __init__(self, in_channels: tuple[int, int, int]) -> None:
        super().__init__()
        c3, c4, c5 = in_channels

        # Top-down
        self.td_p5_proj = ConvBNSiLU(c5, c4, kernel_size=1, padding=0)
        self.td_p4_fuse = C2f(c4 * 2, c4, n=3, shortcut=False)
        self.td_p4_proj = ConvBNSiLU(c4, c3, kernel_size=1, padding=0)
        self.td_p3_fuse = C2f(c3 * 2, c3, n=3, shortcut=False)

        # Bottom-up
        self.bu_p3_down = ConvBNSiLU(c3, c3, kernel_size=3, stride=2)
        self.bu_p4_fuse = C2f(c3 + c3, c4, n=3, shortcut=False)
        self.bu_p4_down = ConvBNSiLU(c4, c4, kernel_size=3, stride=2)
        self.bu_p5_fuse = C2f(c4 + c4, c5, n=3, shortcut=False)

        self.out_channels = (c3, c4, c5)

    def forward(
        self, features: tuple[Tensor, Tensor, Tensor]
    ) -> tuple[Tensor, Tensor, Tensor]:
        p3, p4, p5 = features

        # Top-down path
        p5_td = self.td_p5_proj(p5)
        p4_in = torch.cat(
            [F.interpolate(p5_td, size=p4.shape[2:], mode="nearest"), p4], dim=1
        )
        p4_td = self.td_p4_fuse(p4_in)

        p4_proj = self.td_p4_proj(p4_td)
        p3_in = torch.cat(
            [F.interpolate(p4_proj, size=p3.shape[2:], mode="nearest"), p3], dim=1
        )
        n3 = self.td_p3_fuse(p3_in)

        # Bottom-up path
        p4_in2 = torch.cat([self.bu_p3_down(n3), p4_td], dim=1)
        n4 = self.bu_p4_fuse(p4_in2)

        p5_in2 = torch.cat([self.bu_p4_down(n4), p5], dim=1)
        n5 = self.bu_p5_fuse(p5_in2)

        return n3, n4, n5


# ---------------------------------------------------------------------------
# Decoupled detection head
# ---------------------------------------------------------------------------

class DetectionHead(nn.Module):
    """
    Separate regression and classification branches per scale,
    following YOLOv8 convention.

    Each spatial location predicts:
      - 4 box parameters (cx, cy, w, h) relative to grid cell, normalised by stride
      - num_classes objectness-free class logits (binary cross-entropy per class)
    """

    def __init__(self, in_ch: int, num_classes: int, reg_max: int = 16) -> None:
        super().__init__()
        self.num_classes = num_classes
        self.reg_max = reg_max

        self.cls_branch = nn.Sequential(
            ConvBNSiLU(in_ch, in_ch, kernel_size=3),
            ConvBNSiLU(in_ch, in_ch, kernel_size=3),
            nn.Conv2d(in_ch, num_classes, kernel_size=1),
        )
        # Distribution Focal Loss (DFL) regression: 4 * reg_max outputs
        self.reg_branch = nn.Sequential(
            ConvBNSiLU(in_ch, in_ch, kernel_size=3),
            ConvBNSiLU(in_ch, in_ch, kernel_size=3),
            nn.Conv2d(in_ch, 4 * reg_max, kernel_size=1),
        )

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
        cls_logits = self.cls_branch(x)             # (B, num_classes, H, W)
        reg_dist = self.reg_branch(x)               # (B, 4*reg_max, H, W)
        return cls_logits, reg_dist


# ---------------------------------------------------------------------------
# DFL decode: dist -> ltrb
# ---------------------------------------------------------------------------

def dist2bbox(
    dist: Tensor,
    anchor_points: Tensor,
    reg_max: int = 16,
    stride: float = 1.0,
) -> Tensor:
    """
    Decode DFL distribution into (cx, cy, w, h) boxes in pixel space.

    dist: (B, 4*reg_max, H, W)
    anchor_points: (H*W, 2) grid centres
    """
    B, _, H, W = dist.shape
    dist = dist.permute(0, 2, 3, 1).reshape(B, H * W, 4, reg_max)
    dist = F.softmax(dist, dim=-1)
    proj = torch.arange(reg_max, dtype=dist.dtype, device=dist.device)
    ltrb = (dist * proj).sum(-1)                         # (B, H*W, 4)

    lt = ltrb[..., :2]
    rb = ltrb[..., 2:]
    x1y1 = anchor_points - lt
    x2y2 = anchor_points + rb
    cx = (x1y1[..., 0] + x2y2[..., 0]) / 2.0
    cy = (x1y1[..., 1] + x2y2[..., 1]) / 2.0
    w = x2y2[..., 0] - x1y1[..., 0]
    h = x2y2[..., 1] - x1y1[..., 1]
    return torch.stack([cx, cy, w, h], dim=-1) * stride  # pixel coords


def make_anchor_grid(height: int, width: int, stride: int, device: torch.device) -> Tensor:
    gy, gx = torch.meshgrid(
        torch.arange(height, dtype=torch.float32, device=device),
        torch.arange(width, dtype=torch.float32, device=device),
        indexing="ij",
    )
    anchors = torch.stack([gx + 0.5, gy + 0.5], dim=-1).reshape(-1, 2)
    return anchors


# ---------------------------------------------------------------------------
# NMS post-processing
# ---------------------------------------------------------------------------

def batched_nms(
    boxes: Tensor,
    scores: Tensor,
    class_ids: Tensor,
    iou_threshold: float = 0.45,
) -> Tensor:
    """Returns kept indices after class-aware NMS."""
    if boxes.numel() == 0:
        return torch.zeros(0, dtype=torch.long, device=boxes.device)
    offset = class_ids.float() * (boxes.max() + 1)
    boxes_shifted = boxes + offset.unsqueeze(1)
    x1 = boxes_shifted[:, 0] - boxes_shifted[:, 2] / 2
    y1 = boxes_shifted[:, 1] - boxes_shifted[:, 3] / 2
    x2 = boxes_shifted[:, 0] + boxes_shifted[:, 2] / 2
    y2 = boxes_shifted[:, 1] + boxes_shifted[:, 3] / 2
    boxes_xyxy = torch.stack([x1, y1, x2, y2], dim=1)
    return torch.ops.torchvision.nms(boxes_xyxy, scores, iou_threshold)


# ---------------------------------------------------------------------------
# Full detector
# ---------------------------------------------------------------------------

class LunarHazardDetector(nn.Module):
    """
    Anchor-free single-stage hazard detector.

    Input:  (B, 3, 640, 640) normalised RGB
    Output (training): list of (cls_logits, reg_dist) per FPN level
    Output (inference, post_process=True): list of dicts with
        'boxes'     : (N, 4) cx cy w h in pixel coords
        'scores'    : (N,)   confidence
        'class_ids' : (N,)   int class labels

    Args:
        num_classes:   number of hazard classes (default 4)
        width_mult:    backbone channel multiplier (0.5 = YOLOv8n scale)
        conf_thresh:   confidence threshold for post-processing
        iou_thresh:    NMS IoU threshold
        reg_max:       DFL distribution bins
    """

    def __init__(
        self,
        num_classes: int = NUM_HAZARD_CLASSES,
        width_mult: float = 0.5,
        conf_thresh: float = 0.25,
        iou_thresh: float = 0.45,
        reg_max: int = 16,
    ) -> None:
        super().__init__()
        self.num_classes = num_classes
        self.conf_thresh = conf_thresh
        self.iou_thresh = iou_thresh
        self.reg_max = reg_max
        self.strides = STRIDES

        self.backbone = CSPDarkNet(in_channels=3, width_mult=width_mult)
        self.neck = PANNeck(self.backbone.out_channels)

        self.heads = nn.ModuleList(
            [DetectionHead(ch, num_classes, reg_max)
             for ch in self.neck.out_channels]
        )

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
        # Bias init for classification branches: prior probability 0.01
        prior_prob = 0.01
        bias_value = -math.log((1 - prior_prob) / prior_prob)
        for head in self.heads:
            last_cls = head.cls_branch[-1]
            if isinstance(last_cls, nn.Conv2d) and last_cls.bias is not None:
                nn.init.constant_(last_cls.bias, bias_value)

    def forward(
        self, x: Tensor, post_process: bool = False
    ) -> list[tuple[Tensor, Tensor]] | list[dict[str, Tensor]]:
        p3, p4, p5 = self.backbone(x)
        n3, n4, n5 = self.neck((p3, p4, p5))

        raw_outputs: list[tuple[Tensor, Tensor]] = []
        for feat, head in zip([n3, n4, n5], self.heads):
            raw_outputs.append(head(feat))

        if not post_process:
            return raw_outputs

        return self._decode_and_filter(raw_outputs, input_hw=x.shape[2:], device=x.device)

    def _decode_and_filter(
        self,
        raw_outputs: list[tuple[Tensor, Tensor]],
        input_hw: tuple[int, int],
        device: torch.device,
    ) -> list[dict[str, Tensor]]:
        B = raw_outputs[0][0].shape[0]
        all_boxes = []
        all_scores = []
        all_class_ids = []

        for (cls_logits, reg_dist), stride in zip(raw_outputs, self.strides):
            H, W = cls_logits.shape[2], cls_logits.shape[3]
            anchors = make_anchor_grid(H, W, stride, device)  # (H*W, 2)

            # Per-class sigmoid scores
            cls_scores = cls_logits.sigmoid()  # (B, num_cls, H, W)
            cls_scores = cls_scores.permute(0, 2, 3, 1).reshape(B, H * W, self.num_classes)

            boxes = dist2bbox(reg_dist, anchors, self.reg_max, stride=float(stride))  # (B, H*W, 4)

            conf, cls_id = cls_scores.max(-1)  # (B, H*W)
            all_boxes.append(boxes)
            all_scores.append(conf)
            all_class_ids.append(cls_id)

        all_boxes = torch.cat(all_boxes, dim=1)      # (B, total_anchors, 4)
        all_scores = torch.cat(all_scores, dim=1)    # (B, total_anchors)
        all_class_ids = torch.cat(all_class_ids, dim=1)

        results: list[dict[str, Tensor]] = []
        for b in range(B):
            scores_b = all_scores[b]
            keep_mask = scores_b > self.conf_thresh

            boxes_b = all_boxes[b][keep_mask]
            scores_b = scores_b[keep_mask]
            cls_b = all_class_ids[b][keep_mask]

            if boxes_b.numel() > 0:
                kept = batched_nms(boxes_b, scores_b, cls_b, self.iou_thresh)
                boxes_b = boxes_b[kept]
                scores_b = scores_b[kept]
                cls_b = cls_b[kept]

            results.append({"boxes": boxes_b, "scores": scores_b, "class_ids": cls_b})

        return results

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_hazard_detector(
    num_classes: int = NUM_HAZARD_CLASSES,
    width_mult: float = 0.5,
    conf_thresh: float = 0.25,
    iou_thresh: float = 0.45,
    checkpoint: Optional[str] = None,
    device: str = "cpu",
) -> LunarHazardDetector:
    model = LunarHazardDetector(
        num_classes=num_classes,
        width_mult=width_mult,
        conf_thresh=conf_thresh,
        iou_thresh=iou_thresh,
    )
    if checkpoint is not None:
        state = torch.load(checkpoint, map_location=device)
        model.load_state_dict(state["model_state_dict"])
    return model.to(device)


if __name__ == "__main__":
    model = LunarHazardDetector(num_classes=4, width_mult=0.5)
    model.eval()
    x = torch.randn(1, 3, 640, 640)
    with torch.no_grad():
        preds = model(x, post_process=True)
    print(f"Parameters: {model.count_parameters():,}")
    print(f"Detections in sample 0: {len(preds[0]['boxes'])}")
    raw = model(x, post_process=False)
    for i, (cls, reg) in enumerate(raw):
        print(f"  Scale {STRIDES[i]:2d}: cls={tuple(cls.shape)}  reg={tuple(reg.shape)}")
