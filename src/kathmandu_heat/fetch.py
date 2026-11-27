"""Find Landsat 8/9 scenes and read only the Kathmandu window of each one."""
import time

import numpy as np
import planetary_computer
import rasterio
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

from . import config as c

BANDS = ("lwir11", "qa_pixel", "blue", "red", "nir08", "swir16", "swir22")


def grid():
    """Fixed 30 m grid shared by every layer, trimmed so it divides by AGG."""
    w, s, e, n = transform_bounds("EPSG:4326", c.CRS, *c.BBOX_LL)
    step = c.RES * c.AGG
    w, s = np.floor(w / step) * step, np.floor(s / step) * step
    e, n = np.ceil(e / step) * step, np.ceil(n / step) * step
    return from_origin(w, n, c.RES, c.RES), int((n - s) / c.RES), int((e - w) / c.RES)


def read(href, resampling=Resampling.nearest, nodata=0):
    tf, h, w = grid()
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY=5, GDAL_HTTP_RETRY_DELAY=2):
        with rasterio.open(href) as src, WarpedVRT(
            src, crs=c.CRS, transform=tf, height=h, width=w, resampling=resampling, nodata=nodata
        ) as vrt:
            return vrt.read(1)


def search():
    cat = Client.open(c.STAC, modifier=planetary_computer.sign_inplace)
    items = []
    for y in c.YEARS:
        s = cat.search(
            collections=["landsat-c2-l2"],
            bbox=c.BBOX_LL,
            datetime=f"{y}-{min(c.MONTHS):02d}-01/{y}-{max(c.MONTHS):02d}-31",
            query={
                "eo:cloud_cover": {"lt": c.MAX_SCENE_CLOUD},
                "platform": {"in": ["landsat-8", "landsat-9"]},
                "landsat:collection_category": {"eq": "T1"},
            },
        )
        items += list(s.items())
    return sorted(items, key=lambda i: i.id)


def clear_mask(qa):
    """True where the pixel is valid and free of cloud, cirrus, shadow and snow (Collection 2 QA bits 0-5)."""
    bad = 0
    for bit in range(6):
        bad |= 1 << bit
    return (qa & bad) == 0


def lst_celsius(dn):
    return dn.astype("float32") * 0.00341802 + 149.0 - 273.15


def reflectance(dn):
    return dn.astype("float32") * 0.0000275 - 0.2


def dem():
    f = c.CACHE / "dem.npy"
    if f.exists():
        return np.load(f)
    cat = Client.open(c.STAC, modifier=planetary_computer.sign_inplace)
    out = None
    for it in cat.search(collections=["cop-dem-glo-30"], bbox=c.BBOX_LL).items():
        a = read(it.assets["data"].href, Resampling.bilinear, nodata=-9999).astype("float32")
        a[a <= -9999] = np.nan
        out = a if out is None else np.where(np.isnan(out), a, out)
    if out is None or np.isnan(out).mean() > 0.01:
        raise RuntimeError("DEM does not cover the area")
    np.save(f, out)
    return out


def fetch_all(log=print):
    c.CACHE.mkdir(parents=True, exist_ok=True)
    items = search()
    log(f"{len(items)} candidate scenes")
    skipped = []
    for it in items:
        f = c.CACHE / f"{it.id}.npz"
        if f.exists():
            continue
        for attempt in range(3):
            try:
                layers = {b: read(it.assets[b].href) for b in BANDS}
            except rasterio.errors.RasterioIOError as e:
                err = str(e).split("?")[0]
                time.sleep(5 * (attempt + 1))
            else:
                np.savez_compressed(f, **layers)
                log("  cached", it.id)
                break
        else:
            skipped.append(it.id)
            log("  SKIPPED", it.id, err)
    dem()
    (c.CACHE / "skipped.txt").write_text("\n".join(skipped))
    return skipped
