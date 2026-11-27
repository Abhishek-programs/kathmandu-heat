"""python -m kathmandu_heat  -> rebuilds every table and figure in outputs/."""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as c
from . import model, wards
from .composite import median, stack, table, valley_floor
from .fetch import fetch_all, grid


def main():
    c.FIG.mkdir(parents=True, exist_ok=True)
    fetch_all()
    scenes, st = stack()
    scenes.to_csv(c.OUT / "scenes.csv", index=False)
    used = scenes[scenes.used].reset_index(drop=True)
    year = used.date.dt.year

    full = model.clean(table(st, np.arange(len(used)), c.MIN_OBS))
    train = model.clean(table(st, np.where(year <= 2024)[0], 3))
    test = model.clean(table(st, np.where(year >= 2025)[0], 3))
    scores = pd.concat([model.cross_validate(full), model.temporal(train, test)])
    scores.to_csv(c.OUT / "model_scores.csv", index=False)
    imp = model.importance(full)
    imp.to_csv(c.OUT / "feature_importance.csv", index=False)

    floor = valley_floor()
    g = wards.polygons()
    ranking = wards.rank(g, st["lst"], floor)
    ranking.round(3).to_csv(c.OUT / "ward_heat.csv", index=False)

    figures(st, g, ranking, full, floor)
    summary = {
        "scenes_found": int(len(scenes)),
        "scenes_used": int(len(used)),
        "first": str(used.date.min().date()),
        "last": str(used.date.max().date()),
        "used_per_year": {int(k): int(v) for k, v in year.value_counts().sort_index().items()},
        "cells_120m": int(len(full)),
        "heat_p5": float(full.heat.quantile(0.05)),
        "heat_p95": float(full.heat.quantile(0.95)),
        "corr_heat_ndvi": float(full.heat.corr(full.ndvi)),
        "corr_heat_ndbi": float(full.heat.corr(full.ndbi)),
        "corr_heat_elev": float(full.heat.corr(full.elev)),
        "wards_ranked": int(len(ranking)),
    }
    (c.OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(scores.round(3).to_string(index=False))
    print(imp.round(3).to_string(index=False))
    print(ranking.round(2).head(12).to_string(index=False))
    print(ranking.round(2).tail(6).to_string(index=False))


def figures(st, g, ranking, full, floor):
    tf, h, w = grid()
    ext = (tf.c, tf.c + w * c.RES, tf.f - h * c.RES, tf.f)
    m = np.where(floor, median(st["lst"]), np.nan)
    lim = float(np.nanpercentile(np.abs(m), 98))
    fig, ax = plt.subplots(figsize=(8, 6.6))
    im = ax.imshow(m, extent=ext, cmap="RdBu_r", vmin=-lim, vmax=lim)
    g[g.ward.isin(ranking.ward)].boundary.plot(ax=ax, color="#333", lw=0.35)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.set_axis_off()
    ax.set_title("Kathmandu Valley: surface heat vs the valley median\nclear pre-monsoon mornings (Mar-May 2021-2026), Landsat 8/9", fontsize=11, loc="left")
    fig.colorbar(im, ax=ax, shrink=0.6, label="°C above or below the valley-floor median")
    ax.annotate("2 km", (ext[0] + 1100, ext[2] + 750), fontsize=8)
    ax.plot([ext[0] + 500, ext[0] + 2500], [ext[2] + 500] * 2, color="k", lw=2)
    ax.text(0, -0.03,  "Landsat: USGS, via Microsoft Planetary Computer. DEM: Copernicus GLO-30. Wards: © OpenStreetMap contributors.", fontsize=6.5, transform=ax.transAxes)
    fig.savefig(c.FIG / "heat_map.png", dpi=200, bbox_inches="tight"); plt.close(fig)

    top = ranking.head(15)[::-1]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.errorbar(top.heat_c, top.ward, xerr=[(top.heat_c - top.lo).clip(lower=0), (top.hi - top.heat_c).clip(lower=0)], fmt="o", color="#b2182b", ecolor="#999", capsize=2)
    ax.set_xlabel("°C above the valley-floor median (95% range over resampled dates)")
    ax.set_title("15 hottest wards", loc="left", fontsize=11)
    fig.savefig(c.FIG / "top_wards.png", dpi=200, bbox_inches="tight"); plt.close(fig)

    s = full.sample(min(6000, len(full)), random_state=c.SEED)
    fig, ax = plt.subplots(figsize=(6, 4.2))
    ax.scatter(s.ndvi, s.heat, s=3, alpha=0.25, color="#2166ac", edgecolors="none")
    ax.set_xlabel("NDVI (how green)"); ax.set_ylabel("°C vs valley median")
    ax.set_title("Greener cells run cooler", loc="left", fontsize=11)
    fig.savefig(c.FIG / "ndvi_heat.png", dpi=200, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    main()
