"""Test fixture: Mock QPU for testing without real hardware."""

import time
from qos.backends.types import QPU


class TestQPU(QPU):
    """Mock QPU for testing that sleeps and returns 42."""

    def run(self, *args, **kwargs):
        """Sleep for 5 seconds and return 42."""
        time.sleep(5)
        return 42
