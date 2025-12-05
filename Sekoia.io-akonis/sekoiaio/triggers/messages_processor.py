import signal
from collections.abc import Callable
from queue import Queue
from threading import Event, Thread

from gevent.pool import Pool


class MessagesProcessor(Thread):
    """
    Class in charge of processing messages received by the trigger
    """

    QUEUE_TIMEOUT = 1

    _queue: Queue
    _stop_event: Event
    _pool: Pool

    def __init__(self, callback: Callable):
        super().__init__()
        self._queue = Queue()
        self._stop_event = Event()  # Event to notify we must stop the thread
        self._pool = Pool(100)
        self._callback: Callable = callback

        # Register signal to terminate thread
        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)

    def run(self):
        while not self._stop_event.is_set():
            self._handle_message()
        self._pool.join()

    def push_message(self, message: str):
        self._queue.put(message)

    def exit(self, _, __):
        # Exit signal received, asking the processor to stop
        self.stop()

    def stop(self):
        """
        Stop the thread.
        """
        self._stop_event.set()

    def _handle_message(self):
        try:
            message = self._queue.get(timeout=self.QUEUE_TIMEOUT)
            self._pool.spawn(self._callback, message)
        except Exception:
            # Don't block indefinitely to get a chance to exit properly
            pass
