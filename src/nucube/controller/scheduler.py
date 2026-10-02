import logging
import threading

from nucube.controller.service import Service

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, service: Service):
        self.service = service
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="nucube-scheduler", daemon=True)

    def run(self) -> None:
        ticks = 0
        while not self.stop_event.is_set():
            try:
                self.service.tick()
                if ticks % 120 == 0:
                    self.service.retention()
                ticks += 1
            except Exception as exc:
                self.service.last_error = type(exc).__name__
                logger.exception(
                    "Scheduler pass failed; capacity remains reserved until reconciled"
                )
            self.stop_event.wait(self.service.config.poll_seconds)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join()  # finish current transition before closing SQLite
