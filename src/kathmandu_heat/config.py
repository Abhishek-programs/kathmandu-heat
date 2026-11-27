"""Every number that shapes the result lives here."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "outputs"
FIG = OUT / "figures"

CRS = "EPSG:32645"  # UTM 45N, metres
BBOX_LL = (85.24, 27.61, 85.46, 27.79)  # Kathmandu Valley: west, south, east, north
RES = 30  # Landsat grid, metres
AGG = 4  # 4 x 30 m = 120 m. The thermal band is measured at 100 m, so 30 m pixels are not independent.

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
YEARS = range(2021, 2027)
MONTHS = (3, 4, 5)  # pre-monsoon: the hottest clear-sky season
MAX_SCENE_CLOUD = 40  # whole-scene filter; the valley itself is checked per pixel
MIN_VALLEY_CLEAR = 0.60  # keep a scene only if 60% of the valley floor is clear
MIN_OBS = 5  # a pixel needs at least this many clear dates

FLOOR_MAX_ELEV = 1500  # metres; "valley floor" domain for the model
BLOCK_M = 2000  # spatial cross-validation block size
SEED = 7
OUTSIDE = {"Kakani", "Dhunibesi", "Paunauti"}  # Nuwakot, Dhading and Kavre districts: in the box, not in the valley
