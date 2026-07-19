# Databricks notebook source
# MAGIC %md
# MAGIC # Veridex — Evidence Engine, Vector Search & Trust Scorer (v3)
# MAGIC Runs AFTER `01_ingestion_and_cleaning`. Reads `facilities_clean` fresh.
# MAGIC
# MAGIC **Uses a genuine Mosaic AI Vector Search index** — a **Direct Access
# MAGIC Index**, not Delta Sync. The difference: a Delta Sync Index has
# MAGIC Databricks compute the embeddings internally as part of its managed
# MAGIC ingestion pipeline (this hit a severe throughput ceiling on Free Edition —
# MAGIC observed ~1 row/sec, which would have taken over a week for our data).
# MAGIC A Direct Access Index instead lets us compute embeddings ourselves
# MAGIC (fast, controlled, direct calls to the same `databricks-gte-large-en`
# MAGIC Foundation Model endpoint) and upsert the finished vectors straight into
# MAGIC a real Vector Search index. Same product, same underlying embedding
# MAGIC model, same ANN query capability — just without routing through the
# MAGIC pipeline stage that was the actual bottleneck.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Build evidence spans (one per facility per field)

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG = "veridex"
SCHEMA = "gold"

facilities = spark.table(f"{CATALOG}.{SCHEMA}.facilities_clean")

def field_to_span_simple(colname):
    return (
        facilities
        .withColumn("text_span", F.array_join(F.coalesce(F.col(colname), F.array()), ". "))
        .filter(F.length(F.trim(F.col("text_span"))) > 0)
        .withColumn("field_source", F.lit(colname))
        .withColumn("span_id", F.concat_ws("_", F.col("unique_id"), F.lit(colname)))
        .select("span_id", "unique_id", "field_source", "text_span")
    )

def field_to_span_chunked(colname, chunk_size=4):
    arr_col = F.coalesce(F.col(colname), F.array())
    return (
        facilities
        .withColumn("arr", arr_col)
        .withColumn("arr_size", F.size(F.col("arr")))
        .filter(F.col("arr_size") > 0)
        .withColumn("n_chunks", F.ceil(F.col("arr_size") / F.lit(chunk_size)).cast("int"))
        .withColumn("chunk_idx", F.explode(F.sequence(F.lit(0), F.col("n_chunks") - 1)))
        .withColumn("text_span", F.array_join(F.expr(f"slice(arr, chunk_idx * {chunk_size} + 1, {chunk_size})"), ". "))
        .filter(F.length(F.trim(F.col("text_span"))) > 0)
        .withColumn("field_source", F.lit(colname))
        .withColumn("span_id", F.concat_ws("_", F.col("unique_id"), F.lit(colname), F.col("chunk_idx").cast("string")))
        .select("span_id", "unique_id", "field_source", "text_span")
    )

description_span = (
    facilities
    .filter(F.col("description").isNotNull() & (F.length(F.trim(F.col("description"))) > 0))
    .select("unique_id", F.col("description").alias("text_span"))
    .withColumn("field_source", F.lit("description"))
    .withColumn("span_id", F.concat_ws("_", F.col("unique_id"), F.lit("description")))
)

spans_simple = (
    field_to_span_simple("capability").unionByName(field_to_span_simple("procedure"))
    .unionByName(field_to_span_simple("equipment")).unionByName(description_span)
    .withColumn("text_span", F.expr("substring(text_span, 1, 2000)"))
)

spans_chunked = (
    field_to_span_chunked("capability").unionByName(field_to_span_chunked("procedure"))
    .unionByName(field_to_span_chunked("equipment")).unionByName(description_span)
    .withColumn("text_span", F.expr("substring(text_span, 1, 2000)"))
)

n_simple = spans_simple.count()
n_chunked = spans_chunked.count()
print(f"Simple (one span per facility per field): {n_simple} rows")
print(f"Chunked (4 items per span, more granular): {n_chunked} rows")

spans_simple.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.evidence_spans_simple_tmp")
spans_chunked.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.evidence_spans_chunked_tmp")
print("Wrote both candidate span tables — the next section measures real embedding speed and picks one.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Install the Vector Search client

# COMMAND ----------

# MAGIC %pip install --upgrade --force-reinstall databricks-vectorsearch --quiet

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Batch-embed all spans directly (fast — this is what we control)

# COMMAND ----------

from pyspark.sql import functions as F
import mlflow.deployments
import pandas as pd
import time

CATALOG = "veridex"
SCHEMA = "gold"
EMBEDDING_ENDPOINT = "databricks-gte-large-en"
BATCH_SIZE = 150
TIME_BUDGET_MINUTES = 25  # max minutes we're willing to spend embedding — tune if you have more/less time

deploy_client = mlflow.deployments.get_deploy_client("databricks")

spans_simple = spark.table(f"{CATALOG}.{SCHEMA}.evidence_spans_simple_tmp")
spans_chunked = spark.table(f"{CATALOG}.{SCHEMA}.evidence_spans_chunked_tmp")
n_simple = spans_simple.count()
n_chunked = spans_chunked.count()
print(f"Simple: {n_simple} rows | Chunked: {n_chunked} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3a. Measure real throughput, then decide which granularity to use
# MAGIC No guessing — one real batch call, then pick whichever version fits the
# MAGIC time budget. Prefers the more granular (chunked) version when it fits.

# COMMAND ----------

import concurrent.futures

EMBED_BATCH_SIZE = 10
MAX_WORKERS = 6
TIMEOUT_SECONDS = 20

def embed_one_batch(texts):
    response = deploy_client.predict(endpoint=EMBEDDING_ENDPOINT, inputs={"input": texts})
    return [item["embedding"] for item in response["data"]]

# Proven test methodology — a single large batch call (150 texts) was found
# to silently hang on Free Edition somewhere between 5 and 20 texts per call.
# Small batches (10) run in parallel with a timeout is the reliable pattern —
# measured at 15.4 texts/sec with zero failures on a 300-text test.
sample_texts_pd = spans_chunked.select("text_span").limit(300).toPandas()
sample_texts = sample_texts_pd["text_span"].tolist()
sample_batches = [sample_texts[i:i + EMBED_BATCH_SIZE] for i in range(0, len(sample_texts), EMBED_BATCH_SIZE)]

t0 = time.time()
sample_results = [None] * len(sample_batches)
with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_idx = {executor.submit(embed_one_batch, b): idx for idx, b in enumerate(sample_batches)}
    for future in concurrent.futures.as_completed(future_to_idx):
        idx = future_to_idx[future]
        try:
            sample_results[idx] = future.result(timeout=TIMEOUT_SECONDS)
        except Exception:
            pass
elapsed = time.time() - t0
success_count = sum(len(r) for r in sample_results if r)
embedding_dim = len(next(r for r in sample_results if r)[0])
rate = success_count / elapsed

est_minutes_simple = (n_simple / rate) / 60
est_minutes_chunked = (n_chunked / rate) / 60

print(f"Measured rate: {rate:.1f} texts/sec (small batches, parallel, timeout-protected)")
print(f"Estimated time — simple  ({n_simple} spans): {est_minutes_simple:.1f} min")
print(f"Estimated time — chunked ({n_chunked} spans): {est_minutes_chunked:.1f} min")
print(f"Time budget: {TIME_BUDGET_MINUTES} min")

if est_minutes_chunked <= TIME_BUDGET_MINUTES:
    print(f"\n✅ Chunked version fits the budget — using CHUNKED (more granular evidence, better citations).")
    evidence_spans = spans_chunked
    chosen = "chunked"
elif est_minutes_simple <= TIME_BUDGET_MINUTES:
    print(f"\n⚠️ Chunked would exceed budget — using SIMPLE.")
    evidence_spans = spans_simple
    chosen = "simple"
else:
    print(f"\n🚨 Even SIMPLE exceeds the budget at current throughput ({est_minutes_simple:.0f} min). "
          f"Proceeding with SIMPLE anyway since it's the smaller option — this is a reasonable trade given time constraints.")
    evidence_spans = spans_simple
    chosen = "simple (over original budget — proceeding anyway)"

evidence_spans.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.evidence_spans")
print(f"Using: {chosen}. Wrote evidence_spans ({evidence_spans.count()} rows)")

# COMMAND ----------

# Cleanup — temp tables no longer needed now that evidence_spans is written
spark.sql(f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}.evidence_spans_simple_tmp")
spark.sql(f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}.evidence_spans_chunked_tmp")
print("Temp tables dropped")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3b. Full embedding run

# COMMAND ----------

spans_pd = spark.table(f"{CATALOG}.{SCHEMA}.evidence_spans").select("span_id", "unique_id", "field_source", "text_span").toPandas()
print(f"Embedding {len(spans_pd)} spans...")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3b. Full embedding run — small batches, parallel, timeout-protected
# MAGIC Discovered on Free Edition: batches somewhere between 5 and 20 texts can
# MAGIC silently hang (not error — just never return). Fix: small batches (10),
# MAGIC fired in parallel via a thread pool, each with a hard timeout. Anything
# MAGIC that times out gets retried in a second pass instead of blocking forever.

# COMMAND ----------

import concurrent.futures

EMBED_BATCH_SIZE = 10
MAX_WORKERS = 6
TIMEOUT_SECONDS = 20

def embed_one_batch(texts):
    response = deploy_client.predict(endpoint=EMBEDDING_ENDPOINT, inputs={"input": texts})
    return [item["embedding"] for item in response["data"]]

batches = [spans_pd["text_span"].iloc[i:i + EMBED_BATCH_SIZE].tolist() for i in range(0, len(spans_pd), EMBED_BATCH_SIZE)]
print(f"Total batches: {len(batches)} (size {EMBED_BATCH_SIZE} each)")

results = [None] * len(batches)
failed_idxs = []
start = time.time()

with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_idx = {executor.submit(embed_one_batch, b): idx for idx, b in enumerate(batches)}
    completed = 0
    for future in concurrent.futures.as_completed(future_to_idx):
        idx = future_to_idx[future]
        try:
            results[idx] = future.result(timeout=TIMEOUT_SECONDS)
        except Exception as e:
            failed_idxs.append(idx)
        completed += 1
        if completed % 100 == 0:
            print(f"  {completed}/{len(batches)} batches — {time.time() - start:.0f}s elapsed, {len(failed_idxs)} failed so far")

print(f"First pass done in {time.time() - start:.0f}s. Failed batches: {len(failed_idxs)}")

# Retry pass — smaller, sequential, more patient (higher timeout)
if failed_idxs:
    print(f"Retrying {len(failed_idxs)} failed batches sequentially...")
    still_failed = []
    for idx in failed_idxs:
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                results[idx] = ex.submit(embed_one_batch, batches[idx]).result(timeout=60)
        except Exception as e:
            still_failed.append(idx)
    print(f"Retry done. Still failed: {len(still_failed)}")
    if still_failed:
        # Last resort: embed these one text at a time (slowest but most reliable)
        print("Falling back to one-text-at-a-time for remaining failures...")
        for idx in still_failed:
            try:
                embs = []
                for t in batches[idx]:
                    embs.extend(embed_one_batch([t]))
                results[idx] = embs
            except Exception as e:
                print(f"  batch {idx} permanently failed: {e}")
                results[idx] = [[0.0] * embedding_dim] * len(batches[idx])  # placeholder zero vector

all_embeddings = [emb for batch_result in results for emb in batch_result]
print(f"Total embeddings collected: {len(all_embeddings)} (expected {len(spans_pd)})")
spans_pd["embedding"] = all_embeddings[:len(spans_pd)]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Create a Vector Search Direct Access Index

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient

VS_ENDPOINT_NAME = "veridex_vs_endpoint"
VS_INDEX_NAME = f"{CATALOG}.{SCHEMA}.evidence_spans_index"

vsc = VectorSearchClient(disable_notice=True)

existing_endpoints = [e["name"] for e in vsc.list_endpoints().get("endpoints", [])]
if VS_ENDPOINT_NAME not in existing_endpoints:
    print(f"Creating endpoint '{VS_ENDPOINT_NAME}'...")
    vsc.create_endpoint(name=VS_ENDPOINT_NAME, endpoint_type="STANDARD")
else:
    print(f"Endpoint '{VS_ENDPOINT_NAME}' already exists.")

# COMMAND ----------

existing_indexes = []
try:
    existing_indexes = [i["name"] for i in vsc.list_indexes(VS_ENDPOINT_NAME).get("vector_indexes", [])]
except Exception as e:
    print(f"Could not list indexes yet: {e}")

if VS_INDEX_NAME in existing_indexes:
    print(f"Index '{VS_INDEX_NAME}' already exists — deleting to rebuild cleanly.")
    vsc.delete_index(endpoint_name=VS_ENDPOINT_NAME, index_name=VS_INDEX_NAME)
    time.sleep(10)

print(f"Creating Direct Access Index '{VS_INDEX_NAME}'...")
index = vsc.create_direct_access_index(
    endpoint_name=VS_ENDPOINT_NAME,
    index_name=VS_INDEX_NAME,
    primary_key="span_id",
    embedding_dimension=embedding_dim,
    embedding_vector_column="embedding",
    schema={
        "span_id": "string",
        "unique_id": "string",
        "field_source": "string",
        "text_span": "string",
        "embedding": "array<float>",
    },
)
print("Index created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Upsert the embeddings — direct write, no slow managed pipeline

# COMMAND ----------

UPSERT_BATCH = 500
records = spans_pd[["span_id", "unique_id", "field_source", "text_span", "embedding"]].to_dict("records")

print(f"Upserting {len(records)} vectors in batches of {UPSERT_BATCH}...")
start = time.time()
for i in range(0, len(records), UPSERT_BATCH):
    batch = records[i:i + UPSERT_BATCH]
    index.upsert(batch)

print(f"Upsert complete in {time.time() - start:.0f}s")
print(index.describe().get("status"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Define target capabilities and query the REAL index

# COMMAND ----------

CAPABILITY_TAXONOMY = {
    "ICU": "intensive care unit ICU critical care with ventilator support and continuous monitoring",
    "NICU": "neonatal intensive care unit NICU for newborn and premature infant critical care",
    "Emergency": "24/7 emergency department trauma bay emergency room casualty services",
    "Maternity": "maternity obstetrics labor and delivery gynecology childbirth services",
    "Oncology": "oncology cancer treatment chemotherapy radiation therapy tumor care",
    "Trauma": "trauma center trauma surgery major injury polytrauma emergency surgery",
}

cap_names = list(CAPABILITY_TAXONOMY.keys())
cap_texts = list(CAPABILITY_TAXONOMY.values())
cap_response = deploy_client.predict(endpoint=EMBEDDING_ENDPOINT, inputs={"input": cap_texts})
cap_embeddings = {name: item["embedding"] for name, item in zip(cap_names, cap_response["data"])}

NUM_RESULTS_PER_QUERY = 4000
match_rows = []
for cap_name, cap_vec in cap_embeddings.items():
    results = index.similarity_search(
        query_vector=cap_vec,
        columns=["span_id", "unique_id", "field_source", "text_span"],
        num_results=NUM_RESULTS_PER_QUERY,
    )
    data = results.get("result", {}).get("data_array", [])
    print(f"{cap_name}: {len(data)} results from Vector Search index")
    for row in data:
        span_id, unique_id, field_source, text_span, score = row
        match_rows.append((cap_name, unique_id, field_source, text_span, float(score)))

matches_pd = pd.DataFrame(match_rows, columns=["capability", "unique_id", "field_source", "text_span", "score"])
print(f"\nTotal capability-span match rows: {len(matches_pd)}")
print("\nScore distribution by field_source:")
print(matches_pd.groupby("field_source")["score"].describe())
print("\nSample high-scoring matches (spot-check these look right):")
print(matches_pd.sort_values("score", ascending=False).head(15)[["capability", "field_source", "text_span", "score"]].to_string())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Build the trust score
# MAGIC Field-aware, per the source extraction schema's own field definitions —
# MAGIC check Section 6's printed score distribution before trusting these
# MAGIC threshold values.

# COMMAND ----------

FIELD_WEIGHT = {"capability": 1.0, "procedure": 0.85, "equipment": 0.8, "description": 0.6}

matches_pd["weighted_score"] = matches_pd["score"] * matches_pd["field_source"].map(FIELD_WEIGHT)
if matches_pd["weighted_score"].isna().any():
    unknown_sources = sorted(matches_pd.loc[matches_pd["weighted_score"].isna(), "field_source"].dropna().unique())
    raise RuntimeError(f"Missing FIELD_WEIGHT for field_source values: {unknown_sources}")

best_idx = matches_pd.groupby(["unique_id", "capability"])["weighted_score"].idxmax()
best_matches = matches_pd.loc[best_idx].reset_index(drop=True)

# Data-driven thresholds from the actual winning-match score distribution:
# bottom 40% no_signal, next 30% weak_signal, next 20% likely, top 10% verified.
LOW_THRESH = float(best_matches["weighted_score"].quantile(0.40))
MED_THRESH = float(best_matches["weighted_score"].quantile(0.70))
HIGH_THRESH = float(best_matches["weighted_score"].quantile(0.90))

print("Weighted-score percentile thresholds (absolute values):")
print(f"  LOW_THRESH  / p40 = {LOW_THRESH:.12f}")
print(f"  MED_THRESH  / p70 = {MED_THRESH:.12f}")
print(f"  HIGH_THRESH / p90 = {HIGH_THRESH:.12f}")
print(best_matches["weighted_score"].describe(percentiles=[0.40, 0.70, 0.90]))

def classify(row):
    if row["weighted_score"] >= HIGH_THRESH:
        return "verified"
    elif row["weighted_score"] >= MED_THRESH:
        return "likely"
    elif row["weighted_score"] >= LOW_THRESH:
        return "weak_signal"
    return "no_signal"

best_matches["evidence_status"] = best_matches.apply(classify, axis=1)

# Semantic keyword guard for the middle confidence bands only.
# Verified and no_signal classifications remain untouched.
CAPABILITY_KEYWORDS = {
    "ICU": ["icu", "intensive care", "critical care", "ventilator"],
    "NICU": ["nicu", "neonatal", "newborn intensive"],
    "Emergency": ["emergency", "24/7", "casualty", "trauma bay"],
    "Maternity": ["maternity", "obstetric", "gynecology", "labor", "delivery", "childbirth"],
    "Oncology": ["oncology", "cancer", "chemotherapy", "radiation therapy", "tumor"],
    "Trauma": ["trauma", "polytrauma", "major injury"],
}
unknown_capabilities = sorted(set(best_matches["capability"]) - set(CAPABILITY_KEYWORDS))
if unknown_capabilities:
    raise RuntimeError(f"Missing keyword guards for capabilities: {unknown_capabilities}")

def has_capability_keyword(row):
    text_span = "" if pd.isna(row["text_span"]) else str(row["text_span"]).casefold()
    return any(keyword.casefold() in text_span for keyword in CAPABILITY_KEYWORDS[row["capability"]])

best_matches["keyword_confirmed"] = best_matches.apply(has_capability_keyword, axis=1).astype(bool)
pre_guard_status = best_matches["evidence_status"].copy()
likely_downgrade = (pre_guard_status == "likely") & ~best_matches["keyword_confirmed"]
weak_downgrade = (pre_guard_status == "weak_signal") & ~best_matches["keyword_confirmed"]
best_matches.loc[likely_downgrade, "evidence_status"] = "weak_signal"
best_matches.loc[weak_downgrade, "evidence_status"] = "no_signal"
print(f"Likely rows downgraded to weak_signal: {int(likely_downgrade.sum())}")
print(f"Weak-signal rows downgraded to no_signal: {int(weak_downgrade.sum())}")

status_order = ["verified", "likely", "weak_signal", "no_signal"]
distribution = (
    best_matches.groupby(["capability", "evidence_status"]).size()
    .unstack(fill_value=0)
    .reindex(columns=status_order, fill_value=0)
)
print("Evidence status distribution per capability:")
print(distribution)
print("Evidence status percentages per capability:")
print((distribution.div(distribution.sum(axis=1), axis=0) * 100).round(2))

# Stop before Section 8 writes if classification is missing a status or degenerates.
required_statuses = set(status_order)
missing_global = required_statuses - set(best_matches["evidence_status"].unique())
missing_by_capability = {
    capability: sorted(required_statuses - set(group["evidence_status"].unique()))
    for capability, group in best_matches.groupby("capability")
    if required_statuses - set(group["evidence_status"].unique())
}
max_status_share = float(best_matches["evidence_status"].value_counts(normalize=True).max())
if missing_global or missing_by_capability or max_status_share >= 0.95:
    raise RuntimeError(
        "Degenerate evidence classification ? refusing to write capability_evidence. "
        f"missing_global={sorted(missing_global)}, "
        f"missing_by_capability={missing_by_capability}, "
        f"max_status_share={max_status_share:.4f}"
    )

for status in ["verified", "likely", "weak_signal"]:
    print(f"\nFive sample rows for {status}:")
    sample = (
        best_matches[best_matches["evidence_status"] == status]
        .sort_values("weighted_score", ascending=False)
        .head(5)[["capability", "field_source", "text_span", "score", "weighted_score", "keyword_confirmed"]]
    )
    print(sample.to_string(index=False))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Combine with richness_prior, write final gold table

# COMMAND ----------

# Normalize Vector Search's small internal score scale to a 0-100 percentile rank.
# This changes trust scoring only; evidence_status and its thresholds remain untouched.
best_matches["percentile_rank"] = best_matches["weighted_score"].rank(pct=True) * 100
print("Weighted-score percentile-rank distribution:")
print(best_matches["percentile_rank"].describe(percentiles=[0.25, 0.50, 0.75]))

best_matches_spark = spark.createDataFrame(best_matches)
facilities = spark.table(f"{CATALOG}.{SCHEMA}.facilities_clean")
richness = facilities.select("unique_id", "richness_prior", "source_type_count", "source_url_count")

capability_evidence = (
    best_matches_spark
    .join(richness, on="unique_id", how="left")
    .withColumn(
        "trust_score_pct",
        F.least(
            F.lit(100),
            F.greatest(
                F.lit(0),
                F.bround(
                    F.col("percentile_rank") * 0.75
                    + F.coalesce(F.col("richness_prior"), F.lit(0)) * 100 * 0.25
                ),
            ),
        ).cast("int"),
    )
    # Keep trust confidence consistent with the final post-keyword-guard status.
    .withColumn(
        "trust_score_pct",
        F.least(
            F.col("trust_score_pct"),
            F.when(F.col("evidence_status") == "no_signal", F.lit(30))
            .when(F.col("evidence_status") == "weak_signal", F.lit(60))
            .when(F.col("evidence_status") == "likely", F.lit(90))
            .otherwise(F.lit(100)),
        ).cast("int"),
    )
    .withColumn("trust_score", F.col("trust_score_pct").cast("double") / F.lit(100.0))
    .withColumn(
        "confirm_message",
        F.lit("Every result must be confirmed by direct outreach to the facility — this is decision support, not a verified directory."),
    )
    .select(
        "unique_id", "capability", "evidence_status", "keyword_confirmed", "trust_score", "trust_score_pct",
        "field_source", "text_span", "score", "richness_prior", "confirm_message",
    )
)

capability_evidence.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{CATALOG}.{SCHEMA}.capability_evidence"
)
print(f"Wrote {CATALOG}.{SCHEMA}.capability_evidence  ({capability_evidence.count()} rows)")
display(capability_evidence.groupBy("capability", "evidence_status").count().orderBy("capability", "evidence_status"))