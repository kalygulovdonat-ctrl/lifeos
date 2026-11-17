"""Wellness (SDD §4.10). Observations only — LifeOS never draws medical conclusions."""

from __future__ import annotations

from django.db import models
from django.db.models import F, Q

from common.models import OwnedModel, choices_check


class CheckinSource(models.TextChoices):
    MANUAL = "MANUAL"
    JOURNAL = "JOURNAL"
    REVIEW = "REVIEW"


def _scale(field: str) -> Q:
    return Q(**{f"{field}__isnull": True}) | Q(**{f"{field}__gte": 1, f"{field}__lte": 10})


class StateCheckin(OwnedModel):
    recorded_at = models.DateTimeField()
    local_date = models.DateField()
    timezone = models.CharField(max_length=64)
    mood = models.SmallIntegerField(null=True, blank=True)
    energy = models.SmallIntegerField(null=True, blank=True)
    stress = models.SmallIntegerField(null=True, blank=True)
    note = models.CharField(max_length=500, default="", blank=True)
    source = models.CharField(max_length=8, choices=CheckinSource.choices, default=CheckinSource.MANUAL)
    journal_entry = models.OneToOneField(
        "journal.JournalEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="checkin"
    )

    class Meta:
        db_table = "state_checkin"
        ordering = ["-recorded_at"]
        constraints = [
            choices_check("source", CheckinSource, "state_checkin_source_ck"),
            models.CheckConstraint(condition=_scale("mood"), name="state_checkin_mood_ck"),
            models.CheckConstraint(condition=_scale("energy"), name="state_checkin_energy_ck"),
            models.CheckConstraint(condition=_scale("stress"), name="state_checkin_stress_ck"),
            models.CheckConstraint(
                condition=Q(mood__isnull=False) | Q(energy__isnull=False) | Q(stress__isnull=False),
                name="state_checkin_any_value_ck",
            ),
        ]
        indexes = [models.Index(fields=["user", "local_date"], name="state_checkin_user_date_ix")]

    def __str__(self) -> str:
        return f"{self.local_date} m={self.mood} e={self.energy} s={self.stress}"


class SleepEntry(OwnedModel):
    sleep_start = models.DateTimeField()
    sleep_end = models.DateTimeField()
    wake_date = models.DateField()
    quality = models.SmallIntegerField(null=True, blank=True)
    note = models.CharField(max_length=300, default="", blank=True)

    class Meta:
        db_table = "sleep_entry"
        ordering = ["-sleep_end"]
        constraints = [
            models.CheckConstraint(
                condition=Q(sleep_end__gt=F("sleep_start")), name="sleep_end_after_start_ck"
            ),
            models.CheckConstraint(condition=_scale("quality"), name="sleep_quality_ck"),
        ]
        indexes = [models.Index(fields=["user", "wake_date"], name="sleep_user_wake_ix")]

    @property
    def minutes(self) -> int:
        return int((self.sleep_end - self.sleep_start).total_seconds() // 60)

    def __str__(self) -> str:
        return f"sleep {self.wake_date}"
