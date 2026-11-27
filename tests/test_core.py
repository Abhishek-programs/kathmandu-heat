import numpy as np

from kathmandu_heat import fetch


def test_lst_scale_matches_usgs_example():
    # USGS Collection 2: K = DN * 0.00341802 + 149.0
    assert abs(fetch.lst_celsius(np.array([44000]))[0] - (44000 * 0.00341802 + 149 - 273.15)) < 1e-3


def test_clear_mask_rejects_each_bad_bit():
    clear = 21824  # standard Collection 2 "clear, low confidence" value
    assert fetch.clear_mask(np.array([clear]))[0]
    for bit in range(6):
        assert not fetch.clear_mask(np.array([clear | (1 << bit)]))[0]


def test_grid_divides_by_aggregation():
    from kathmandu_heat import config as c

    _, h, w = fetch.grid()
    assert h % c.AGG == 0 and w % c.AGG == 0


def test_north_facing_slope_is_positive(monkeypatch):
    from kathmandu_heat import composite

    rows = np.arange(40)[:, None] * np.ones((1, 40)) * 10.0  # higher towards the south: faces north
    monkeypatch.setattr(composite, "dem", lambda: rows)
    _, _, north, east = composite.terrain()
    assert (north > 0).all() and np.allclose(east, 0, atol=1e-9)


def test_median_needs_enough_dates():
    from kathmandu_heat.composite import median

    a = np.full((5, 1, 2), np.nan)
    a[:, 0, 0] = 1.0
    a[:2, 0, 1] = 1.0
    m = median(a, 3)
    assert m[0, 0] == 1.0 and np.isnan(m[0, 1])


def test_valley_excludes_other_districts():
    from kathmandu_heat import config as c, wards

    g = wards.polygons()
    assert not set(g.municipality) & c.OUTSIDE
    assert "Kathmandu-09" in set(g.ward)
