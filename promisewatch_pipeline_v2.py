"""
PromiseWatch — evidence pipeline (consolidated rewrite)
=========================================================
Paste this whole file into a single Colab cell and run it top to
bottom. No __main__ guard — everything executes directly, matching
how Colab actually runs code, and there's nothing left to wire up
by hand afterward.

Requires: pip install earthengine-api geemap pandas  (run once, in
its own cell, before this one)

Requires an uploaded promisewatch_cases_v3.csv in the Colab session
(folder icon -> upload) before running.
"""

import ee
import pandas as pd
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# 0. Setup
# ---------------------------------------------------------------------------
ee.Authenticate()  # opens a browser auth flow — approve it
ee.Initialize(project='promisewatch-cases')

CASES_CSV = "promisewatch_cases_v3.csv"


# ---------------------------------------------------------------------------
# 1. Cloud-masked Sentinel-2 water index (MNDWI)
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
# 2. Dam case evaluator + resolver (delta-based guardrail, in one place)
# ---------------------------------------------------------------------------
def evaluate_dam_case(name, lat, lon, buffer_m, claim_start,
                       guardrail_min_hectares, design_target_hectares,
                       today=None):
    """
    Builds the lazy Earth Engine computation for one dam case. Returns
    a dict of un-evaluated EE objects plus metadata — call
    resolve_case() on the result to actually pull numbers and get a
    verdict.

    guardrail_min_hectares: the low bar that rules out "this is just a
    small pre-existing water pan, not the promised project." Checked
    against the DELTA above baseline, not raw current extent — a site
    can have real pre-existing water (natural river/wetland, or known
    unrelated water pans) that has nothing to do with the claimed
    project. Only water added since baseline counts as dam evidence.

    design_target_hectares: the dam's actual full design reservoir
    surface area, from engineering specs. Used to compute % of design
    capacity newly filled — a progress metric, separate from the
    guardrail. Do not conflate this with a contractor's reported
    "% construction complete" — they measure different things and lag
    each other.
    """
    point = ee.Geometry.Point([lon, lat])
    aoi = point.buffer(buffer_m)

    claim_start_dt = datetime.strptime(claim_start, '%Y-%m-%d')
    baseline_end_dt = claim_start_dt + timedelta(days=90)

    today_dt = today or datetime.utcnow()
    current_start_dt = today_dt - timedelta(days=90)

    pre_composite, pre_n = get_water_composite(
        aoi, claim_start_dt.strftime('%Y-%m-%d'), baseline_end_dt.strftime('%Y-%m-%d')
    )
    current_composite, cur_n = get_water_composite(
        aoi, current_start_dt.strftime('%Y-%m-%d'), today_dt.strftime('%Y-%m-%d')
    )

    return {
        'project': name,
        'aoi': aoi,
        'aoi_center': (lat, lon),
        'pre_composite': pre_composite,
        'current_composite': current_composite,
        'pre_image_count': pre_n,
        'current_image_count': cur_n,
        'pre_extent_ha': water_extent_hectares(pre_composite, aoi),
        'current_extent_ha': water_extent_hectares(current_composite, aoi),
        'guardrail_min_ha': guardrail_min_hectares,
        'design_target_ha': design_target_hectares,
    }


def resolve_case(result):
    """
    Pull real numbers from a result dict via .getInfo() and apply the
    delta-based guardrail. Returns a plain dict — safe to print, put
    in a DataFrame, or write to JSON/CSV.
    """
    pre_n = result['pre_image_count'].getInfo()
    cur_n = result['current_image_count'].getInfo()
    pre_ha = result['pre_extent_ha'].getInfo()
    cur_ha = result['current_extent_ha'].getInfo()
    guardrail = result['guardrail_min_ha']
    target = result['design_target_ha']

    delta_ha = None
    if pre_n == 0 or cur_n == 0:
        verdict = ("UNDERDETERMINED — no usable cloud-free imagery in one "
                   "or both windows (pre: %d scenes, current: %d scenes). "
                   "Widen the date range or loosen the cloud filter before "
                   "trusting any extent number." % (pre_n, cur_n))
    else:
        # Compare the DELTA above baseline, not raw current extent —
        # a site can have real pre-existing water unrelated to the
        # claimed project. Only water added since baseline counts.
        delta_ha = cur_ha - pre_ha
        if delta_ha < guardrail:
            verdict = ("NOT DELIVERED / CONFLICTED — water added since "
                       "baseline (%.2f ha delta) is below the small-pan "
                       "guardrail (%.1f ha). Current extent (%.2f ha) may "
                       "be pre-existing water unrelated to this project — "
                       "not evidence the dam exists." % (delta_ha, guardrail, cur_ha))
        else:
            pct_filled = delta_ha / target * 100
            verdict = ("SUPPORTED — reservoir forming, ~%.1f%% of design "
                       "surface area (%.2f ha of %.0f ha) newly filled "
                       "since baseline. Do NOT equate this with a "
                       "contractor's reported construction-complete "
                       "percentage — they measure different things." % (pct_filled, delta_ha, target))

    return {
        'project': result['project'],
        'aoi_center': result['aoi_center'],
        'pre_image_count': pre_n,
        'current_image_count': cur_n,
        'pre_extent_ha': round(pre_ha, 2) if pre_ha is not None else None,
        'current_extent_ha': round(cur_ha, 2) if cur_ha is not None else None,
        'delta_ha': round(delta_ha, 2) if delta_ha is not None else None,
        'verdict': verdict,
    }


def thumbnail_url(image, aoi, bands=('B4', 'B3', 'B2'), vis_min=0, vis_max=0.3, dimensions=512):
    """
    Quick true-color thumbnail URL for visually sanity-checking an
    AOI — e.g. confirming the pin actually sits on a river valley
    before trusting a 0.0 ha result as 'nothing built' rather than
    'nothing detectable here.'
    """
    return image.getThumbURL({
        'bands': list(bands),
        'min': vis_min,
        'max': vis_max,
        'dimensions': dimensions,
        'region': aoi,
    })


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
# 5. Run all three dam cases
# ---------------------------------------------------------------------------
cases = pd.read_csv(CASES_CSV)
thwake = cases[cases['project_name'] == 'Thwake Dam'].iloc[0]
arror = cases[cases['project_name'] == 'Arror Dam'].iloc[0]
kimwarer = cases[cases['project_name'] == 'Kimwarer Dam'].iloc[0]

result = evaluate_dam_case(
    name=thwake['project_name'],
    lat=thwake['latitude'],
    lon=thwake['longitude'],
    # 8km radius as a rough approximation of a reservoir stretching
    # ~10km upstream along two river arms — a circle centered on the
    # dam wall still won't perfectly trace both arms.
    buffer_m=8000,
    claim_start='2018-01-01',
    guardrail_min_hectares=30,      # well above a small community water pan
    design_target_hectares=2900,    # Ministry of Water / Phase I design spec
)

# PROVISIONAL coordinates — confirm visually before trusting either verdict.
arror_result = evaluate_dam_case(
    name=arror['project_name'],
    lat=1.02,
    lon=35.57,
    buffer_m=2000,  # ~280 ha design reservoir
    claim_start='2017-01-01',
    guardrail_min_hectares=20,
    design_target_hectares=280,      # NEMA design spec: 2.8 km2
)

kimwarer_result = evaluate_dam_case(
    name=kimwarer['project_name'],
    lat=0.265,
    lon=35.564,
    buffer_m=1800,  # ~215 ha design reservoir
    claim_start='2017-01-01',
    guardrail_min_hectares=20,
    design_target_hectares=215,      # NEMA design spec: 2.15 km2
)

thwake_resolved = resolve_case(result)
arror_resolved = resolve_case(arror_result)
kimwarer_resolved = resolve_case(kimwarer_result)

summary_df = pd.DataFrame([thwake_resolved, arror_resolved, kimwarer_resolved])
print(summary_df.to_string(index=False))

# Visual sanity check — especially for Arror/Kimwarer's provisional pins.
# A 0.0 ha result should mean "nothing there," not "nothing detectable."
# Open each URL printed below and confirm the AOI actually sits on a
# river valley consistent with the claimed dam site.
print("\nThumbnail URLs (current-period composite):")
print("Thwake:  ", thumbnail_url(result['current_composite'], result['aoi']))
print("Arror:   ", thumbnail_url(arror_result['current_composite'], arror_result['aoi']))
print("Kimwarer:", thumbnail_url(kimwarer_result['current_composite'], kimwarer_result['aoi']))
