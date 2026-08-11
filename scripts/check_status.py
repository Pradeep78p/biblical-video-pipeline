"""
Quick view of where every video stands across all 6 stages, plus cache
stats. Run any time to check batch-run progress.

Usage:
    python scripts/check_status.py
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import pipeline_state as state
import cache

if __name__ == "__main__":
    state.init_db()
    state.summary()
    print()
    cache.cache_stats()
