"""Keeps uvicorn's access log free of successful health checks.

The client polls ``GET /health`` every few seconds, which would otherwise flood the console with
``"GET /health HTTP/1.1" 200`` lines. Failed checks are still logged.
"""

import logging

ACCESS_LOGGER = "uvicorn.access"
HEALTH_PATH = "/health"


class HealthCheckAccessFilter(logging.Filter):
    """Drops uvicorn access log records for successful ``GET /health`` requests."""

    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn logs '%s - "%s %s HTTP/%s" %d' with (client, method, path, version, status).
        args = record.args
        if not isinstance(args, tuple) or len(args) != 5:
            return True
        _, method, path, _, status = args
        is_health = (
            method == "GET" and isinstance(path, str) and path.split("?", 1)[0] == HEALTH_PATH
        )
        return not (is_health and isinstance(status, int) and status < 400)


def quiet_health_checks() -> None:
    """Install the filter on uvicorn's access logger (idempotent)."""
    logger = logging.getLogger(ACCESS_LOGGER)
    if not any(isinstance(f, HealthCheckAccessFilter) for f in logger.filters):
        logger.addFilter(HealthCheckAccessFilter())
