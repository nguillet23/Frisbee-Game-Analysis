"""Phase 5 modeling: predict a player's Phase 3 composite rating for a
game *before it happens*, from Phase 4's pre-game-safe features only
(role, trailing form, opponent strength, home/away) — never from that
game's own per-point stats, which is what the composite rating is
computed from (using them would make the "prediction" circular/trivial).

Three models compared on the same time-based train/test split, per
Plans/UFA_Analysis.md Phase 5:
- a hand-rolled baseline linear regression (no scikit-learn, see CLAUDE.md)
- XGBoost (gradient boosting), with per-prediction explanations via its
  built-in Tree SHAP (``pred_contribs=True``) — the ``shap`` package itself
  hits the same Application Control policy block as scipy on this machine
  (it depends on scipy internals), but XGBoost's own C++ Tree SHAP doesn't
  need it and gives exact, not approximate, per-feature contributions.
- a small PyTorch feedforward net (learning-goal comparison, not expected
  to beat the GBM on data this size/tabular — see the plan).
"""

import numpy as np
import pandas as pd
import torch
import xgboost as xgb
from torch import nn

from ufa_modeling.features import FORM_COLS

FORM_FEATURE_COLS = [f"{c}_last3" for c in FORM_COLS] + [f"{c}_season_to_date" for c in FORM_COLS]
CONTEXT_FEATURE_COLS = ["opponent_strength", "is_home"]
ARCHETYPE_COL = "archetype_label"


def build_model_frame(feats: pd.DataFrame, target_col: str = "composite_rating_game") -> pd.DataFrame:
    """Select and clean the pre-game-safe modeling columns from Phase 4's
    feature table, plus the target. Drops rows missing form/opponent
    history (a player's or opponent's first game of the season) rather
    than imputing — there's no principled "prior form" to fill in for a
    game that has none, and it's a small, well-understood slice of rows
    (see Phase 4 findings).
    """
    cols = FORM_FEATURE_COLS + CONTEXT_FEATURE_COLS + [ARCHETYPE_COL, "player_name", "start_timestamp", target_col]
    df = feats[cols].copy()
    df["is_home"] = df["is_home"].astype(float)
    df[ARCHETYPE_COL] = df[ARCHETYPE_COL].fillna("Low-usage")
    df = df.dropna(subset=FORM_FEATURE_COLS + ["opponent_strength", target_col])
    # Keep feats' original index (don't reset it) so callers can join
    # results (predictions, contributions) back onto `feats` by index.
    return df


def encode_features(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode archetype and return the final numeric design matrix
    (used identically by the OLS baseline and XGBoost, so their inputs are
    directly comparable)."""
    numeric = df[FORM_FEATURE_COLS + CONTEXT_FEATURE_COLS]
    archetype = pd.get_dummies(df[ARCHETYPE_COL], prefix="archetype")
    return pd.concat([numeric, archetype], axis=1)


def time_split(df: pd.DataFrame, test_frac: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    """Split by a chronological cutoff (last ``test_frac`` of the season by
    date is the test set), not randomly — this simulates the real
    deployment scenario of predicting upcoming games from what's known so
    far, not just holding out random rows that already know the season's
    full context via other players' overlapping form windows.
    """
    cutoff = df["start_timestamp"].quantile(1 - test_frac)
    train_mask = (df["start_timestamp"] <= cutoff).to_numpy()
    return np.where(train_mask)[0], np.where(~train_mask)[0]


def fit_baseline_ols(x_train: np.ndarray, y_train: np.ndarray) -> dict:
    """Hand-rolled standardized OLS (no scikit-learn on this machine, see
    CLAUDE.md) — same approach as ``ufa_modeling.target.fit_ols``, made
    standalone here since this fits on an arbitrary design matrix
    (one-hot archetypes included) rather than the fixed team-level columns.
    """
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std[std == 0] = 1.0  # constant columns (e.g. an archetype dummy in a degenerate split)
    x_std = (x_train - mean) / std

    design = np.column_stack([np.ones(len(x_std)), x_std])
    coefs, *_ = np.linalg.lstsq(design, y_train, rcond=None)

    return {"coefs": coefs, "mean": mean, "std": std}


def predict_baseline_ols(fit: dict, x: np.ndarray) -> np.ndarray:
    x_std = (x - fit["mean"]) / fit["std"]
    design = np.column_stack([np.ones(len(x_std)), x_std])
    return design @ fit["coefs"]


def fit_xgboost(x_train: pd.DataFrame, y_train: np.ndarray, **params) -> xgb.Booster:
    dtrain = xgb.DMatrix(x_train, label=y_train, feature_names=list(x_train.columns))
    defaults = {"max_depth": 4, "eta": 0.05, "subsample": 0.8, "colsample_bytree": 0.8, "seed": 0}
    return xgb.train({**defaults, **params}, dtrain, num_boost_round=300)


def xgboost_contributions(booster: xgb.Booster, x: pd.DataFrame) -> pd.DataFrame:
    """Per-prediction feature contributions via XGBoost's built-in exact
    Tree SHAP (not the ``shap`` package — see module docstring). Returns
    one row per prediction, one column per feature plus ``bias``; each
    row sums exactly to that row's prediction.
    """
    dmat = xgb.DMatrix(x, feature_names=list(x.columns))
    contribs = booster.predict(dmat, pred_contribs=True)
    return pd.DataFrame(contribs, columns=list(x.columns) + ["bias"], index=x.index)


class FeedforwardNet(nn.Module):
    """Small feedforward comparison model — a learning-goal secondary to
    the GBM, per the plan; not expected to beat gradient boosting on data
    this size/tabular."""

    def __init__(self, n_features: int, hidden: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def fit_torch_net(
    x_train: np.ndarray, y_train: np.ndarray, epochs: int = 200, lr: float = 1e-2, seed: int = 0
) -> tuple[FeedforwardNet, dict]:
    """Standardize (same reasoning as the OLS baseline — features live on
    different scales) and train with plain full-batch Adam; the dataset is
    small enough (a few thousand rows) that mini-batching isn't needed.
    """
    torch.manual_seed(seed)
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std[std == 0] = 1.0
    x_std = (x_train - mean) / std

    model = FeedforwardNet(x_train.shape[1])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    x_t = torch.tensor(x_std, dtype=torch.float32)
    y_t = torch.tensor(y_train, dtype=torch.float32)

    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        loss = loss_fn(model(x_t), y_t)
        loss.backward()
        optimizer.step()

    return model, {"mean": mean, "std": std}


def predict_torch_net(model: FeedforwardNet, scale: dict, x: np.ndarray) -> np.ndarray:
    x_std = (x - scale["mean"]) / scale["std"]
    model.eval()
    with torch.no_grad():
        return model(torch.tensor(x_std, dtype=torch.float32)).numpy()


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    residual = y_true - y_pred
    ss_res = float((residual**2).sum())
    ss_tot = float(((y_true - y_true.mean()) ** 2).sum())
    return {
        "r_squared": 1.0 - ss_res / ss_tot,
        "mae": float(np.abs(residual).mean()),
        "rmse": float(np.sqrt((residual**2).mean())),
    }
