"""
Wheel slip prediction model for NASA lunar rover autonomy.

Temporal CNN + LSTM hybrid that processes 10-timestep sequences of
rover state (wheel velocities, IMU, terrain type, motor torques, inclination)
to predict per-wheel slip ratio and epistemic uncertainty via MC Dropout.

Architecture rationale:
  - Temporal CNN extracts short-range dynamics (wheel vibration signatures)
  - LSTM captures longer-term terrain-induced slip patterns
  - MC Dropout provides calibrated uncertainty used by the planner to
    conservatively cap speed when slip prediction is unreliable
"""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
from torch import Tensor


NUM_WHEELS = 6
TERRAIN_CLASSES = 8
SEQ_LEN = 10

# Input feature breakdown per timestep:
#   wheel_angular_vel:   6   (rad/s, one per wheel)
#   imu_accel:           3   (ax, ay, az  m/s²)
#   imu_gyro:            3   (wx, wy, wz  rad/s)
#   terrain_onehot:      8   (from segmentation model)
#   motor_torques:       6   (Nm, one per wheel)
#   surface_inclination: 1   (degrees, from SLAM)
INPUT_DIM = 6 + 3 + 3 + TERRAIN_CLASSES + 6 + 1  # = 27


# ---------------------------------------------------------------------------
# Temporal convolutional block
# ---------------------------------------------------------------------------

class TCNBlock(nn.Module):
    """
    Causal dilated 1-D convolution with residual connection.

    Dilation grows exponentially to cover longer temporal context without
    increasing parameter count linearly.
    """

    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        kernel_size: int = 3,
        dilation: int = 1,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        pad = (kernel_size - 1) * dilation  # causal: only pad left
        self.conv1 = nn.Conv1d(
            in_ch, out_ch, kernel_size,
            padding=pad, dilation=dilation,
        )
        self.norm1 = nn.BatchNorm1d(out_ch)
        self.conv2 = nn.Conv1d(
            out_ch, out_ch, kernel_size,
            padding=pad, dilation=dilation,
        )
        self.norm2 = nn.BatchNorm1d(out_ch)
        self.act = nn.GELU()
        self.dropout = nn.Dropout(dropout)
        self.pad = pad

        self.residual = (
            nn.Conv1d(in_ch, out_ch, 1) if in_ch != out_ch else nn.Identity()
        )

    def forward(self, x: Tensor) -> Tensor:
        # x: (B, C, T)
        r = self.residual(x)

        x = self.conv1(x)
        if self.pad > 0:
            x = x[:, :, : -self.pad]   # remove right padding to keep causality
        x = self.act(self.norm1(x))
        x = self.dropout(x)

        x = self.conv2(x)
        if self.pad > 0:
            x = x[:, :, : -self.pad]
        x = self.act(self.norm2(x))
        x = self.dropout(x)

        return x + r


class TemporalCNN(nn.Module):
    """Stack of TCN blocks covering up to 10-step context."""

    def __init__(
        self,
        input_dim: int = INPUT_DIM,
        hidden_dim: int = 64,
        num_blocks: int = 4,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        blocks: list[nn.Module] = [TCNBlock(input_dim, hidden_dim, dilation=1, dropout=dropout)]
        for i in range(1, num_blocks):
            dilation = 2 ** i
            blocks.append(TCNBlock(hidden_dim, hidden_dim, dilation=dilation, dropout=dropout))
        self.blocks = nn.Sequential(*blocks)
        self.out_dim = hidden_dim

    def forward(self, x: Tensor) -> Tensor:
        # x: (B, T, F) → (B, F, T) for Conv1d
        return self.blocks(x.permute(0, 2, 1)).permute(0, 2, 1)  # → (B, T, hidden)


# ---------------------------------------------------------------------------
# Wheel attention: focus on high-slip wheels
# ---------------------------------------------------------------------------

class WheelAttention(nn.Module):
    """
    Learned attention over the 6 wheel positions.
    Allows the model to weight wheel contributions contextually —
    e.g. uphill wheels may matter more in slope traversal.
    """

    def __init__(self, context_dim: int, num_wheels: int = NUM_WHEELS) -> None:
        super().__init__()
        self.att = nn.Linear(context_dim, num_wheels)

    def forward(self, context: Tensor) -> Tensor:
        # context: (B, context_dim)
        return torch.softmax(self.att(context), dim=-1)  # (B, NUM_WHEELS)


# ---------------------------------------------------------------------------
# Full model
# ---------------------------------------------------------------------------

class WheelSlipPredictor(nn.Module):
    """
    Temporal CNN + LSTM for per-wheel slip prediction with uncertainty.

    Args:
        input_dim:       feature dimension per timestep (default 27)
        tcn_hidden:      TCN channel width
        tcn_blocks:      number of TCN dilation blocks
        lstm_hidden:     LSTM hidden size
        lstm_layers:     stacked LSTM depth
        num_wheels:      number of rover wheels (default 6)
        mc_dropout_rate: MC Dropout rate used during inference for uncertainty
    """

    def __init__(
        self,
        input_dim: int = INPUT_DIM,
        tcn_hidden: int = 64,
        tcn_blocks: int = 4,
        lstm_hidden: int = 128,
        lstm_layers: int = 2,
        num_wheels: int = NUM_WHEELS,
        mc_dropout_rate: float = 0.2,
    ) -> None:
        super().__init__()
        self.num_wheels = num_wheels
        self.mc_dropout_rate = mc_dropout_rate

        # Input normalisation (learned per-feature)
        self.input_norm = nn.LayerNorm(input_dim)

        # Temporal feature extraction
        self.tcn = TemporalCNN(input_dim, tcn_hidden, tcn_blocks, dropout=mc_dropout_rate)

        # Sequence modelling
        self.lstm = nn.LSTM(
            input_size=tcn_hidden,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            dropout=mc_dropout_rate if lstm_layers > 1 else 0.0,
        )

        # MC Dropout layer — active during both training AND inference
        self.mc_drop = nn.Dropout(mc_dropout_rate)

        # Per-wheel slip head
        self.wheel_attention = WheelAttention(lstm_hidden, num_wheels)
        self.slip_head = nn.Sequential(
            nn.Linear(lstm_hidden, 64),
            nn.GELU(),
            nn.Linear(64, num_wheels),
            nn.Sigmoid(),   # slip ratio in [0, 1]
        )

        # Uncertainty head (log-variance)
        self.uncertainty_head = nn.Sequential(
            nn.Linear(lstm_hidden, 64),
            nn.GELU(),
            nn.Linear(64, num_wheels),
        )

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, (nn.LSTM,)):
                for name, param in m.named_parameters():
                    if "weight" in name:
                        nn.init.orthogonal_(param)
                    elif "bias" in name:
                        nn.init.zeros_(param)

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
        """
        Args:
            x: (B, T, input_dim) where T=SEQ_LEN=10

        Returns:
            slip:        (B, num_wheels) predicted slip ratio in [0,1]
            log_var:     (B, num_wheels) log-variance for uncertainty estimation
        """
        x = self.input_norm(x)
        tcn_out = self.tcn(x)                           # (B, T, tcn_hidden)
        lstm_out, _ = self.lstm(tcn_out)                # (B, T, lstm_hidden)
        h = self.mc_drop(lstm_out[:, -1, :])            # last timestep + MC Dropout

        slip = self.slip_head(h)
        log_var = self.uncertainty_head(h)
        return slip, log_var

    @torch.no_grad()
    def predict_with_uncertainty(
        self, x: Tensor, n_samples: int = 30
    ) -> tuple[Tensor, Tensor, Tensor]:
        """
        Run MC Dropout inference to estimate epistemic uncertainty.

        Forces dropout active regardless of model.eval() state.

        Returns:
            slip_mean:  (B, num_wheels)  mean predicted slip
            slip_std:   (B, num_wheels)  std dev (epistemic uncertainty)
            total_std:  (B, num_wheels)  combined epistemic + aleatoric std
        """
        self.train()   # activates dropout
        slip_samples = []
        logvar_samples = []
        for _ in range(n_samples):
            slip, log_var = self.forward(x)
            slip_samples.append(slip.unsqueeze(0))
            logvar_samples.append(log_var.unsqueeze(0))

        self.eval()
        slip_stack = torch.cat(slip_samples, dim=0)        # (n_samples, B, W)
        logvar_stack = torch.cat(logvar_samples, dim=0)

        slip_mean = slip_stack.mean(0)
        slip_std = slip_stack.std(0)                       # epistemic
        aleatoric_var = logvar_stack.exp().mean(0)
        total_std = (slip_std ** 2 + aleatoric_var).sqrt()

        return slip_mean, slip_std, total_std

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_wheel_slip_model(
    checkpoint: Optional[str] = None,
    device: str = "cpu",
    mc_dropout_rate: float = 0.2,
) -> WheelSlipPredictor:
    model = WheelSlipPredictor(mc_dropout_rate=mc_dropout_rate)
    if checkpoint is not None:
        state = torch.load(checkpoint, map_location=device)
        model.load_state_dict(state["model_state_dict"])
    return model.to(device)


if __name__ == "__main__":
    model = WheelSlipPredictor()
    x = torch.randn(4, SEQ_LEN, INPUT_DIM)
    slip, log_var = model(x)
    print(f"Input:       {tuple(x.shape)}")
    print(f"Slip out:    {tuple(slip.shape)}")
    print(f"LogVar out:  {tuple(log_var.shape)}")
    print(f"Parameters:  {model.count_parameters():,}")

    slip_m, slip_s, total_s = model.predict_with_uncertainty(x, n_samples=10)
    print(f"MC mean:     {tuple(slip_m.shape)}")
    print(f"MC std:      {tuple(slip_s.shape)}")
