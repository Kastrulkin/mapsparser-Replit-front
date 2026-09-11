"""Dedicated consumer for interactive Operator jobs, isolated from long parser work."""
import logging
import time
from services.operator_async_jobs import process_next_operator_async_job


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            result = process_next_operator_async_job()
            if result is None:
                time.sleep(1)
        except Exception:
            logging.error('Operator job processing failed; retrying')
            time.sleep(5)


if __name__ == '__main__':
    main()
