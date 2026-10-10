import json
import logging

from app.core.logging import JsonFormatter, request_id_ctx


def _format(message: str, **extra: object) -> dict[str, object]:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    parsed: dict[str, object] = json.loads(JsonFormatter().format(record))
    return parsed


def test_emits_one_json_object_with_core_fields() -> None:
    payload = _format("hello")

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "hello"
    assert "timestamp" in payload


def test_includes_request_id_when_inside_a_request() -> None:
    token = request_id_ctx.set("req-1")
    try:
        payload = _format("inside")
    finally:
        request_id_ctx.reset(token)

    assert payload["request_id"] == "req-1"


def test_drops_fields_that_are_not_on_the_allow_list() -> None:
    payload = _format("body logged by mistake", request_body='{"password": "x"}', path="/a")

    assert "request_body" not in payload
    assert payload["path"] == "/a"
