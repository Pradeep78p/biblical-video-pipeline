"""
Tracks per-video status across the 6 pipeline stages, in SQLite, so a
1200-video batch run is resumable and auditable.

Stages: extract_audio, transcribe, segment, generate_image_queries,
fetch_images, generate_handoff

Status values: pending, running, done, failed, needs_review
"""
import sqlite3
from contextlib import contextmanager

import config

STAGES = [
    "extract_audio",
    "transcribe",
    "segment",
    "generate_image_queries",
    "fetch_images",
    "generate_handoff",
]


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.STATE_DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS video_stage_status (
                video_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (video_id, stage)
            )
            """
        )
        # Query cache lives in the same DB — see cache.py
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS image_query_cache (
                query_normalized TEXT PRIMARY KEY,
                image_id TEXT NOT NULL,
                source TEXT NOT NULL,
                image_url TEXT,
                local_path TEXT NOT NULL,
                license TEXT,
                title TEXT,
                source_page_url TEXT,
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def register_video(video_id: str):
    with get_conn() as conn:
        for stage in STAGES:
            conn.execute(
                """
                INSERT OR IGNORE INTO video_stage_status (video_id, stage, status)
                VALUES (?, ?, 'pending')
                """,
                (video_id, stage),
            )


def set_status(video_id: str, stage: str, status: str, notes: str = None):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE video_stage_status
            SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP,
                attempts = attempts + (CASE WHEN ? = 'running' THEN 1 ELSE 0 END)
            WHERE video_id = ? AND stage = ?
            """,
            (status, notes, status, video_id, stage),
        )


def get_status(video_id: str, stage: str) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM video_stage_status WHERE video_id = ? AND stage = ?",
            (video_id, stage),
        ).fetchone()
        return row[0] if row else "pending"


def videos_ready_for(stage: str, prior_stage: str = None):
    with get_conn() as conn:
        if prior_stage:
            rows = conn.execute(
                """
                SELECT a.video_id FROM video_stage_status a
                JOIN video_stage_status b
                  ON a.video_id = b.video_id AND b.stage = ?
                WHERE a.stage = ? AND a.status = 'pending' AND b.status = 'done'
                """,
                (prior_stage, stage),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT video_id FROM video_stage_status WHERE stage = ? AND status = 'pending'",
                (stage,),
            ).fetchall()
        return [r[0] for r in rows]


def summary():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT stage, status, COUNT(*) FROM video_stage_status GROUP BY stage, status"
        ).fetchall()
    grid = {}
    for stage, status, count in rows:
        grid.setdefault(stage, {})[status] = count
    for stage in STAGES:
        print(stage, grid.get(stage, {}))


if __name__ == "__main__":
    init_db()
    print("Initialized pipeline_state.db")
