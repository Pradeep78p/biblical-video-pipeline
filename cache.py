"""
Caches image search results by NORMALIZED QUERY/TOPIC, not by video or scene.

This is the piece that stops "Exodus Red Sea crossing" from triggering a
fresh image API call every single time it comes up across your 1200 videos.
The first time any scene (in any video) searches for a given topic, the
result is stored here. Every later scene with the same (or near-same)
query reuses it instantly — no API call, no download, no rate-limit hit.

Given a biblical theology course likely repeats the same handful of major
narrative beats (creation, flood, Exodus, exile, crucifixion, etc.) across
many videos, this can cut your real API call volume dramatically below the
6,000-12,000 estimate.
"""
import re

import pipeline_state as state


def normalize_query(query: str) -> str:
    """
    Normalize a search query so near-duplicate phrasing still hits the same
    cache entry, e.g. "Exodus Red Sea crossing" and "the Red Sea crossing
    during the Exodus" should ideally collapse to the same cache key.

    This is a simple normalization (lowercase, strip punctuation, sort
    words, collapse whitespace) — good enough for exact/near-exact repeats.
    If you find many topics phrased too differently to collapse, consider
    upgrading this to an embedding-similarity cache lookup instead of exact
    string matching.
    """
    q = query.lower().strip()
    q = re.sub(r"[^a-z0-9\s]", "", q)
    q = re.sub(r"\s+", " ", q)
    words = sorted(q.split())
    return " ".join(words)


def get_cached(query: str) -> dict | None:
    key = normalize_query(query)
    with state.get_conn() as conn:
        row = conn.execute(
            """
            SELECT image_id, source, image_url, local_path, license, title, source_page_url
            FROM image_query_cache WHERE query_normalized = ?
            """,
            (key,),
        ).fetchone()
    if not row:
        return None
    return {
        "image_id": row[0],
        "source": row[1],
        "image_url": row[2],
        "local_path": row[3],
        "license": row[4],
        "title": row[5],
        "source_page_url": row[6],
        "from_cache": True,
    }


def set_cached(query: str, result: dict):
    key = normalize_query(query)
    with state.get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO image_query_cache
                (query_normalized, image_id, source, image_url, local_path, license, title, source_page_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                result["image_id"],
                result["source"],
                result.get("image_url"),
                result["local_path"],
                result.get("license"),
                result.get("title"),
                result.get("source_page_url"),
            ),
        )


def cache_stats():
    with state.get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM image_query_cache").fetchone()[0]
    print(f"Cached unique image queries: {count}")
    return count
