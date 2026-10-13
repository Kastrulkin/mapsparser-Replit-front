"""Dedicated consumer for interactive Operator jobs, isolated from long parser work."""
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

from database_manager import DatabaseManager
from services.contact_intelligence_service import (
    claim_next_enrichment_job,
    fail_enrichment_job,
    process_enrichment_job,
)
from services.operator_async_jobs import process_next_operator_async_job


def website_research_enabled():
    return all(
        str(os.getenv(name) or '').strip().lower() in {'1', 'true', 'yes', 'on'}
        for name in ('OPENCLAW_WEBSITE_RESEARCH_ENABLED', 'PROSPECTING_CONTACT_INTELLIGENCE_ENABLED')
    )


def process_reviewed_website_job():
    """Consume the existing queue only for active, approved chat tasks."""
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        job = claim_next_enrichment_job(cursor, reviewed_sources_only=True)
        db.conn.commit()
        if not job:
            return False
        try:
            result = process_enrichment_job(cursor, job)
        except Exception as error:
            db.conn.rollback()
            result = fail_enrichment_job(db.conn.cursor(), job, error)
        db.conn.commit()
        logging.info('Reviewed website job %s: %s', job.get('id'), result.get('status'))
        return True
    except Exception:
        db.conn.rollback()
        # Provider exception strings can include credentials; never log them.
        logging.error('Reviewed website job processing failed')
        return False
    finally:
        db.close()


def poll_once(executor, research_future):
    """A bounded site read must not prevent chat commands, including pause."""
    if research_future is not None and research_future.done():
        try:
            research_future.result()
        except Exception:
            logging.error('Reviewed website consumer failed')
        research_future = None
    if research_future is None and website_research_enabled():
        research_future = executor.submit(process_reviewed_website_job)
    result = process_next_operator_async_job()
    return result, research_future


def main():
    logging.basicConfig(level=logging.INFO)
    research_future = None
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='reviewed-website') as executor:
        while True:
            try:
                result, research_future = poll_once(executor, research_future)
                if result is None:
                    time.sleep(1)
            except Exception:
                logging.error('Operator job processing failed; retrying')
                time.sleep(5)


if __name__ == '__main__':
    main()
