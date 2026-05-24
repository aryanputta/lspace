"""
Energy consumption prediction for NASA lunar rover path planning.

MLP with skip connections predicts energy (Wh) consumed along a candidate path
segment, with a confidence interval used by the path planner as a cost function.

The model supports the planner selecting energy-efficient routes while
accounting for battery temperature, solar availability, and terrain difficulty.
Confidence intervals prevent committing to paths where energy prediction is
highly uncertain (e.g. novel terrain types not seen in training).

Input features (10 total):
  0: path_distance        (m)
  1: terrain_roughness    (dimensionless 0-1 index)
  2: average_slope_deg    (degrees, positive = uphill)
  3: payload_active       (bool as float: 1=instruments active, 0=traversal only)
  4: battery_temp_c       (Celsius; cold batteries have higher internal resistance)
  5: solar_irradiance     (W/m², 0 = eclipse/PSR, ~1360 on lunar surface at noon)
  6: average_speed        (m/s)
  7: wheel_slip_estimate  (0-1, from slip prediction model)
  8: comms_overhead       (bool as float: 1=comms active during traverse)
  9: elevation_change     (m, signed; used with slope for consistency checking)
"""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


INPUT_DIM = 10


# ---------------------------------------------------------------------------
# Feature normalisation (learned shift+scale, initialised from statistics)
# ---------------------------------------------------------------------------

class FeatureNormaliser(nn.Module):
    """
    Learnable per-feature normalisation that can be initialised from dataset
    statistics but adapts during fine-tuning on deployment telemetry.
    """

    def __init__(self, input_dim: int) -> None:
        super().__init__()
        self.shift = nn.Parameter(torch.zeros(input_dim))
        self.scale = nn.Parameter(torch.ones(input_dim))

    def forward(self, x: Tensor) -> Tensor:
        return (x - self.shift) / (self.scale.abs() + 1e-6)

    def initialise_from_stats(self, mean: Tensor, std: Tensor) -> None:
        with torch.no_grad():
            self.shift.copy_(mean)
            self.scale.copy_(std)


# ---------------------------------------------------------------------------
# Gated residual MLP block
# ---------------------------------------------------------------------------

class GatedResidualBlock(nn.Module):
    """
    MLP residual block with gating mechanism.

    Gating helps the model selectively suppress irrelevant features —
    useful when solar_irradiance = 0 (eclipse) makes solar-related
    computations irrelevant.
    """

    def __init__(self, dim: int, hidden_dim: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.ff = nn.Sequential(
            nn.Linear(dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, dim),
        )
        self.gate = nn.Sequential(
            nn.Linear(dim, dim),
            nn.Sigmoid(),
        )
        self.norm = nn.LayerNorm(dim)

    def forward(self, x: Tensor) -> Tensor:
        ff_out = self.ff(x)
        gated = self.gate(x) * ff_out
        return self.norm(x + gated)


# ---------------------------------------------------------------------------
# Cross-feature interaction layer
# ---------------------------------------------------------------------------

class FeatureInteractionLayer(nn.Module):
    """
    Explicit second-order feature interaction via outer product projection.

    Captures synergies like (high_slope AND high_slip) → much more energy
    than either factor alone, which pure additive MLPs underfit.
    """

    def __init__(self, input_dim: int, interaction_rank: int = 8) -> None:
        super().__init__()
        # Low-rank outer product: project to rank-k, outer product, then summarise
        self.proj_v = nn.Linear(input_dim, interaction_rank, bias=False)
        self.proj_out = nn.Linear(interaction_rank, input_dim)

    def forward(self, x: Tensor) -> Tensor:
        v = self.proj_v(x)               # (B, rank)
        interaction = v.unsqueeze(-1) * v.unsqueeze(-2)  # (B, rank, rank)
        interaction = interaction.sum(-1)  # (B, rank) — sum over one axis
        return x + self.proj_out(interaction)


# ---------------------------------------------------------------------------
# Main model
# ---------------------------------------------------------------------------

class EnergyPredictor(nn.Module):
    """
    MLP with skip connections, gated residual blocks, and explicit feature
    interactions for energy consumption prediction.

    Outputs:
      energy_pred: (B,) — predicted energy in Wh
      log_var:     (B,) — log-variance for confidence interval

    Confidence interval (95%): energy_pred ± 1.96 * exp(0.5 * log_var)

    Args:
        input_dim:       number of input features (default 10)
        hidden_dim:      width of MLP layers
        num_blocks:      number of GatedResidualBlocks
        dropout:         dropout rate (also used for MC Dropout if needed)
        interaction_rank: rank for feature interaction layer
    """

    def __init__(
        self,
        input_dim: int = INPUT_DIM,
        hidden_dim: int = 128,
        num_blocks: int = 4,
        dropout: float = 0.1,
        interaction_rank: int = 8,
    ) -> None:
        super().__init__()
        self.normaliser = FeatureNormaliser(input_dim)
        self.interaction = FeatureInteractionLayer(input_dim, interaction_rank)

        self.input_proj = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        self.blocks = nn.Sequential(
            *[GatedResidualBlock(hidden_dim, hidden_dim * 2, dropout) for _ in range(num_blocks)]
        )

        # Skip connection from input projection to output
        self.skip_proj = nn.Linear(input_dim, hidden_dim)

        # Energy head
        self.energy_head = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.GELU(),
            nn.Linear(64, 1),
            nn.Softplus(),  # ensures non-negative energy output
        )

        # Uncertainty head
        self.uncertainty_head = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.GELU(),
            nn.Linear(64, 1),
        )

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
        """
        Args:
            x: (B, input_dim) feature vector

        Returns:
            energy_pred: (B,) in Wh (non-negative)
            log_var:     (B,) log-variance for CI computation
        """
        x_norm = self.normaliser(x)
        x_interacted = self.interaction(x_norm)

        h = self.input_proj(x_interacted)
        h = self.blocks(h)

        # Add skip from normalised input
        h = h + self.skip_proj(x_interacted)

        energy = self.energy_head(h).squeeze(-1)
        log_var = self.uncertainty_head(h).squeeze(-1)
        return energy, log_var

    def predict_with_ci(
        self, x: Tensor, z: float = 1.96
    ) -> tuple[Tensor, Tensor, Tensor]:
        """
        Returns (energy_mean, ci_lower, ci_upper) using aleatoric uncertainty.

        Args:
            z: z-score for confidence interval (1.96 = 95%)
        """
        with torch.no_grad():
            energy, log_var = self.forward(x)
            std = (log_var * 0.5).exp()
            return energy, energy - z * std, energy + z * std

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_energy_model(
    checkpoint: Optional[str] = None,
    device: str = "cpu",
) -> EnergyPredictor:
    model = EnergyPredictor()
    if checkpoint is not None:
        state = torch.load(checkpoint, map_location=device)
        model.load_state_dict(state["model_state_dict"])
    return model.to(device)


if __name__ == "__main__":
    model = EnergyPredictor()
    x = torch.randn(16, INPUT_DIM)
    with torch.no_grad():
        energy, log_var = model(x)
        e, lo, hi = model.predict_with_ci(x)
    print(f"Input:       {tuple(x.shape)}")
    print(f"Energy pred: {tuple(energy.shape)}  mean={energy.mean():.3f} Wh")
    print(f"CI lower:    {lo.mean():.3f} Wh")
    print(f"CI upper:    {hi.mean():.3f} Wh")
    print(f"Parameters:  {model.count_parameters():,}")
