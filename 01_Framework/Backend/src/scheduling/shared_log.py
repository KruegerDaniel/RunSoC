"""Thread-safe shared execution log implementation using deque and Lock."""
from collections import deque
from threading import Lock


class SharedExecutionLog:
    """Thread-safe execution log that stores task execution records with a maximum size limit."""

    def __init__(self, max_size=1000):
        self.log = deque(maxlen=max_size)
        self.lock = Lock()
        self.callbacks = []

    def append(self, entry):
        """Append a new entry to the execution log thread-safely."""
        with self.lock:
            self.log.append(entry)
            for callback in self.callbacks:
                callback(entry)

    def get_log(self):
        """Get a copy of the current execution log thread-safely."""
        with self.lock:
            return list(self.log)

    def register_callback(self, callback):
        """Register a callback to be called when a new entry is appended to the log."""
        self.callbacks.append(callback)
