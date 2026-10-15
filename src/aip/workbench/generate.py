"""Deterministic synthesis of a workbench dataset from its spec (synthetic; no real population)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from aip.workbench.specs import DatasetSpec


@dataclass(frozen=True)
class Synthetic:
    spec: DatasetSpec
    x: np.ndarray  # n x F, NaN = unknown, column order = spec.features
    segment: np.ndarray  # hidden; used only to plant structure and to check semantic relevance
    breakdown: np.ndarray  # index into spec.breakdown_values
    seed: np.ndarray  # entity indices in the seed list (empty if none)
    behavior: np.ndarray  # entity indices showing the behavior pattern (empty if none)
    outcome: np.ndarray | None  # 0/1 per entity, or None

    @property
    def sha256(self) -> str:
        """Content hash of the generated snapshot, recorded in its dataset manifest."""
        digest = hashlib.sha256()
        for part in (self.x, self.breakdown, self.seed, self.behavior):
            digest.update(np.ascontiguousarray(part).tobytes())
        if self.outcome is not None:
            digest.update(self.outcome.tobytes())
        return "sha256:" + digest.hexdigest()


def _column(kind: str, means: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if kind == "count":
        return rng.poisson(means * rng.gamma(2.0, 0.5, size=means.shape)).astype(float)
    if kind == "share":
        conc = 14.0
        return rng.beta(means * conc, (1 - means) * conc)
    if kind == "binary":
        return (rng.random(means.shape) < means).astype(float)
    return means + rng.normal(0.0, 1.2, size=means.shape)


def _zscore(col: np.ndarray) -> np.ndarray:
    filled = np.where(np.isnan(col), np.nanmean(col), col)
    sd = filled.std()
    return (filled - filled.mean()) / (sd if sd > 0 else 1.0)


def _intercept_for(base_rate: float, linear: np.ndarray) -> float:
    lo, hi = -20.0, 20.0
    for _ in range(60):
        mid = (lo + hi) / 2
        rate = float(np.mean(1 / (1 + np.exp(-(mid + linear)))))
        lo, hi = (mid, hi) if rate < base_rate else (lo, mid)
    return (lo + hi) / 2


def generate(spec: DatasetSpec) -> Synthetic:
    rng = np.random.default_rng(spec.rng_seed)
    n, names = spec.n, [f.name for f in spec.features]
    segment = rng.choice(len(spec.segment_probs), size=n, p=np.array(spec.segment_probs) / sum(spec.segment_probs))
    cols = []
    for feature in spec.features:
        col = _column(feature.kind, np.array(feature.means)[segment], rng)
        if feature.missing:
            col[rng.random(n) < feature.missing] = np.nan
        cols.append(col)
    x = np.column_stack(cols)

    probs = np.array(spec.breakdown_by_segment)[segment]
    breakdown = (probs.cumsum(axis=1) > rng.random((n, 1))).argmax(axis=1)

    seed = np.array([], dtype=int)
    if spec.seed_size:
        w = np.array(spec.seed_segment_weights)[segment] + 1e-9
        seed = np.sort(rng.choice(n, size=spec.seed_size, replace=False, p=w / w.sum()))

    behavior = np.array([], dtype=int)
    if spec.behavior_features:
        index = sum(_zscore(x[:, names.index(f)]) for f in spec.behavior_features) + rng.normal(0, 1.0, n)
        behavior = np.sort(np.argsort(-index)[: int(round(spec.behavior_share * n))])

    outcome = None
    if spec.outcome:
        z = np.column_stack([_zscore(x[:, names.index(f)]) for f in spec.outcome.weights])
        linear = z @ np.array(list(spec.outcome.weights.values()))
        b0 = _intercept_for(spec.outcome.base_rate, linear)
        outcome = (rng.random(n) < 1 / (1 + np.exp(-(b0 + linear)))).astype(np.int8)

    return Synthetic(spec, x, segment, breakdown, seed, behavior, outcome)
