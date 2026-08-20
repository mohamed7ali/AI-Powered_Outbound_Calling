"""Run the background follow-up scheduler until terminated."""

from __future__ import annotations

import os
import time

from outbound_ai.observability.logging import configure_logging, log_event
from outbound_ai.telephony.scheduler import run_follow_up_cycle


def main() -> None:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    interval_seconds = max(5, int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "30")))
    batch_size = max(1, min(100, int(os.getenv("SCHEDULER_BATCH_SIZE", "20"))))
    while True:
        result = run_follow_up_cycle(limit=batch_size)
        log_event(__import__("logging").getLogger(__name__), "follow_up_cycle", **result)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
