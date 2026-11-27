# Surface heat by ward in the Kathmandu Valley, 2021-2026

Abhishek Bhattarai. Draft v0.1, 2026-11-25. Not peer reviewed.

## Question
1. Which wards have the hottest land surface on clear pre-monsoon mornings?
2. How much of the pattern do land cover and terrain explain, in areas and years the model has not seen?

## Data
| Source | Use |
|---|---|
| Landsat 8/9 Collection 2 Level-2, path 141 row 041 | surface temperature (band 10), reflectance, cloud mask |
| Copernicus DEM GLO-30 | elevation, slope, aspect |
| OpenStreetMap, admin level 9 (snapshot 2026-11-25) | ward polygons |

41 scenes matched (March to May, 2021 to 2026, under 40% scene cloud). One could not be read from the server (LC09 2022-05-11, band 7). Of the other 40, 35 had at least 60% of the valley floor clear and were used: 3 in 2021, 6 in 2022, 8 in 2023, 7 in 2024, 4 in 2025, 7 in 2026.

## Method
1. **Mask.** Drop pixels flagged as fill, cloud, dilated cloud, cirrus, shadow or snow.
2. **Aggregate to 120 m.** The thermal sensor measures at 100 m and is resampled to 30 m, so 30 m pixels would repeat information.
3. **Remove the weather.** On each date subtract the valley-floor median. Each cell then has a temperature *difference*, comparable across dates.
4. **Composite.** Median difference per cell, at least 5 clear dates.
5. **Domain.** Below 1500 m, inside wards of Kathmandu, Lalitpur and Bhaktapur districts (23,061 cells).
6. **Ward ranking.** Mean per ward, for wards with at least half their area in the domain (181 of 203). Ranges come from resampling whole dates 500 times.
7. **Models.** Predict the composite from NDVI, NDBI, albedo, elevation, slope and aspect. Compared: the mean, a line on elevation, a line on all features, and gradient boosting. Tested three ways: random folds, 2 km spatial blocks, and fit on 2021-24 then tested on 2025-26.

## Results
**The spread is about 6 °C.** Between the 5th and 95th percentile cell: -3.2 to +2.5 °C against the valley median.

**Hottest wards** (°C above the median, 95% range over dates):

| Ward | Heat | Range | Plausible rank |
|---|---|---|---|
| Kathmandu-09 | 3.2 | 2.8 to 3.7 | 1 |
| Kathmandu-28 | 2.7 | 2.2 to 3.1 | 2 to 7 |
| Gokarneshwar-06 | 2.6 | 2.4 to 3.0 | 2 to 8 |
| Gokarneshwar-05 | 2.6 | 2.3 to 3.0 | 2 to 9 |
| Kathmandu-22 | 2.5 | 1.9 to 3.3 | 2 to 10 |

Kathmandu-09 contains the international airport. The runway and apron pull its mean up, so "hottest ward" there describes asphalt more than homes. Places 2 to 8 overlap: the data supports the group, not the order inside it. The coolest are forested edges such as Budhanilkantha-02 (-2.8 °C).

**What explains it** (R², higher is better):

| Model | Random folds | Unseen 2 km blocks | Unseen years |
|---|---|---|---|
| Mean | 0.00 | -0.01 | 0.00 |
| Elevation only | 0.28 | 0.27 | 0.29 |
| Linear, all features | 0.78 | 0.78 | 0.76 |
| Gradient boosting | 0.82 | 0.81 | 0.80 |

Typical error of gradient boosting on unseen blocks is 0.59 °C (linear: 0.62 °C). **The complex model barely beats the straight line.** For planning use the linear model is easier to defend.

On held-out blocks the built-up index (NDBI) matters most by far: shuffling it adds 0.66 °C of error, against 0.10 °C or less for any other feature. NDVI and NDBI carry much of the same information (both correlate with heat at about 0.8 in size, with opposite signs), so this does not mean greenery is unimportant.

## Limits
- **Surface, not air.** Land surface temperature is not what a thermometer in the shade reads, and not what a person feels.
- **About 10:30 in the morning only.** Landsat passes once. Nights, when heat harms sleep and health, are not seen.
- **Clear days only.** Hazy and cloudy days are missing.
- **Association, not cause.** The model cannot say what planting trees in a ward would do.
- **Shared sensor.** Features and target come from the same satellite passes, and the surface-temperature product itself uses an emissivity estimate tied to land cover. Some of the fit is built in.
- **Temporal test is partly shared.** Terrain and the cells are the same in both periods. It tests stability over years, not a new city.
- **No people yet.** The ranking has no population, age or housing data, so it is heat, not risk.
- **Wards are volunteer-mapped.** Kathmandu-24 and -25 do not close in OpenStreetMap and are unranked. The study box cuts some outer wards.

## Next
Population and building data for exposure; night-time thermal from ECOSTRESS; a check against air-temperature stations.

## Reproduce
`uv run python -m kathmandu_heat`. Code was written with AI assistance (Claude); the author is responsible for checking the method and results.
