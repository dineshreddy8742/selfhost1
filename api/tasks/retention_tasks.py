"""Automated retention and data purging tasks to keep database and storage lean and secure."""

from datetime import datetime, timezone
from loguru import logger

from api.db import db_client


async def purge_5day_expired_data(ctx=None, days: int = 5) -> int:
    """Scheduled task to purge recordings, transcripts, and logs older than 5 days.

    Runs automatically via ARQ cron worker.
    """
    logger.info(f"Starting automatic 5-day retention purge (older than {days} days)...")
    try:
        count = await db_client.purge_expired_runs_data(days=days)
        logger.info(f"Successfully purged expired logs and recording references for {count} workflow runs.")
        return count
    except Exception as e:
        logger.error(f"Error during automated 5-day retention purge: {e}")
        return 0
