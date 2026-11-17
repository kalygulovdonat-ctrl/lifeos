from datetime import UTC, datetime, timedelta

import pytest

from apps.schedule.models import Event, EventReschedule, EventSeries
from apps.schedule.recurrence import Recurrence, expand
from apps.schedule.selectors import severity
from common.exceptions import DomainValidationError

pytestmark = pytest.mark.django_db
URL = "/api/v1/events/"


def ev(client, start, end, time_type="PERSONAL", title="Event", force=False, **extra):
    payload = {"title": title, "start_at": start, "end_at": end, "time_type": time_type, **extra}
    return client.post(URL + ("?force=true" if force else ""), payload, format="json")


def day(client, date="2026-11-18"):
    return client.get(f"{URL}?from={date}&to={date}").json()["results"]


class TestEvents:
    def test_create_and_list(self, api_client):
        res = ev(api_client, "2026-11-18T10:00:00+06:00", "2026-11-18T11:00:00+06:00", title="Лекция")
        assert res.status_code == 201, res.json()
        body = res.json()
        assert body["timezone"] == "Asia/Bishkek"
        assert body["status"] == "PLANNED"
        assert body["warnings"] == []
        assert [e["title"] for e in day(api_client)] == ["Лекция"]

    def test_end_must_follow_start(self, api_client):
        res = ev(api_client, "2026-11-18T11:00:00+06:00", "2026-11-18T11:00:00+06:00")
        assert res.status_code == 400
        assert "end_at" in res.json()["error"]["details"]

    def test_naive_datetime_rejected(self, api_client):
        res = ev(api_client, "2026-11-18T10:00:00", "2026-11-18T11:00:00")
        assert res.status_code == 400

    def test_range_is_local_days(self, api_client):
        # 23:30 local on the 18th is 17:30 UTC — still the 18th for the user.
        ev(api_client, "2026-11-18T23:30:00+06:00", "2026-11-18T23:50:00+06:00")
        assert len(day(api_client, "2026-11-18")) == 1
        assert len(day(api_client, "2026-11-19")) == 0

    def test_update_records_reschedule(self, api_client):
        e = ev(api_client, "2026-11-18T10:00:00+06:00", "2026-11-18T11:00:00+06:00").json()
        res = api_client.post(
            f"{URL}{e['id']}/reschedule/",
            {
                "start_at": "2026-11-18T12:00:00+06:00",
                "end_at": "2026-11-18T13:00:00+06:00",
                "reason": "Пробки",
            },
            format="json",
        )
        assert res.status_code == 200
        move = EventReschedule.objects.get(event_id=e["id"])
        assert move.reason == "Пробки"
        assert move.old_start_at == datetime(2026, 11, 18, 4, tzinfo=UTC)

    def test_status_and_delete(self, api_client):
        e = ev(api_client, "2026-11-18T10:00:00+06:00", "2026-11-18T11:00:00+06:00").json()
        res = api_client.post(f"{URL}{e['id']}/status/", {"status": "DONE"}, format="json")
        assert res.json()["status"] == "DONE"
        assert api_client.delete(f"{URL}{e['id']}/").status_code == 204
        assert day(api_client) == []
        assert Event.all_objects.get(id=e["id"]).deleted_at is not None

    def test_isolation(self, api_client, other_client):
        e = ev(api_client, "2026-11-18T10:00:00+06:00", "2026-11-18T11:00:00+06:00").json()
        assert other_client.get(f"{URL}{e['id']}/").status_code == 404
        assert other_client.delete(f"{URL}{e['id']}/").status_code == 404
        assert day(other_client) == []

    def test_range_limit(self, api_client):
        res = api_client.get(f"{URL}?from=2026-01-01&to=2026-12-31")
        assert res.status_code == 400


class TestConflicts:
    def test_matrix(self):
        assert severity("FIXED", "FIXED") == "CONFLICT"
        assert severity("FIXED", "FOCUS") == "WARNING"
        assert severity("FIXED", "BUFFER") == "INFO"
        assert severity("FOCUS", "FREE") == "INFO"
        assert severity("REST", "REST") == "INFO"
        assert severity("REST", "FIXED") == "WARNING"
        assert severity("BUFFER", "FIXED") == "INFO"

    def test_fixed_on_fixed_is_409_unless_forced(self, api_client):
        ev(api_client, "2026-11-18T10:00:00+06:00", "2026-11-18T11:00:00+06:00", "FIXED", title="Пара")
        res = ev(api_client, "2026-11-18T10:30:00+06:00", "2026-11-18T11:30:00+06:00", "FIXED")
        assert res.status_code == 409
        err = res.json()["error"]
        assert err["code"] == "SCHEDULE_CONFLICT"
        assert err["details"]["conflicting"][0]["title"] == "Пара"

        res = ev(api_client, "2026-11-18T10:30:00+06:00", "2026-11-18T11:30:00+06:00", "FIXED", force=True)
        assert res.status_code == 201
        assert res.json()["warnings"][0]["severity"] == "CONFLICT"

    def test_focus_overlap_is_warning(self, api_client):
        ev(api_client, "2026-11-18T10:00:00+06:00", "2026-11-18T11:00:00+06:00", "FIXED", title="Пара")
        res = ev(api_client, "2026-11-18T10:30:00+06:00", "2026-11-18T12:00:00+06:00", "FOCUS")
        assert res.status_code == 201
        w = res.json()["warnings"]
        assert w[0]["code"] == "SCHEDULE_OVERLAP" and w[0]["severity"] == "WARNING"

    def test_touching_intervals_do_not_conflict(self, api_client):
        ev(api_client, "2026-11-18T10:00:00+06:00", "2026-11-18T11:00:00+06:00", "FIXED")
        res = ev(api_client, "2026-11-18T11:00:00+06:00", "2026-11-18T12:00:00+06:00", "FIXED")
        assert res.status_code == 201
        assert res.json()["warnings"] == []

    def test_cancelled_events_ignored(self, api_client):
        e = ev(api_client, "2026-11-18T10:00:00+06:00", "2026-11-18T11:00:00+06:00", "FIXED").json()
        api_client.post(f"{URL}{e['id']}/status/", {"status": "CANCELLED"}, format="json")
        assert (
            ev(api_client, "2026-11-18T10:00:00+06:00", "2026-11-18T11:00:00+06:00", "FIXED").status_code
            == 201
        )

    def test_check_and_list_conflicts(self, api_client):
        e = ev(api_client, "2026-11-18T10:00:00+06:00", "2026-11-18T11:00:00+06:00", "FIXED").json()
        res = api_client.post(
            f"{URL}check-conflicts/",
            {
                "start_at": "2026-11-18T10:15:00+06:00",
                "end_at": "2026-11-18T10:45:00+06:00",
                "time_type": "FIXED",
            },
            format="json",
        )
        assert res.json()["has_conflict"] is True
        res = api_client.post(
            f"{URL}check-conflicts/",
            {
                "start_at": "2026-11-18T10:15:00+06:00",
                "end_at": "2026-11-18T10:45:00+06:00",
                "time_type": "FIXED",
                "exclude_id": e["id"],
            },
            format="json",
        )
        assert res.json()["has_conflict"] is False
        ev(api_client, "2026-11-18T10:30:00+06:00", "2026-11-18T12:00:00+06:00", "BUFFER")
        pairs = api_client.get(f"{URL}conflicts/?from=2026-11-18&to=2026-11-18").json()["results"]
        assert pairs[0]["severity"] == "INFO"

    def test_moving_into_conflict_is_409(self, api_client):
        ev(api_client, "2026-11-18T10:00:00+06:00", "2026-11-18T11:00:00+06:00", "FIXED")
        e = ev(api_client, "2026-11-18T12:00:00+06:00", "2026-11-18T13:00:00+06:00", "FIXED").json()
        res = api_client.patch(
            f"{URL}{e['id']}/",
            {"start_at": "2026-11-18T10:30:00+06:00", "end_at": "2026-11-18T11:30:00+06:00"},
            format="json",
        )
        assert res.status_code == 409


class TestSeries:
    def weekly(self, client, **extra):
        return ev(
            client,
            "2026-11-16T09:00:00+06:00",
            "2026-11-16T10:30:00+06:00",
            "FIXED",
            title="Матанализ",
            recurrence={"freq": "WEEKLY", "by_day": ["MO", "WE"], **extra},
        )

    def week(self, client):
        return client.get(f"{URL}?from=2026-11-16&to=2026-11-22").json()["results"]

    def test_expands_virtually(self, api_client):
        res = self.weekly(api_client)
        assert res.status_code == 201, res.json()
        assert res.json()["recurrence"]["by_day"] == ["MO", "WE"]
        items = self.week(api_client)
        assert [i["start_at"][:10] for i in items] == ["2026-11-16", "2026-11-18"]
        assert all(i["id"] is None and i["occurrence_key"] for i in items)
        assert Event.objects.count() == 0

    def test_count_and_until(self, api_client):
        self.weekly(api_client, count=1)
        assert len(self.week(api_client)) == 1
        EventSeries.objects.all().delete()
        self.weekly(api_client, until="2026-11-17")
        assert len(self.week(api_client)) == 1

    def test_edit_one_occurrence(self, api_client):
        self.weekly(api_client)
        wed = self.week(api_client)[1]
        epoch = wed["occurrence_key"].split(":")[1]
        res = api_client.patch(
            f"/api/v1/event-series/{wed['series_id']}/occurrences/{epoch}/",
            {
                "title": "Перенесли",
                "start_at": "2026-11-18T14:00:00+06:00",
                "end_at": "2026-11-18T15:30:00+06:00",
            },
            format="json",
        )
        assert res.status_code == 200, res.json()
        items = self.week(api_client)
        assert [i["title"] for i in items] == ["Матанализ", "Перенесли"]
        assert items[1]["id"] is not None
        assert items[1]["original_start_at"] == wed["start_at"]

    def test_cancel_occurrence(self, api_client):
        self.weekly(api_client)
        mon = self.week(api_client)[0]
        epoch = mon["occurrence_key"].split(":")[1]
        res = api_client.delete(f"/api/v1/event-series/{mon['series_id']}/occurrences/{epoch}/")
        assert res.status_code == 204
        assert [i["start_at"][:10] for i in self.week(api_client)] == ["2026-11-18"]

    def test_unknown_occurrence_404(self, api_client):
        sid = self.weekly(api_client).json()["series_id"]
        bogus = int(datetime(2026, 11, 17, 3, tzinfo=UTC).timestamp())  # a Tuesday
        assert api_client.delete(f"/api/v1/event-series/{sid}/occurrences/{bogus}/").status_code == 404

    def test_this_and_following(self, api_client):
        self.weekly(api_client)
        wed = self.week(api_client)[1]
        epoch = wed["occurrence_key"].split(":")[1]
        res = api_client.patch(
            f"/api/v1/event-series/{wed['series_id']}/occurrences/{epoch}/",
            {"scope": "following", "title": "Новый курс"},
            format="json",
        )
        assert res.status_code == 200, res.json()
        assert [i["title"] for i in self.week(api_client)] == ["Матанализ", "Новый курс"]
        nxt = api_client.get(f"{URL}?from=2026-11-23&to=2026-11-29").json()["results"]
        assert {i["title"] for i in nxt} == {"Новый курс"}
        assert EventSeries.objects.count() == 2

    def test_series_conflicts_with_fixed(self, api_client):
        ev(api_client, "2026-11-25T09:30:00+06:00", "2026-11-25T10:00:00+06:00", "FIXED", title="Экзамен")
        res = self.weekly(api_client)
        assert res.status_code == 409

    def test_delete_series(self, api_client):
        sid = self.weekly(api_client).json()["series_id"]
        assert api_client.delete(f"/api/v1/event-series/{sid}/").status_code == 204
        assert self.week(api_client) == []

    def test_series_patch(self, api_client):
        sid = self.weekly(api_client).json()["series_id"]
        res = api_client.patch(
            f"/api/v1/event-series/{sid}/",
            {"title": "Алгебра", "recurrence": {"freq": "DAILY"}},
            format="json",
        )
        assert res.status_code == 200, res.json()
        assert len(self.week(api_client)) == 7

    def test_dst_keeps_local_wall_clock(self):
        rec = Recurrence(freq="WEEKLY")
        tz = "Europe/Berlin"
        first = datetime(2026, 10, 19, 7, tzinfo=UTC)  # 09:00 CEST
        starts = expand(
            rule=rec.to_rrule(),
            dtstart_at=first,
            tz_name=tz,
            duration=timedelta(hours=1),
            window_start=first,
            window_end=first + timedelta(days=15),
        )
        # After the switch to CET on 25 Oct, 09:00 local is 08:00 UTC.
        assert [s.hour for s in starts] == [7, 8, 8]

    def test_rrule_validation(self):
        with pytest.raises(DomainValidationError):
            Recurrence(freq="HOURLY").to_rrule()
        with pytest.raises(DomainValidationError):
            Recurrence(freq="DAILY", count=3, until=datetime(2026, 1, 1).date()).to_rrule()
        assert Recurrence.from_rrule(
            Recurrence(freq="MONTHLY", by_month_day=[1, 15]).to_rrule()
        ).by_month_day == [
            1,
            15,
        ]


class TestFreeSlots:
    def test_free_time(self, api_client):
        # profile window 07:00-23:00 local
        ev(api_client, "2026-11-18T09:00:00+06:00", "2026-11-18T12:00:00+06:00", "FIXED")
        ev(api_client, "2026-11-18T11:00:00+06:00", "2026-11-18T13:00:00+06:00", "FOCUS")
        ev(api_client, "2026-11-18T18:00:00+06:00", "2026-11-18T19:00:00+06:00", "FREE")
        ev(api_client, "2026-11-18T20:00:00+06:00", "2026-11-18T20:10:00+06:00", "BUFFER")
        body = api_client.get("/api/v1/schedule/free-slots/?date=2026-11-18").json()
        assert body["busy_minutes"] == 4 * 60 + 10
        assert body["reserved_free_minutes"] == 60
        starts = [s["start_at"][11:16] for s in body["slots"]]
        assert starts == ["01:00", "07:00", "14:10"]  # UTC: 07:00, 13:00, 20:10 local
        assert body["free_minutes"] == 16 * 60 - (4 * 60 + 10)
