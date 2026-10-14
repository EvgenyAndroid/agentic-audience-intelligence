"""Labeled propensity baselines (requires the optional 'modeling' extra: scikit-learn).

Use only after a task decision is ELIGIBLE for training (qualified labels). Preprocessing is fit
inside the pipeline on training data only. Imputation with indicators is a documented transform.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def fit_logistic_baseline(x_train: np.ndarray, y_train: np.ndarray, random_state: int) -> Any:
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    model = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True),
        StandardScaler(),
        LogisticRegression(max_iter=1000, random_state=random_state),
    )
    return model.fit(x_train, y_train)


def fit_boosted_candidate(x_train: np.ndarray, y_train: np.ndarray, random_state: int, max_iter: int) -> Any:
    """Bounded gradient-boosted candidate; handles NaN natively without imputation."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    return HistGradientBoostingClassifier(max_iter=max_iter, random_state=random_state).fit(x_train, y_train)
