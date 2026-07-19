# Databricks notebook source
# MAGIC %md
# MAGIC # Veridex — District Resolution: Point-in-Polygon Fallback
# MAGIC Runs AFTER `01_ingestion_and_cleaning`. Reads the already-written gold
# MAGIC tables fresh from Delta (not in-memory state), resolves any remaining
# MAGIC unresolved facilities using true point-in-polygon matching against
# MAGIC 2019-vintage district boundaries (matching NFHS-5's 2019-21 survey
# MAGIC period), and updates `facilities_clean` in place.
# MAGIC
# MAGIC Uses pure `shapely` (no GDAL/geopandas) for portability across
# MAGIC Databricks environments — per the organizer's own recommended
# MAGIC geospatial approach (point-in-polygon against district boundaries).

# COMMAND ----------

# MAGIC %pip install shapely --quiet

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

from pyspark.sql import functions as F
import requests
import difflib
import re
import shapely.geometry as sgeom
from shapely.strtree import STRtree

CATALOG = "veridex"
SCHEMA = "gold"

facilities_gold = spark.table(f"{CATALOG}.{SCHEMA}.facilities_clean")
nfhs5 = spark.table(f"{CATALOG}.{SCHEMA}.nfhs5_clean")

n_total = facilities_gold.count()
n_already_resolved = facilities_gold.filter(F.col("district_resolved")).count()
print(f"Starting point: {n_already_resolved} / {n_total} resolved ({n_already_resolved/n_total:.1%})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Download and decode district boundaries
# MAGIC 2019-vintage, 734 districts — matches NFHS-5's 2019-21 survey period,
# MAGIC which should reduce naming mismatches versus current-day sources.

# COMMAND ----------

DISTRICT_BOUNDARY_URL = "https://raw.githubusercontent.com/guneetnarula/indian-district-boundaries/master/topojson/india-districts-2019-734.json"

resp = requests.get(DISTRICT_BOUNDARY_URL, timeout=60)
resp.raise_for_status()
topo = resp.json()
print(f"Downloaded: {len(resp.content)/1e6:.1f} MB")

transform = topo.get("transform")
scale = transform["scale"] if transform else [1, 1]
translate = transform["translate"] if transform else [0, 0]

def decode_arc(arc):
    coords = []
    x, y = 0, 0
    for dx, dy in arc:
        x += dx
        y += dy
        coords.append((x * scale[0] + translate[0], y * scale[1] + translate[1]))
    return coords

decoded_arcs = [decode_arc(a) for a in topo["arcs"]]

def arc_coords(index):
    return list(reversed(decoded_arcs[~index])) if index < 0 else decoded_arcs[index]

def ring_coords(arc_indices):
    coords = []
    for idx in arc_indices:
        pts = arc_coords(idx)
        if coords and coords[-1] == pts[0]:
            coords.extend(pts[1:])
        else:
            coords.extend(pts)
    return coords

obj_name = list(topo["objects"].keys())[0]
geometries = topo["objects"][obj_name]["geometries"]

district_records = []
for g in geometries:
    props = g.get("properties", {})
    gtype = g["type"]
    geom = None
    if gtype == "Polygon":
        rings = [ring_coords(r) for r in g["arcs"]]
        if rings:
            geom = sgeom.Polygon(rings[0], rings[1:])
    elif gtype == "MultiPolygon":
        polys = []
        for poly_arcs in g["arcs"]:
            rings = [ring_coords(r) for r in poly_arcs]
            if rings:
                polys.append(sgeom.Polygon(rings[0], rings[1:]))
        if polys:
            geom = sgeom.MultiPolygon(polys)
    if geom is not None and geom.is_valid:
        district_records.append({
            "district": props.get("district"),
            "state": props.get("st_nm"),
            "geometry": geom,
        })

def normalize_name(s):
    return re.sub(r"\s+", " ", str(s).strip().lower()) if s else None

for r in district_records:
    r["district_norm_poly"] = normalize_name(r["district"])
    r["state_norm_poly"] = normalize_name(r["state"])

print(f"Decoded {len(district_records)} district polygons")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Point-in-polygon match for still-unresolved facilities

# COMMAND ----------

tree = STRtree([r["geometry"] for r in district_records])

unresolved_pd = (
    facilities_gold
    .filter(~F.col("district_resolved") & F.col("coordinates_valid"))
    .select("unique_id", "latitude", "longitude")
    .toPandas()
)
print(f"Attempting point-in-polygon for {len(unresolved_pd)} facilities")

def find_district(lon, lat):
    pt = sgeom.Point(lon, lat)
    for idx in tree.query(pt):
        if district_records[idx]["geometry"].contains(pt):
            return district_records[idx]["district_norm_poly"], district_records[idx]["state_norm_poly"]
    return None, None

results = unresolved_pd.apply(lambda row: find_district(row["longitude"], row["latitude"]), axis=1)
unresolved_pd["district_norm_poly"] = results.apply(lambda x: x[0])
unresolved_pd["state_norm_poly"] = results.apply(lambda x: x[1])

n_poly_matched = unresolved_pd["district_norm_poly"].notna().sum()
print(f"Matched to a district polygon: {n_poly_matched} / {len(unresolved_pd)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Reconcile polygon district names against NFHS-5
# MAGIC Same exact-then-fuzzy pattern as the PIN-based reconciliation — never
# MAGIC guess across state boundaries, never force a match below threshold.

# COMMAND ----------

nfhs_pairs = nfhs5.select("state_norm", "district_norm").distinct().toPandas()

# Verified false positive: "Purba" (East) and "Paschim" (West) Bardhaman are
# different, non-overlapping districts in West Bengal — a shared "bardhaman"
# substring pushed this above the fuzzy cutoff despite being geographically
# wrong. NFHS-5 genuinely has no separate Purba Bardhaman entry; leave unmatched
# rather than force it onto the wrong half of the district.
DISTRICT_ALIAS_BLOCKLIST_POLY = {
    ("west bengal", "purba bardhaman", "paschim barddhaman"),
}

def match_to_nfhs(state_norm_poly, district_norm_poly):
    if state_norm_poly is None or district_norm_poly is None:
        return None, None
    candidates = nfhs_pairs[nfhs_pairs.state_norm == state_norm_poly]["district_norm"].tolist()
    if not candidates:
        return None, None
    if district_norm_poly in candidates:
        return district_norm_poly, "poly_exact"
    close = difflib.get_close_matches(district_norm_poly, candidates, n=1, cutoff=0.72)
    if close:
        candidate = close[0]
        if (state_norm_poly, district_norm_poly, candidate) in DISTRICT_ALIAS_BLOCKLIST_POLY:
            return None, None
        return candidate, "poly_fuzzy"
    return None, None

nfhs_matches = unresolved_pd.apply(
    lambda row: match_to_nfhs(row["state_norm_poly"], row["district_norm_poly"]), axis=1
)
unresolved_pd["nfhs_district_norm_matched"] = nfhs_matches.apply(lambda x: x[0])
unresolved_pd["poly_match_type"] = nfhs_matches.apply(lambda x: x[1])

poly_resolved_pd = unresolved_pd[unresolved_pd["nfhs_district_norm_matched"].notna()][
    ["unique_id", "state_norm_poly", "nfhs_district_norm_matched", "poly_match_type"]
]
print(f"Resolved to an NFHS-5 district via polygon: {len(poly_resolved_pd)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Merge back into facilities_clean and overwrite

# COMMAND ----------

if len(poly_resolved_pd) > 0:
    poly_resolved_spark = spark.createDataFrame(poly_resolved_pd)

    poly_with_district_name = poly_resolved_spark.join(
        nfhs5.select(
            F.col("state_norm").alias("pg_state_norm"),
            F.col("district_norm").alias("pg_district_norm"),
            F.col("district_name").alias("poly_nfhs_district_name"),
        ),
        (poly_resolved_spark["state_norm_poly"] == F.col("pg_state_norm")) &
        (poly_resolved_spark["nfhs_district_norm_matched"] == F.col("pg_district_norm")),
        "left",
    ).select("unique_id", "poly_nfhs_district_name", "poly_match_type").dropDuplicates(["unique_id"])

    facilities_gold = (
        facilities_gold
        .join(poly_with_district_name, on="unique_id", how="left")
        .withColumn("nfhs_district_name", F.coalesce(F.col("nfhs_district_name"), F.col("poly_nfhs_district_name")))
        .withColumn(
            "district_match_type",
            F.when(F.col("district_resolved"), F.col("district_match_type"))
             .otherwise(F.coalesce(F.col("poly_match_type"), F.col("district_match_type")))
        )
        .withColumn("district_resolved", F.col("nfhs_district_name").isNotNull())
        .drop("poly_nfhs_district_name", "poly_match_type")
    )
else:
    print("No additional facilities resolved via polygon fallback.")

n_final = facilities_gold.filter(F.col("district_resolved")).count()
print(f"Final resolution: {n_final} / {n_total}  ({n_final/n_total:.1%})")

# COMMAND ----------

facilities_gold.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{SCHEMA}.facilities_clean")
print(f"Updated {CATALOG}.{SCHEMA}.facilities_clean")

# COMMAND ----------

display(facilities_gold.groupBy("district_match_type").count())