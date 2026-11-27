"""Turn cached scenes into one heat layer and a set of land-cover features."""
import numpy as np
import pandas as pd
from scipy import ndimage

from . import config as c
from .fetch import clear_mask, dem, lst_celsius, reflectance


def ratio(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (a - b) / (a + b)
    out[~np.isfinite(out) | (np.abs(out) > 1)] = np.nan
    return out


def load_scene(path):
    with np.load(path) as z:
        ok = clear_mask(z["qa_pixel"]) & (z["lwir11"] > 0)
        lst = np.where(ok, lst_celsius(z["lwir11"]), np.nan).astype("float32")
        r = {}
        for b in ("blue", "red", "nir08", "swir16", "swir22"):
            v = reflectance(z[b])
            r[b] = np.where(ok & (z[b] > 0) & (v > 0) & (v < 1), v, np.nan).astype("float32")
    albedo = 0.356 * r["blue"] + 0.130 * r["red"] + 0.373 * r["nir08"] + 0.085 * r["swir16"] + 0.072 * r["swir22"] - 0.0018
    return {
        "lst": lst,
        "ndvi": ratio(r["nir08"].copy(), r["red"]),
        "ndbi": ratio(r["swir16"].copy(), r["nir08"]),
        "albedo": albedo,
    }


def agg(a):
    """Mean over AGG x AGG blocks; needs at least half the block."""
    h, w = a.shape
    b = a.reshape(h // c.AGG, c.AGG, w // c.AGG, c.AGG)
    n = np.isfinite(b).sum(axis=(1, 3))
    s = np.nansum(b, axis=(1, 3))
    return np.where(n >= c.AGG * c.AGG / 2, s / np.maximum(n, 1), np.nan)


def valley_floor():
    """Land below FLOOR_MAX_ELEV inside the wards of Kathmandu, Lalitpur and Bhaktapur districts.

    An elevation cut alone leaks: the valley connects over low passes to land that drains elsewhere.
    """
    from .wards import label_grid, polygons  # local import: wards uses median() from here

    # Two OSM rings (Kathmandu-24 and -25) do not close; filling the hole keeps their cells, unranked.
    inside = ndimage.binary_fill_holes(label_grid(polygons()) >= 0)
    return (agg(dem()) < c.FLOOR_MAX_ELEV) & inside


def terrain():
    z = agg(dem())
    step = c.RES * c.AGG
    gy, gx = np.gradient(z, step)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    # y axis points down in the array, so north-facing means elevation falls towards smaller rows
    aspect = np.arctan2(-gx, gy)
    return z, slope, np.cos(aspect) * np.sin(np.radians(slope)), np.sin(aspect) * np.sin(np.radians(slope))


def stack(log=print):
    """Per-scene arrays at 120 m. LST becomes an anomaly: pixel minus the valley-floor median on that date,

    which removes the weather of the day and leaves the place.
    """
    floor = valley_floor()
    rows, out = [], {k: [] for k in ("lst", "ndvi", "ndbi", "albedo")}
    for f in sorted(c.CACHE.glob("L*.npz")):
        s = {k: agg(v) for k, v in load_scene(f).items()}
        clear = float(np.isfinite(s["lst"][floor]).mean())
        used = clear >= c.MIN_VALLEY_CLEAR
        med = float(np.nanmedian(s["lst"][floor])) if clear > 0 else np.nan
        rows.append({"scene": f.stem, "date": pd.Timestamp(f.stem.split("_")[3]), "valley_clear": clear, "valley_median_c": med, "used": used})
        if used:
            s["lst"] = s["lst"] - med
            for k in out:
                out[k].append(s[k])
    scenes = pd.DataFrame(rows)
    log(f"{scenes.used.sum()} of {len(scenes)} scenes used")
    return scenes, {k: np.stack(v) for k, v in out.items()}


def median(a, min_obs=c.MIN_OBS):
    n = np.isfinite(a).sum(0)
    with np.errstate(all="ignore"):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = np.nanmedian(a, axis=0)
    return np.where(n >= min_obs, m, np.nan)


def table(st, idx, min_obs):
    """One row per 120 m cell, from the scenes in idx."""
    z, slope, north, east = terrain()
    h, w = z.shape
    yy, xx = np.mgrid[0:h, 0:w]
    step = c.RES * c.AGG
    df = pd.DataFrame(
        {
            "floor": valley_floor().ravel(),
            "row": yy.ravel(),
            "col": xx.ravel(),
            "heat": median(st["lst"][idx], min_obs).ravel(),
            "ndvi": median(st["ndvi"][idx], min_obs).ravel(),
            "ndbi": median(st["ndbi"][idx], min_obs).ravel(),
            "albedo": median(st["albedo"][idx], min_obs).ravel(),
            "elev": z.ravel(),
            "slope": slope.ravel(),
            "northness": north.ravel(),
            "eastness": east.ravel(),
        }
    )
    df["block"] = (df.row * step // c.BLOCK_M).astype(int) * 1000 + (df.col * step // c.BLOCK_M).astype(int)
    return df
