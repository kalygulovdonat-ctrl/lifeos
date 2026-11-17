"""Journal (SDD §4.8). Entries are private by default and never written to logs or audit."""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.accounts.models import Category, Tag
from common.models import SoftDeleteModel, choices_check


class EntryType(models.TextChoices):
    DAILY = "DAILY"
    FREE = "FREE"
    NOTE = "NOTE"


DAILY_V1 = ("happened", "accomplished", "problems", "learned", "grateful", "improve", "tomorrow")
TEMPLATES = {"daily_v1": DAILY_V1}


class JournalEntry(SoftDeleteModel):
    entry_date = models.DateField()
    entry_type = models.CharField(max_length=8, choices=EntryType.choices, default=EntryType.FREE)
    title = models.CharField(max_length=200, default="", blank=True)
    template_key = models.CharField(max_length=40, null=True, blank=True)
    sections = models.JSONField(default=dict, blank=True)
    body = models.TextField(default="", blank=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    tags = models.ManyToManyField(Tag, blank=True, db_table="journal_tag", related_name="journal_entries")
    is_sensitive = models.BooleanField(default=True)
    ai_allowed = models.BooleanField(default=False)

    class Meta(SoftDeleteModel.Meta):
        db_table = "journal_entry"
        ordering = ["-entry_date", "-created_at"]
        constraints = [
            choices_check("entry_type", EntryType, "journal_entry_type_ck"),
            models.UniqueConstraint(
                fields=["user", "entry_date"],
                condition=Q(entry_type="DAILY", deleted_at__isnull=True),
                name="journal_one_daily_per_date_uq",
            ),
        ]
        indexes = [models.Index(fields=["user", "-entry_date"], name="journal_user_date_ix")]

    def __str__(self) -> str:
        return f"{self.entry_type} {self.entry_date}"
