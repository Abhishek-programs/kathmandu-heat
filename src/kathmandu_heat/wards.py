"""Ward polygons from OpenStreetMap, and ward-level heat with an uncertainty range."""
import json
import re

import geopandas as gpd
import numpy as np
import requests
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union

from . import config as c
from .composite import median
from .fetch import grid

URL = "https://overpass-api.de/api/interpreter"
QUERY = '[out:json][timeout:150];relation["boundary"="administrative"]["admin_level"="9"]({s},{w},{n},{e});out geom;'


def download():
    f = c.ROOT / "data" / "osm_wards.json"
    if not f.exists():
        w, s, e, n = c.BBOX_LL
        r = requests.post(URL, data={"data": QUERY.format(s=s, w=w, n=n, e=e)}, headers={"User-Agent": "kathmandu-heat/0.1"}, timeout=180)
        r.raise_for_status()
        f.write_text(r.text)
    return json.loads(f.read_text())


def polygons():
    recs = []
    for el in download()["elements"]:
        t = el["tags"]
        name = t.get("name:en") or t.get("name")
        lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]]) for m in el["members"] if m["type"] == "way" and m["role"] != "inner" and len(m.get("geometry", [])) > 1]
        polys = list(polygonize(unary_union(lines)))
        if polys and name:
            recs.append({"ward": name, "municipality": re.sub(r"[-\s]*\d+$", "", name), "geometry": unary_union(polys)})
    g = gpd.GeoDataFrame(recs, crs="EPSG:4326").to_crs(c.CRS)
    return g[~g.municipality.isin(c.OUTSIDE)].drop_duplicates("ward").reset_index(drop=True)


def label_grid(g):
    """Ward index per 120 m cell (-1 outside)."""
    tf, h, w = grid()
    step = c.RES * c.AGG
    return rasterize(
        ((geom, i) for i, geom in enumerate(g.geometry)),
        out_shape=(h // c.AGG, w // c.AGG),
        transform=from_origin(tf.c, tf.f, step, step),
        fill=-1,
        dtype="int32",
    )


def rank(g, lst, floor, n_boot=500, min_cells=15):
    """Mean heat per ward. The range comes from resampling whole scenes, so it reflects which days we happened to see."""
    every = label_grid(g)
    lab = np.where(floor, every, -1)
    ids = [i for i in range(len(g)) if (lab == i).sum() >= max(min_cells, 0.5 * (every == i).sum())]

    def means(m):
        return np.array([np.nanmean(m[lab == i]) if np.isfinite(m[lab == i]).any() else np.nan for i in ids])

    base = means(median(lst))
    rng = np.random.default_rng(c.SEED)
    boots = np.array([means(median(lst[rng.integers(0, len(lst), len(lst))], 1)) for _ in range(n_boot)])
    ranks = (-boots).argsort(1).argsort(1) + 1
    out = g.loc[ids, ["ward", "municipality"]].assign(
        heat_c=base,
        lo=np.nanpercentile(boots, 2.5, axis=0),
        hi=np.nanpercentile(boots, 97.5, axis=0),
        rank_lo=np.percentile(ranks, 2.5, axis=0).astype(int),
        rank_hi=np.percentile(ranks, 97.5, axis=0).astype(int),
        top10_share=(ranks <= 10).mean(0),
    )
    return out.sort_values("heat_c", ascending=False).reset_index(drop=True)
