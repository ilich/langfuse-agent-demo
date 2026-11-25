import logging

import pytest

from langfuse_agent_demo.access_log import HealthCheckAccessFilter, quiet_health_checks


def access_record(path: str, status: int, method: str = "GET") -> logging.LogRecord:
    """A log record shaped like the ones uvicorn's access logger emits."""
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:65160", method, path, "1.1", status),
        exc_info=None,
    )


@pytest.mark.parametrize("status", [200, 204])
def test_hides_successful_health_checks(status: int) -> None:
    assert HealthCheckAccessFilter().filter(access_record("/health", status)) is False


def test_hides_health_checks_with_query_string() -> None:
    assert HealthCheckAccessFilter().filter(access_record("/health?x=1", 200)) is False


@pytest.mark.parametrize(
    "record",
    [
        access_record("/health", 503),  # failed checks stay visible
        access_record("/orders/assist", 200, method="POST"),
        access_record("/healthz", 200),
        access_record("/health", 200, method="HEAD"),
    ],
)
def test_keeps_other_requests(record: logging.LogRecord) -> None:
    assert HealthCheckAccessFilter().filter(record) is True


def test_keeps_records_with_unexpected_args() -> None:
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 0, "plain", None, None)
    assert HealthCheckAccessFilter().filter(record) is True


def test_quiet_health_checks_installs_the_filter_once() -> None:
    logger = logging.getLogger("uvicorn.access")
    before = list(logger.filters)
    # Importing the app already installs the filter; start without it.
    logger.filters = [f for f in before if not isinstance(f, HealthCheckAccessFilter)]
    try:
        quiet_health_checks()
        quiet_health_checks()

        installed = [f for f in logger.filters if isinstance(f, HealthCheckAccessFilter)]
        assert len(installed) == 1
    finally:
        logger.filters = before
