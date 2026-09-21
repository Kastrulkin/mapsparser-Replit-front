"""Folder imports run in the ordinary worker, isolated from slow maintenance calls."""
import logging
import time


def run_forever():
    from services.disk_import import schedule_due
    from services.operator_async_jobs import process_next_operator_async_job
    while True:
        try:
            schedule_due()
            result=process_next_operator_async_job(background=True,background_only=True)
            if result is None:time.sleep(2)
        except Exception:
            logging.exception('Disk import queue will retry')
            time.sleep(5)


def start():
    import os
    import threading
    if not os.getenv('DISK_IMPORT_BUSINESS_IDS','').strip():return
    threading.Thread(target=run_forever,name='disk-import',daemon=True).start()
