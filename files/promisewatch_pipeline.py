"""
PromiseWatch — evidence pipeline scaffold
==========================================
Run this in Google Colab or a local environment with earthengine-api
already authenticated (ee.Authenticate() + ee.Initialize()). Not
executable in this sandbox — no network path to earthengine.googleapis.com.

Covers: dam water-extent detection (Thwake, Arror/Kimwarer) first.
Road and stadium detection functions are stubbed with a clear TODO —
build those after the dam case is validated end to end.

Install: pip install earthengine-api geemap pandas
"""

import ee
import pandas as pd
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# 0. Setup
# ---------------------------------------------------------------------------
# ee.Authenticate()  # uncomment on first run
ee.Initialize(project='YOUR_GEE_PROJECT_ID')  # replace with your GEE project

CASES_CSV = "promisewatch_cases_v3.csv"  # the file from the earlier step


# ---------------------------------------------------------------------------
# 1. Cloud-masked Sentinel-2 water index (NDWI / MNDWI)
# ---------------------------------------------------------------------------
def mask_s2_clouds(image):
    """Mask clouds using the Sentinel-2 QA60 band."""
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
        qa.bitwiseAnd(cirrus_bit_mask).eq(0)
    )
    return image.updateMask(mask).divide(10000)


def get_water_composite(aoi, start_date, end_date):
    """
    Median cloud-free Sentinel-2 composite over an AOI/date range,
    with MNDWI (Modified NDWI — more robust than NDWI over built-up
    areas near reservoirs) added as a band.
    """
    collection = (
        ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
        .map(mask_s2_clouds)
    )
    composite = collection.median().clip(aoi)
    mndwi = composite.normalizedDifference(['B3', 'B11']).rename('MNDWI')
    return composite.addBands(mndwi), collection.size()


def water_extent_hectares(mndwi_image, aoi, threshold=0.0, scale=10):
    """
    Area (hectares) of pixels classified as water (MNDWI > threshold)
    within the AOI. threshold=0.0 is a standard starting point —
    validate against a known-water case (Thwake) before trusting it
    on ambiguous cases.
    """
    water_mask = mndwi_image.select('MNDWI').gt(threshold)
    area_image = water_mask.multiply(ee.Image.pixelArea())
    stats = area_image.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=aoi,
        scale=scale,
        maxPixels=1e9,
    )
    sq_meters = stats.get('MNDWI')
    return ee.Number(sq_meters).divide(10000)  # -> hectares


# ---------------------------------------------------------------------------
# 2. Dam case evaluator, with the Arror/Kimwarer size guardrail
# ---------------------------------------------------------------------------
def evaluate_dam_case(name, lat, lon, buffer_m, claim_start, claim_end,
                       guardrail_min_hectares, design_target_hectares,
                       today=None):
    """
    Two separate thresholds — don't collapse them into one:

    guardrail_min_hectares: the LOW bar that rules out "this is just a
    small pre-existing water pan, not the promised project." Should be
    set well above typical small community water-pan sizes (roughly
    1-10 ha) but well below full design capacity, since a genuinely
    in-progress dam may only be partially filled. Use this to catch
    false positives like the Arror/Kimwarer decoy pans.

    design_target_hectares: the dam's actual FULL design reservoir
    surface area, from engineering specs. Use this to compute % of
    design capacity currently filled — a progress metric, not a
    pass/fail guardrail. Do not conflate "% construction complete"
    (an engineering/contractor metric) with "% of reservoir filled"
    (a hydrological one) — they lag each other.

    For Thwake: design_target_hectares ~= 2900 (per Ministry of
    Water / Kenya Engineer reporting on the Phase I design). Backflow
    extends ~10km upstream along both the Thwake and Athi arms, so a
    small circular buffer will clip the true extent — increase
    buffer_m accordingly, and treat a circular buffer as an
    approximation only; a proper polygon following both river arms
    would be more accurate.
    """
    point = ee.Geometry.Point([lon, lat])
    aoi = point.buffer(buffer_m)

    # Baseline window: first 90 days after claimed construction start —
    # reservoir should still be empty/near-empty here if the project
    # hadn't broken ground yet, or just starting to fill if it had.
    claim_start_dt = datetime.strptime(claim_start, '%Y-%m-%d')
    baseline_end_dt = claim_start_dt + timedelta(days=90)

    # Current window: most recent 90 days with usable imagery.
    today_dt = today or datetime.utcnow()
    current_start_dt = today_dt - timedelta(days=90)

    pre_composite, pre_n = get_water_composite(
        aoi, claim_start_dt.strftime('%Y-%m-%d'), baseline_end_dt.strftime('%Y-%m-%d')
    )
    current_composite, cur_n = get_water_composite(
        aoi, current_start_dt.strftime('%Y-%m-%d'), today_dt.strftime('%Y-%m-%d')
    )

    pre_extent = water_extent_hectares(pre_composite, aoi)
    current_extent = water_extent_hectares(current_composite, aoi)

    return {
        'project': name,
        'aoi_center': (lat, lon),
        'pre_image_count': pre_n,       # .getInfo() — sanity-check >0 cloud-free scenes exist
        'current_image_count': cur_n,   # .getInfo()
        'pre_extent_ha': pre_extent,    # .getInfo() to pull the actual number
        'current_extent_ha': current_extent,  # .getInfo()
        'guardrail_min_ha': guardrail_min_hectares,
        'design_target_ha': design_target_hectares,
        # Apply AFTER pulling real numbers with .getInfo():
        #   current_ha = result['current_extent_ha'].getInfo()
        #   if current_ha < guardrail_min_hectares:
        #       verdict = ("Not Delivered / Conflicted — water present, if "
        #                  "any, is at small-pan scale, not dam scale; check "
        #                  "for a known nearby unrelated feature before "
        #                  "concluding either way.")
        #   else:
        #       pct_filled = current_ha / design_target_hectares * 100
        #       verdict = f"Supported — reservoir forming, ~{pct_filled:.0f}% "
        #                 f"of design surface area currently filled. Do NOT "
        #                 f"equate this with the contractor's reported "
        #                 f"construction-complete percentage — they measure "
        #                 f"different things."
    }


# ---------------------------------------------------------------------------
# 3. TODO — road corridor change detection (Day 3)
# ---------------------------------------------------------------------------
def evaluate_road_case(name, lat, lon, route_geometry=None):
    """
    Stub. Needs an actual route line/buffer, not a single point —
    pull from OSM (osmnx) if the road is mapped, or digitize manually
    in geemap before running this. Approach: SAR backscatter change
    (Sentinel-1, robust to cloud cover) along a buffered corridor,
    before vs. after claimed construction start.
    """
    raise NotImplementedError("Build after dam pipeline is validated on Thwake.")


# ---------------------------------------------------------------------------
# 4. TODO — stadium footprint change detection (Day 3)
# ---------------------------------------------------------------------------
def evaluate_stadium_case(name, lat, lon, buffer_m=150):
    """
    Stub. Approach: built-up index / NDVI drop + brightness increase
    within a small buffer around the claimed site, before vs. after
    claimed construction start. At Sentinel-2's 10m resolution this
    can only confirm gross structure presence/absence, not finish
    quality — say so explicitly in the demo, don't overclaim.
    """
    raise NotImplementedError("Build after dam pipeline is validated on Thwake.")


# ---------------------------------------------------------------------------
# 5. Run — start here
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    cases = pd.read_csv(CASES_CSV)
    thwake = cases[cases['project_name'] == 'Thwake Dam'].iloc[0]

    result = evaluate_dam_case(
        name=thwake['project_name'],
        lat=thwake['latitude'],
        lon=thwake['longitude'],
        # 8km radius as a rough approximation of a reservoir stretching
        # ~10km upstream along two river arms — a circle centered on the
        # dam wall still won't perfectly trace both arms. If you have
        # time, replace this buffer with a proper polygon following the
        # Thwake and Athi river courses upstream from the confluence.
        buffer_m=8000,
        claim_start='2018-01-01',
        claim_end='2026-12-01',
        guardrail_min_hectares=30,      # well above a small community water pan
        design_target_hectares=2900,    # Ministry of Water / Phase I design spec
    )
    print(result)
    # Next: result['pre_extent_ha'].getInfo(), result['current_extent_ha'].getInfo()

    # -----------------------------------------------------------------
    # Arror and Kimwarer — TWO SEPARATE SITES, TWO SEPARATE CALLS.
    # Design specs below are sourced from NEMA engineering descriptions
    # (2.8 km2 / 280 ha reservoir for Arror, 2.15 km2 / 215 ha for
    # Kimwarer). Coordinates are still TODO — the single pin given
    # earlier (0.318797, 35.631198) can't serve as the AOI center for
    # both sites; get a separate lat/lon for each before running these.
    # -----------------------------------------------------------------
    arror = cases[cases['project_name'] == 'Arror Dam'].iloc[0]
    kimwarer = cases[cases['project_name'] == 'Kimwarer Dam'].iloc[0]

    arror_result = evaluate_dam_case(
        name=arror['project_name'],
        lat=1.02,     # PROVISIONAL — area estimate near Sererwa/Kapsowar, not a
        lon=35.57,    # sourced grid reference. Confirm visually before trusting.
        buffer_m=2000,  # ~280 ha design reservoir - smaller footprint than Thwake
        claim_start='2017-01-01',
        claim_end='2026-12-01',
        guardrail_min_hectares=20,       # above small-pan scale, below 280 ha design
        design_target_hectares=280,      # NEMA design spec: 2.8 km2
    )

    kimwarer_result = evaluate_dam_case(
        name=kimwarer['project_name'],
        lat=0.265,    # NEMA UTM grid ref (785300E, 29300N, zone 36N) — internally
        lon=35.564,   # consistent conversion, higher confidence than Arror's pin.
        buffer_m=1800,  # ~215 ha design reservoir
        claim_start='2017-01-01',
        claim_end='2026-12-01',
        guardrail_min_hectares=20,
        design_target_hectares=215,      # NEMA design spec: 2.15 km2
    )
    print(arror_result)
    print(kimwarer_result)
