import logging
import os
from typing import Any, Dict, List, Optional

from google.cloud import bigquery

from .config import get_logger

# ---------- Config ----------
PROJECT_ID    = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID") or "grestok-app-dev"
BQ_DATASET    = os.environ.get("BQ_DATASET", "grestok_master")
BQ_TABLE      = os.environ.get("BQ_TABLE", "courses_search")            # table with embeddings
BQ_MODEL      = os.environ.get("BQ_MODEL", "text_embedding_model")      # remote model
BQ_LOCATION   = os.environ.get("BQ_LOCATION", "asia-south1")
FRACTION_IVF  = float(os.environ.get("IVF_FRACTION", "0.05"))           # 5% of lists
DEFAULT_THRESH = float(os.environ.get("SIM_THRESHOLD", "0.35"))         # cosine DISTANCE threshold (smaller = closer)
EMBED_DIM     = int(os.environ.get("EMBED_DIM", "768"))                # must match how you built embeddings

logger = get_logger("grestok.bigquery")

client = bigquery.Client(project=PROJECT_ID)


def search_and_count(
    query_text: str,
    limit: int = 15,
    offset: int = 0,
    threshold: Optional[float] = None,
    use_brute_force: bool = False,
) -> Dict[str, Any]:
    """
    Performs a pure vector similarity search over the courses embedding index in BigQuery.
    Provide a richly described natural-language query that already encodes any desired constraints
    (country, level, budget, duration, etc.), because no structured filters are applied server-side.

    Returns:
      {
        "hits": [ { ui fields... , "similarity": float }, ... ],
        "next_offset": int|None,
        "totals": { "programs": int, "schools": int, "threshold": float }
      }
    """
    thresh = threshold if threshold is not None else DEFAULT_THRESH
    topk = max(1, min(2000, limit + offset + 1))
    options_json = '{"use_brute_force": true}' if use_brute_force else f'{{"fraction_lists_to_search": {FRACTION_IVF} }}'

    logger.info(
        "Running BigQuery vector search | query=%r limit=%d offset=%d threshold=%.3f brute_force=%s topk=%d",
        query_text,
        limit,
        offset,
        thresh,
        use_brute_force,
        topk,
    )

    tbl_search = f"`{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`"
    mdl = f"`{PROJECT_ID}.{BQ_DATASET}.{BQ_MODEL}`"
    logger.debug("Using BigQuery resources | table=%s model=%s", tbl_search, mdl)
    # ---------- HITS (IVF) ----------
    # Only select fields that are STORED in the index + distance.
    top_hits_sql = f"""
WITH query_vec AS (
  SELECT ml_generate_embedding_result AS qvec
  FROM ML.GENERATE_EMBEDDING(
    MODEL {mdl},
    (SELECT @q AS content),
    STRUCT(TRUE AS flatten_json_output,
           'RETRIEVAL_QUERY' AS task_type,
           {EMBED_DIM} AS output_dimensionality)  -- literal
  )
),
vs AS (
  SELECT
    base.gt_program_id,
    base.gt_school_id,
    base.name,
    base.currency,
    base.programLevel,
    base.program_category,
    base.tuition,
    base.school_name,
    base.school_city,
    base.school_province,
    base.school_countryCode,
    distance
  FROM VECTOR_SEARCH(
    (
      SELECT
        -- select ONLY columns stored in the index + embedding
        gt_program_id, gt_school_id,
        name, currency, programLevel, program_category, tuition,
        school_name, school_city, school_province, school_countryCode,
        embedding
      FROM {tbl_search}
    ),
    'embedding',
    (SELECT qvec FROM query_vec),
    query_column_to_search => 'qvec',
    top_k => @topk,
    distance_type => 'COSINE',
    options => '{options_json}'
  )
)
SELECT *
FROM vs
ORDER BY (1.0 - distance) DESC
LIMIT @limit OFFSET @offset
"""

    params_hits = [
        bigquery.ScalarQueryParameter("q", "STRING", query_text),
        bigquery.ScalarQueryParameter("topk", "INT64", topk),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
    ]
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Top hits SQL:\n%s", top_hits_sql)

    hits_job = client.query(
        top_hits_sql,
        job_config=bigquery.QueryJobConfig(query_parameters=params_hits),
        location=BQ_LOCATION,
    )
    top_rows = list(hits_job.result())

    hits: List[Dict[str, Any]] = []
    for r in top_rows:
        row_dict = dict(r.items())
        program_id = row_dict.get("gt_program_id")
        if program_id is None:
            logger.warning("Skipping result without program id | row=%s", row_dict)
            continue
        school_id = row_dict.get("gt_school_id")
        program_level = row_dict.get("programLevel") or row_dict.get("program_category")
        distance = row_dict.get("distance")
        hits.append({
            "program_id": str(program_id),
            "school_id": str(school_id) if school_id is not None else None,
            "name": row_dict.get("name"),
            "currency": row_dict.get("currency"),
            "programLevel": program_level,
            "program_category": row_dict.get("program_category"),
            "tuition": float(row_dict.get("tuition")) if row_dict.get("tuition") is not None else None,
            "school_name": row_dict.get("school_name"),
            "school_city": row_dict.get("school_city"),
            "school_province": row_dict.get("school_province"),
            "school_countryCode": row_dict.get("school_countryCode"),
            "similarity": float(1.0 - distance) if distance is not None else None,
        })

    logger.info(
        "Vector search returned %d hits | limit=%d offset=%d", len(hits), limit, offset
    )
    if not hits:
        logger.warning("Vector search yielded no results for query '%s'", query_text)

    # ---------- COUNTS (exact over same filters) ----------
    counts_sql = f"""
WITH query_vec AS (
  SELECT ml_generate_embedding_result AS qvec
  FROM ML.GENERATE_EMBEDDING(
    MODEL {mdl},
    (SELECT @q AS content),
    STRUCT(TRUE AS flatten_json_output,
           'RETRIEVAL_QUERY' AS task_type,
           {EMBED_DIM} AS output_dimensionality)  -- literal
  )
),
scored AS (
  SELECT
    school_countryCode,
    gt_school_id,
    ML.DISTANCE(embedding, (SELECT qvec FROM query_vec), 'COSINE') AS cos_dist
  FROM {tbl_search}
)
SELECT
  COUNTIF(cos_dist <= @thresh) AS programs_total,
  COUNT(DISTINCT IF(cos_dist <= @thresh, gt_school_id, NULL)) AS schools_total,
  COUNT(DISTINCT IF(cos_dist <= @thresh, school_countryCode, NULL)) AS countries_total
FROM scored
"""
    params_counts = [
        bigquery.ScalarQueryParameter("q", "STRING", query_text),
        bigquery.ScalarQueryParameter("thresh", "FLOAT64", thresh),
    ]
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Counts SQL:\n%s", counts_sql)

    totals_job = client.query(
        counts_sql,
        job_config=bigquery.QueryJobConfig(query_parameters=params_counts),
        location=BQ_LOCATION,
    )
    totals_row = list(totals_job.result())[0]
    totals = {
        "programs": int(totals_row["programs_total"] or 0),
        "schools": int(totals_row["schools_total"] or 0),
        "countries": int(totals_row["countries_total"] or 0),
        "threshold": thresh,
    }

    next_offset = (offset + limit) if totals["programs"] > (offset + limit) else None
    logger.info(
        "Vector search totals | programs=%d schools=%d countries=%d threshold=%.3f next_offset=%s",
        totals["programs"],
        totals["schools"],
        totals["countries"],
        totals["threshold"],
        next_offset,
    )

    if logger.isEnabledFor(logging.DEBUG):
        preview = hits[:3]
        logger.debug("Sample hits: %s", preview)

    return {"hits": hits, "next_offset": next_offset, "totals": totals}
