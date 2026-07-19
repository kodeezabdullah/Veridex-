# Databricks notebook source
# MAGIC %md
# MAGIC # Veridex — Ingestion & Cleaning
# MAGIC Cleans the three source tables (facilities, PIN code directory, NFHS-5 district
# MAGIC health indicators) and produces validated, joined "gold" Delta tables for the
# MAGIC vector search + trust scoring stages.
# MAGIC
# MAGIC **Design principle:** never silently convert "missing" into "no" or "0".
# MAGIC Missing stays NULL and gets an explicit `*_reported` flag downstream.

# COMMAND ----------

from pyspark.sql import functions as F, types as T
from pyspark.sql.window import Window

# Real data has malformed numeric values (e.g. literal "NA" text instead of
# NULL — confirmed in the PIN directory's lat/lon columns). Plain .cast()
# throws under Databricks' ANSI mode instead of returning NULL. try_cast
# returns NULL for anything it can't convert — use this everywhere instead
# of .cast() for columns that might contain messy real-world data.
def safe_cast(col_name, target_type):
    return F.expr(f"try_cast(`{col_name}` as {target_type})")

SOURCE_CATALOG = "databricks_virtue_foundation_dataset_dais_2026"
SOURCE_SCHEMA = "virtue_foundation_dataset"

# Shared/Marketplace catalogs are read-only — write outputs to our own catalog.
OUTPUT_CATALOG = "veridex"
OUTPUT_SCHEMA = "gold"

spark.sql(f"CREATE CATALOG IF NOT EXISTS {OUTPUT_CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {OUTPUT_CATALOG}.{OUTPUT_SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Facilities — load + parse

# COMMAND ----------

facilities_raw = spark.table(f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.facilities")

# Columns stored as JSON-array strings — parse into real arrays.
LIST_COLUMNS = [
    "phone_numbers", "websites", "specialties", "procedure",
    "equipment", "capability", "source_types", "source_ids", "source_urls",
]

facilities = facilities_raw
for c in LIST_COLUMNS:
    facilities = facilities.withColumn(
        c, F.from_json(F.col(c), T.ArrayType(T.StringType()))
    )

# Numeric fields are stored as strings. Safe-cast: non-numeric / empty -> NULL,
# never 0. This IS the fix for the "data desert vs medical desert" problem —
# NULL means "unknown", not "absent".
facilities = (
    facilities
    .withColumn("numberDoctors_clean", safe_cast("numberDoctors", "int"))
    .withColumn("capacity_clean", safe_cast("capacity", "int"))
    .withColumn("yearEstablished_clean", safe_cast("yearEstablished", "int"))
    .withColumn("doctors_reported", F.col("numberDoctors_clean").isNotNull())
    .withColumn("capacity_reported", F.col("capacity_clean").isNotNull())
)

# Boolean-ish signal fields, also stored as strings.
BOOL_COLUMNS = ["affiliated_staff_presence", "custom_logo_presence", "acceptsVolunteers"]
for c in BOOL_COLUMNS:
    facilities = facilities.withColumn(c, safe_cast(c, "boolean"))

NUMERIC_SIGNAL_COLUMNS = [
    "recency_of_page_update", "distinct_social_media_presence_count",
    "number_of_facts_about_the_organization", "post_metrics_post_count",
    "engagement_metrics_n_followers", "engagement_metrics_n_likes",
    "engagement_metrics_n_engagements",
]
for c in NUMERIC_SIGNAL_COLUMNS:
    facilities = facilities.withColumn(c, safe_cast(c, "double"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Coordinate validation
# MAGIC Real bug found in sample data: at least one facility has lat/lon that lands
# MAGIC in the Atlantic Ocean, not India. Flag anything outside India's rough bounding
# MAGIC box instead of silently trusting it — never use unvalidated coordinates for
# MAGIC spatial aggregation.

# COMMAND ----------

INDIA_LAT_RANGE = (6.0, 38.0)
INDIA_LON_RANGE = (68.0, 98.0)

facilities = facilities.withColumn(
    "coordinates_valid",
    (F.col("latitude").between(*INDIA_LAT_RANGE)) &
    (F.col("longitude").between(*INDIA_LON_RANGE))
)

n_total = facilities.count()
n_invalid = facilities.filter(~F.col("coordinates_valid")).count()
print(f"Facilities with out-of-India coordinates: {n_invalid} / {n_total}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Corroboration / richness prior
# MAGIC A transparent, rule-based feature — NOT the final trust score. This is one
# MAGIC input the trust-scoring agent will combine with claim-level evidence checks.
# MAGIC Keeping it separate and explainable satisfies the "honest explanations"
# MAGIC requirement (don't let a heuristic masquerade as proof).

# COMMAND ----------

facilities = (
    facilities
    .withColumn("source_type_count", F.size(F.coalesce(F.col("source_types"), F.array())))
    .withColumn("source_url_count",
                F.size(F.array_except(F.coalesce(F.col("source_urls"), F.array()), F.array(F.lit(None).cast("string")))))
    .withColumn(
        "richness_prior",
        # 0..1 heuristic: more independent sources + more organizational facts
        # + verified digital presence => higher prior. Documented, not hidden.
        F.least(
            F.lit(1.0),
            (
                F.least(F.col("source_type_count") / F.lit(4.0), F.lit(0.4)) +
                F.least(F.col("source_url_count") / F.lit(5.0), F.lit(0.3)) +
                (F.col("affiliated_staff_presence").cast("int") * F.lit(0.15)) +
                (F.col("custom_logo_presence").cast("int") * F.lit(0.15))
            )
        )
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. PIN code directory — dedupe to district-level
# MAGIC Row grain is *post office*, not PIN. A PIN can map to more than one district
# MAGIC in raw data — take the **mode** (most frequent) district per PIN rather than
# MAGIC an arbitrary first row.

# COMMAND ----------

pincode_raw = spark.table(f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.india_post_pincode_directory")

pin_district_counts = (
    pincode_raw
    .filter(F.col("district").isNotNull() & F.col("statename").isNotNull())
    .filter(F.upper(F.trim(F.col("statename"))) != "NA")  # garbage state entry found in raw data
    .groupBy("pincode", "district", "statename")
    .agg(F.count("*").alias("cnt"))
)

w = Window.partitionBy("pincode").orderBy(F.desc("cnt"))
pincode_lookup = (
    pin_district_counts
    .withColumn("rank", F.row_number().over(w))
    .filter(F.col("rank") == 1)
    .drop("rank", "cnt")
    .withColumn("district_norm", F.lower(F.trim(F.regexp_replace(F.col("district"), r"\s+", " "))))
    .withColumn("state_norm", F.lower(F.trim(F.regexp_replace(F.col("statename"), r"\s+", " "))))
)

# Average geocoded lat/lon per PIN as a fallback centroid (many rows are NA —
# average() ignores nulls automatically, giving NULL only if ALL rows lack coords).
pincode_geo = (
    pincode_raw
    # Marketplace listing notes ~12,600 rows carry literal "NA" text here —
    # try_cast turns that into NULL instead of crashing.
    .withColumn("lat_d", safe_cast("latitude", "double"))
    .withColumn("lon_d", safe_cast("longitude", "double"))
    .groupBy("pincode")
    .agg(
        F.avg("lat_d").alias("pin_centroid_lat"),
        F.avg("lon_d").alias("pin_centroid_lon"),
    )
)

pincode_lookup = pincode_lookup.join(pincode_geo, on="pincode", how="left")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. NFHS-5 — clean suppressed values and inconsistent types
# MAGIC `*` = suppressed (NULL, not 0). Parenthesized values are small-sample
# MAGIC estimates — strip parens, keep the number, flag as low-confidence.

# COMMAND ----------

nfhs5_raw = spark.table(f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.nfhs_5_district_health_indicators")

nfhs5 = nfhs5_raw
string_pct_cols = [c for c, t in nfhs5_raw.dtypes if c.endswith("_pct") and t == "string"]

for c in string_pct_cols:
    flag_col = f"{c}_low_confidence"
    nfhs5 = (
        nfhs5
        .withColumn(flag_col, F.col(c).rlike(r"^\(.*\)$"))          # parenthesized -> low-confidence flag
        .withColumn(c, F.regexp_replace(F.col(c), r"[()]", ""))     # strip parens, keep number
        .withColumn(c, F.when(F.col(c).isin("*", "NA", "N/A", ""), None).otherwise(F.col(c)))  # suppressed/missing -> NULL
        .withColumn(c, safe_cast(c, "double"))
    )

# State-name reconciliation between NFHS-5 and the PIN directory. Found by
# diagnostic: NFHS-5 has a genuine source typo ("Maharastra") plus several
# "&" vs "and" / prefix differences against the PIN directory's naming.
STATE_ALIAS_FIX = {
    "maharastra": "maharashtra",                 # typo in NFHS-5 source data
    "nct of delhi": "delhi",
    "jammu & kashmir": "jammu and kashmir",
    "andaman & nicobar islands": "andaman and nicobar islands",
    "dadra and nagar haveli & daman and diu": "the dadra and nagar haveli and daman and diu",
}
state_fix_map = F.create_map([F.lit(x) for pair in STATE_ALIAS_FIX.items() for x in pair])

nfhs5 = (
    nfhs5
    .withColumn("district_norm", F.lower(F.trim(F.regexp_replace(F.col("district_name"), r"\s+", " "))))
    .withColumn("state_norm_raw", F.lower(F.trim(F.regexp_replace(F.col("state_ut"), r"\s+", " "))))
    .withColumn("state_norm", F.coalesce(state_fix_map[F.col("state_norm_raw")], F.col("state_norm_raw")))
)

print(f"NFHS-5 percentage columns needing cleanup: {len(string_pct_cols)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5b. District name reconciliation (fuzzy match)
# MAGIC District renaming (e.g. Bangalore -> Bengaluru, Gulbarga -> Kalaburagi)
# MAGIC breaks exact-string joins. Exact matches pass straight through; close
# MAGIC misspellings/renames get a fuzzy match above a similarity threshold;
# MAGIC anything below the threshold stays unmatched and flagged — never guessed.

# COMMAND ----------

import difflib

# Known official district renames (e.g. Karnataka's 2014 renaming) — verified
# explicitly rather than left to a fuzzy-match threshold, since these are
# large spelling changes, not typos.
DISTRICT_ALIAS_FIX = {
    ("karnataka", "bangalore"): "bengaluru urban",
    ("karnataka", "bangalore rural"): "bengaluru rural",
    ("karnataka", "belgaum"): "belagavi",
    ("karnataka", "bellary"): "ballari",
    ("karnataka", "chikmagalur"): "chikkamagaluru",
    ("karnataka", "gulbarga"): "kalaburagi",
    ("karnataka", "mysore"): "mysuru",
    ("karnataka", "shimoga"): "shivamogga",
    ("karnataka", "tumkur"): "tumakuru",
    ("karnataka", "bijapur"): "vijayapura",
    ("karnataka", "chamarajanagar"): "chamarajanagara",
    ("karnataka", "davanagere"): "davangere",
    # Confirmed via national-level diagnostic against exact NFHS-5 district lists.
    ("haryana", "gurgaon"): "gurugram",
    ("west bengal", "north twenty four pargana"): "24 paraganas north",
    ("west bengal", "south twenty four pargana"): "24 paraganas south",
    ("west bengal", "hugli"): "hooghly",
    ("west bengal", "paschim medinipur"): "medinipur west",
    ("west bengal", "purba medinipur"): "medinipur east",
    ("west bengal", "koch bihar"): "coochbehar",
    ("uttar pradesh", "allahabad"): "prayagraj",
    ("uttar pradesh", "faizabad"): "ayodhya",
    ("andhra pradesh", "sri potti sriramulu nello"): "spsr nellore",
    ("punjab", "sahibzada ajit singh nagar"): "s.a.s nagar",
    ("punjab", "muktsar"): "sri muktsar sahib",
    ("tamil nadu", "thoothukkudi"): "tuticorin",
    ("jharkhand", "purbi singhbhum"): "east singhbum",
}

nfhs_pairs = nfhs5.select("state_norm", "district_norm").distinct().toPandas()
pin_pairs = pincode_lookup.select("state_norm", "district_norm").distinct().toPandas()

# Verified false positives from difflib fuzzy matching — short district names
# sharing a generic suffix ("nagar", "pur") can score above the cutoff despite
# being genuinely different, unrelated districts. Block explicitly rather
# than raising the global threshold (which would drop good matches too).
DISTRICT_ALIAS_BLOCKLIST = {
    ("uttar pradesh", "kanshiram nagar", "kushi nagar"),  # Kasganj vs Kushinagar — different districts
}

fuzzy_rows = []
for state in nfhs_pairs["state_norm"].unique():
    nfhs_d = nfhs_pairs[nfhs_pairs.state_norm == state]["district_norm"].tolist()
    pin_d = pin_pairs[pin_pairs.state_norm == state]["district_norm"].tolist()
    if not pin_d:
        continue
    for nd in nfhs_d:
        alias_target = DISTRICT_ALIAS_FIX.get((state, nd))
        if alias_target and alias_target in pin_d:
            fuzzy_rows.append((state, nd, alias_target, "known_alias"))
        elif nd in pin_d:
            fuzzy_rows.append((state, nd, nd, "exact"))
        else:
            close = difflib.get_close_matches(nd, pin_d, n=1, cutoff=0.72)
            candidate = close[0] if close else None
            if candidate and (state, nd, candidate) in DISTRICT_ALIAS_BLOCKLIST:
                candidate = None
            fuzzy_rows.append((state, nd, candidate, "fuzzy" if candidate else "unmatched"))

district_alias = spark.createDataFrame(
    fuzzy_rows, schema=["state_norm", "nfhs_district_norm", "pin_district_norm_matched", "match_type"]
)
display(district_alias.groupBy("match_type").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Resolve each facility to a district
# MAGIC Path: facility postcode -> PIN lookup (mode district/state) -> normalized
# MAGIC join to NFHS-5. Unmatched stays NULL and gets flagged — never guessed.

# COMMAND ----------

facilities_with_pin = (
    facilities
    .withColumn("zip_clean", F.regexp_extract(F.col("address_zipOrPostcode"), r"(\d{6})", 1))
    .withColumn("zip_clean", F.when(F.col("zip_clean") != "", safe_cast("zip_clean", "long")))
    .join(
        pincode_lookup.withColumnRenamed("district_norm", "pin_district_norm")
                       .withColumnRenamed("state_norm", "pin_state_norm"),
        F.col("zip_clean") == F.col("pincode"),
        "left",
    )
)

facilities_with_alias = (
    facilities_with_pin
    .join(
        district_alias.withColumnRenamed("state_norm", "alias_state_norm"),
        (facilities_with_pin["pin_state_norm"] == F.col("alias_state_norm")) &
        (facilities_with_pin["pin_district_norm"] == F.col("pin_district_norm_matched")),
        "left",
    )
)

facilities_gold = (
    facilities_with_alias
    .join(
        nfhs5.select(
            "state_norm", "district_norm",
            F.col("district_name").alias("nfhs_district_name"),
            F.col("state_ut").alias("nfhs_state_ut"),
        ),
        (facilities_with_alias["pin_state_norm"] == F.col("state_norm")) &
        (facilities_with_alias["nfhs_district_norm"] == F.col("district_norm")),
        "left",
    )
    .withColumn("district_resolved", F.col("nfhs_district_name").isNotNull())
    .withColumn("district_match_type", F.coalesce(F.col("match_type"), F.lit("unmatched")))
)

# The district_alias join can fan out if a PIN district matches more than one
# NFHS-5 entry — collapse back to one row per facility.
facilities_gold = facilities_gold.dropDuplicates(["unique_id"])

n_resolved = facilities_gold.filter(F.col("district_resolved")).count()
print(f"Facilities resolved to an NFHS-5 district: {n_resolved} / {n_total}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6b. Spatial fallback for facilities with no zip-based match
# MAGIC Some facilities have a missing/malformed postal code, or a postal code
# MAGIC not present in the directory, but still have validated coordinates.
# MAGIC For these, fall back to the nearest PIN centroid within 25km — capped
# MAGIC so a facility never gets assigned to a district that's actually far
# MAGIC away (better to leave it unmatched than guess wrong).

# COMMAND ----------

from pyspark.sql.window import Window as W2

still_unresolved = (
    facilities_gold
    .filter(~F.col("district_resolved") & F.col("coordinates_valid"))
    .select("unique_id", "latitude", "longitude")
)

pin_centroids = (
    pincode_lookup
    .filter(F.col("pin_centroid_lat").isNotNull() & F.col("pin_centroid_lon").isNotNull())
    .select("pincode", "district_norm", "state_norm", "pin_centroid_lat", "pin_centroid_lon")
)

R_KM = 6371.0
candidates = still_unresolved.crossJoin(F.broadcast(pin_centroids)).withColumn(
    "distance_km",
    F.lit(2) * F.lit(R_KM) * F.asin(
        F.sqrt(
            F.pow(F.sin((F.radians(F.col("pin_centroid_lat")) - F.radians(F.col("latitude"))) / 2), 2) +
            F.cos(F.radians(F.col("latitude"))) * F.cos(F.radians(F.col("pin_centroid_lat"))) *
            F.pow(F.sin((F.radians(F.col("pin_centroid_lon")) - F.radians(F.col("longitude"))) / 2), 2)
        )
    )
)

nearest_w = W2.partitionBy("unique_id").orderBy("distance_km")
nearest_pin = (
    candidates
    .withColumn("rank", F.row_number().over(nearest_w))
    .filter((F.col("rank") == 1) & (F.col("distance_km") <= 25))
    .select(
        "unique_id",
        F.col("district_norm").alias("spatial_district_norm"),
        F.col("state_norm").alias("spatial_state_norm"),
        "distance_km",
    )
)
print(f"Facilities resolvable via spatial fallback (<=25km): {nearest_pin.count()}")

# Route the spatial guess through the SAME district_alias table, since the
# same naming mismatches (Bengaluru/Bangalore etc.) apply here too.
spatial_with_alias = nearest_pin.join(
    district_alias.withColumnRenamed("state_norm", "sp_alias_state_norm"),
    (nearest_pin["spatial_state_norm"] == F.col("sp_alias_state_norm")) &
    (nearest_pin["spatial_district_norm"] == F.col("pin_district_norm_matched")),
    "left",
)

spatial_resolved = (
    spatial_with_alias
    .join(
        nfhs5.select(
            F.col("state_norm").alias("sp_nfhs_state_norm"),
            F.col("district_norm").alias("sp_nfhs_district_norm"),
            F.col("district_name").alias("spatial_nfhs_district_name"),
        ),
        (spatial_with_alias["spatial_state_norm"] == F.col("sp_nfhs_state_norm")) &
        (spatial_with_alias["nfhs_district_norm"] == F.col("sp_nfhs_district_norm")),
        "left",
    )
    .filter(F.col("spatial_nfhs_district_name").isNotNull())
    .select(
        "unique_id",
        F.col("spatial_nfhs_district_name"),
        F.col("spatial_state_norm"),
        F.lit("spatial_fallback").alias("spatial_match_type"),
    )
    .dropDuplicates(["unique_id"])
)

facilities_gold = (
    facilities_gold
    .join(spatial_resolved, on="unique_id", how="left")
    .withColumn(
        "nfhs_district_name",
        F.coalesce(F.col("nfhs_district_name"), F.col("spatial_nfhs_district_name")),
    )
    .withColumn(
        "district_match_type",
        F.when(F.col("district_resolved"), F.col("district_match_type"))
         .otherwise(F.coalesce(F.col("spatial_match_type"), F.col("district_match_type"))),
    )
    .withColumn("district_resolved", F.col("nfhs_district_name").isNotNull())
    .drop("spatial_nfhs_district_name", "spatial_state_norm", "spatial_match_type")
)

n_resolved_final = facilities_gold.filter(F.col("district_resolved")).count()
print(f"Facilities resolved after spatial fallback: {n_resolved_final} / {n_total}  ({n_resolved_final/n_total:.1%})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Write gold tables

# COMMAND ----------

(facilities_gold.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{OUTPUT_CATALOG}.{OUTPUT_SCHEMA}.facilities_clean"))
(pincode_lookup.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{OUTPUT_CATALOG}.{OUTPUT_SCHEMA}.pincode_lookup"))
(nfhs5.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{OUTPUT_CATALOG}.{OUTPUT_SCHEMA}.nfhs5_clean"))

print("Done. Wrote:")
print(f"  {OUTPUT_CATALOG}.{OUTPUT_SCHEMA}.facilities_clean  ({facilities_gold.count()} rows)")
print(f"  {OUTPUT_CATALOG}.{OUTPUT_SCHEMA}.pincode_lookup     ({pincode_lookup.count()} rows)")
print(f"  {OUTPUT_CATALOG}.{OUTPUT_SCHEMA}.nfhs5_clean        ({nfhs5.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Quick sanity checks — run these before moving on

# COMMAND ----------

# Should be a small number, not zero and not everything — sanity check the bug we found
display(facilities_gold.filter(~F.col("coordinates_valid")).select("name", "address_city", "address_stateOrRegion", "latitude", "longitude"))

# COMMAND ----------

# District resolution rate by state — low numbers here mean the PIN/name join needs work
display(
    facilities_gold.groupBy("address_stateOrRegion")
    .agg(
        F.count("*").alias("total"),
        F.sum(F.col("district_resolved").cast("int")).alias("resolved"),
    )
    .withColumn("resolution_rate", F.round(F.col("resolved") / F.col("total"), 2))
    .orderBy(F.desc("total"))
)

# COMMAND ----------

# Breakdown of HOW each facility got resolved — exact / fuzzy / unmatched.
# Good demo evidence: shows the system reconciles real naming differences
# transparently instead of hiding them.
display(facilities_gold.groupBy("district_match_type").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Diagnose the remaining "no PIN match" facilities
# MAGIC These never got a district_alias chance at all — the gap is upstream
# MAGIC of the alias table, either a missing/malformed postal code or a PIN
# MAGIC not present in the directory.

# COMMAND ----------

no_pin_match = facilities_gold.filter(F.col("pin_district_norm").isNull())
print(f"No PIN match total: {no_pin_match.count()}")
print(f"  zip_clean is NULL (no 6-digit code found in address): {no_pin_match.filter(F.col('zip_clean').isNull()).count()}")
print(f"  zip_clean found but that pincode isn't in the directory: {no_pin_match.filter(F.col('zip_clean').isNotNull()).count()}")