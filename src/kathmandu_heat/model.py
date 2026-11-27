"""How much of the heat pattern can land cover and terrain explain, and does it hold elsewhere?"""
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config as c

FEATURES = ["ndvi", "ndbi", "albedo", "elev", "slope", "northness", "eastness"]


def models():
    return {
        "mean (no skill)": (DummyRegressor(), FEATURES),
        "linear: elevation only": (make_pipeline(StandardScaler(), LinearRegression()), ["elev"]),
        "linear: all features": (make_pipeline(StandardScaler(), LinearRegression()), FEATURES),
        "gradient boosting": (HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40, random_state=c.SEED), FEATURES),
    }


def clean(df):
    d = df[df.floor].dropna(subset=["heat", *FEATURES])
    return d.reset_index(drop=True)


def cross_validate(d):
    rows = []
    for name, (m, cols) in models().items():
        for label, split in (
            ("random", KFold(5, shuffle=True, random_state=c.SEED).split(d)),
            ("spatial blocks", GroupKFold(5).split(d, groups=d.block)),
        ):
            pred = np.full(len(d), np.nan)
            for tr, te in split:
                pred[te] = m.fit(d[cols].iloc[tr], d.heat.iloc[tr]).predict(d[cols].iloc[te])
            rows.append({"model": name, "split": label, "r2": r2_score(d.heat, pred), "mae_c": mean_absolute_error(d.heat, pred)})
    return pd.DataFrame(rows)


def temporal(train, test):
    rows = []
    for name, (m, cols) in models().items():
        p = m.fit(train[cols], train.heat).predict(test[cols])
        rows.append({"model": name, "split": "train 2021-24, test 2025-26", "r2": r2_score(test.heat, p), "mae_c": mean_absolute_error(test.heat, p)})
    return pd.DataFrame(rows)


def importance(d):
    """Permutation importance measured on held-out blocks, not on training data."""
    m, cols = models()["gradient boosting"]
    out = []
    for tr, te in GroupKFold(5).split(d, groups=d.block):
        m.fit(d[cols].iloc[tr], d.heat.iloc[tr])
        r = permutation_importance(m, d[cols].iloc[te], d.heat.iloc[te], n_repeats=5, random_state=c.SEED, scoring="neg_mean_absolute_error")
        out.append(r.importances_mean)
    a = np.array(out)
    return pd.DataFrame({"feature": cols, "mae_increase_c": a.mean(0), "sd_over_folds": a.std(0)}).sort_values("mae_increase_c", ascending=False)
