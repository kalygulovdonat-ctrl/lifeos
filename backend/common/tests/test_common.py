import json
import logging
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import time_machine

from common.exceptions import error_payload
from common.idempotency import TTL
from common.logging import JsonFormatter, RedactFilter, redact
from common.models import IdempotencyRecord
from common.tasks import purge_idempotency_records
from common.time import intervals_overlap, local_date_of, period_bounds


class TestPeriodBounds:
    def test_day_in_bishkek(self):
        b = period_bounds("Asia/Bishkek", "day", date(2026, 11, 16))
        assert b.start == datetime(2026, 11, 15, 18, 0, tzinfo=UTC)
        assert b.end == datetime(2026, 11, 16, 18, 0, tzinfo=UTC)

    def test_week_starts_monday_by_default(self):
        b = period_bounds("UTC", "week", date(2026, 11, 19))  # Thursday
        assert (b.first_day, b.last_day) == (date(2026, 11, 16), date(2026, 11, 22))

    def test_week_starting_sunday(self):
        b = period_bounds("UTC", "week", date(2026, 11, 19), week_start=7)
        assert (b.first_day, b.last_day) == (date(2026, 11, 15), date(2026, 11, 21))

    def test_month_handles_february(self):
        b = period_bounds("UTC", "month", date(2028, 2, 10))
        assert (b.first_day, b.last_day) == (date(2028, 2, 1), date(2028, 2, 29))

    def test_dst_day_is_23_hours(self):
        b = period_bounds("Europe/Berlin", "day", date(2026, 3, 29))
        assert b.end - b.start == timedelta(hours=23)

    def test_invalid_week_start(self):
        with pytest.raises(ValueError):
            period_bounds("UTC", "week", date(2026, 1, 1), week_start=0)


def test_local_date_crosses_midnight():
    moment = datetime(2026, 11, 16, 20, 0, tzinfo=UTC)
    assert local_date_of(moment, "Asia/Bishkek") == date(2026, 11, 17)
    with pytest.raises(ValueError):
        local_date_of(datetime(2026, 1, 1), "UTC")


def test_half_open_intervals_touching_do_not_overlap():
    t = datetime(2026, 1, 1, 10, tzinfo=UTC)
    h = timedelta(hours=1)
    assert not intervals_overlap(t, t + h, t + h, t + 2 * h)
    assert intervals_overlap(t, t + 2 * h, t + h, t + 3 * h)


class TestRedaction:
    def test_redact_nested(self):
        assert redact({"email": "a@b.c", "password": "x", "nested": {"token": "y"}}) == {
            "email": "a@b.c",
            "password": "***",
            "nested": {"token": "***"},
        }

    def test_inline_secret(self):
        assert "s3cr3t" not in redact("login failed password=s3cr3t for user")

    def test_formatter_output_has_no_secrets(self):
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "auth %s", ("token=abc123",), None)
        record.password = "hunter2"
        RedactFilter().filter(record)
        out = json.loads(JsonFormatter().format(record))
        assert "abc123" not in out["message"]
        assert out["password"] == "***"


@pytest.mark.django_db
class TestHealthAndErrors:
    def test_live(self, anon_client):
        res = anon_client.get("/api/v1/health/live/")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    def test_ready(self, anon_client):
        res = anon_client.get("/api/v1/health/ready/")
        assert res.status_code == 200
        assert res.json()["checks"] == {"database": "ok", "cache": "ok"}

    def test_request_id_echoed(self, anon_client):
        rid = str(uuid.uuid4())
        res = anon_client.get("/api/v1/health/live/", HTTP_X_REQUEST_ID=rid)
        assert res["X-Request-ID"] == rid

    def test_unknown_route_is_json_404(self, anon_client):
        res = anon_client.get("/api/v1/does-not-exist/")
        assert res.status_code == 404
        assert res.json() == error_payload("NOT_FOUND", "Resource not found.")

    def test_malformed_json(self, api_client):
        res = api_client.post("/api/v1/tags/", data="{bad json", content_type="application/json")
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
class TestIdempotency:
    url = "/api/v1/tags/"

    def test_replay_returns_same_response_without_duplicate(self, api_client):
        first = api_client.post(self.url, {"name": "deep-work"}, HTTP_IDEMPOTENCY_KEY="k-1")
        second = api_client.post(self.url, {"name": "deep-work"}, HTTP_IDEMPOTENCY_KEY="k-1")
        assert first.status_code == second.status_code == 201
        assert first.json()["id"] == second.json()["id"]

    def test_same_key_different_body(self, api_client):
        api_client.post(self.url, {"name": "a"}, HTTP_IDEMPOTENCY_KEY="k-2")
        res = api_client.post(self.url, {"name": "b"}, HTTP_IDEMPOTENCY_KEY="k-2")
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    def test_keys_are_per_user(self, api_client, other_client):
        a = api_client.post(self.url, {"name": "shared"}, HTTP_IDEMPOTENCY_KEY="same")
        b = other_client.post(self.url, {"name": "shared"}, HTTP_IDEMPOTENCY_KEY="same")
        assert a.status_code == b.status_code == 201
        assert a.json()["id"] != b.json()["id"]

    def test_error_responses_are_replayed_too(self, api_client):
        bad = {"name": "c", "color": "nope"}
        first = api_client.post(self.url, bad, HTTP_IDEMPOTENCY_KEY="k-3")
        second = api_client.post(self.url, bad, HTTP_IDEMPOTENCY_KEY="k-3")
        assert first.status_code == second.status_code == 400

    def test_without_header_no_record(self, api_client):
        api_client.post(self.url, {"name": "plain"})
        assert not IdempotencyRecord.objects.exists()

    def test_key_too_long(self, api_client):
        res = api_client.post(self.url, {"name": "z"}, HTTP_IDEMPOTENCY_KEY="x" * 65)
        assert res.status_code == 400

    def test_purge_old_records(self, api_client):
        with time_machine.travel(datetime.now(UTC) - TTL - timedelta(hours=1)):
            api_client.post(self.url, {"name": "old"}, HTTP_IDEMPOTENCY_KEY="old")
        api_client.post(self.url, {"name": "new"}, HTTP_IDEMPOTENCY_KEY="new")
        assert purge_idempotency_records() == 1
        assert list(IdempotencyRecord.objects.values_list("key", flat=True)) == ["new"]
