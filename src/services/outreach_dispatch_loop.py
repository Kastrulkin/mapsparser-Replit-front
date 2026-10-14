"""Keep the existing dispatch owner responsive while unrelated worker jobs run."""
import logging
import threading


class SerializedDispatchLoop:
    def __init__(self, callback, *, interval=10):
        self.callback = callback
        self.interval = interval
        self._tick_lock = threading.Lock()
        self._start_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def tick(self):
        # Legacy call sites and the dedicated loop share one owner in this worker.
        if not self._tick_lock.acquire(blocking=False):
            return False
        try:
            self.callback()
            return True
        finally:
            self._tick_lock.release()

    def run(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                logging.getLogger(__name__).exception('Outreach dispatch cycle failed')
            self._stop.wait(self.interval)

    def start(self):
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return self._thread
            self._thread = threading.Thread(target=self.run, name='outreach-native-dispatch', daemon=True)
            self._thread.start()
            return self._thread
