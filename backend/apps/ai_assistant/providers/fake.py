# ruff: noqa: RUF001, RUF002 - Russian demo replies
"""Demo provider: a rule-based assistant for tests, CI and running LifeOS without an API key.

It never touches the network, but it goes through the same tools as the real model, so consent
checks, context logging and drafts behave exactly as in production. It understands a handful of
common requests and answers them from the user's own data:

- "задача: …" / "task: …"          → drafts CREATE_TASK with the text after the colon;
- "событие: …" / "event: …"        → drafts CREATE_EVENT tomorrow 10:00–11:00;
- free time ("свободн", "окн")     → free windows for the next 7 days, optionally ≥ N hours;
- a plan ("план", "завтра")        → tomorrow's events, free windows and the top open tasks;
- habits, goals, the week's results, today's tasks;
- "что умеешь" / anything else     → says it is the demo and lists what it understands;
- "ignore previous"                → tries an unknown tool (must be rejected, nothing created).
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from apps.ai_assistant.providers.base import RunResult, ToolHandler, ToolSpec

WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
PRIORITY_ORDER = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
NUMBER_WORDS = {"один": 1, "одн": 1, "час ": 1, "два": 2, "две": 2, "три": 3, "четыр": 4, "пят": 5}

CAPABILITIES = (
    "Сейчас я работаю в демо-режиме: без подключённой модели Claude и понимаю простые запросы.\n"
    "Попробуйте:\n"
    "• «Когда у меня есть 2 свободных часа на этой неделе?»\n"
    "• «Составь план на завтра»\n"
    "• «Задача: купить билеты» — подготовлю черновик задачи\n"
    "• «Событие: созвон с командой» — подготовлю черновик события\n"
    "• «Как мои привычки?», «Как дела с целями?», «Итоги недели»\n"
    "Чтобы я понимал любые вопросы, администратору нужно добавить ключ Anthropic API."
)


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m["role"] == "user" and isinstance(m["content"], str):
            return m["content"]
    return ""


def _today(system: list[dict[str, Any]]) -> date:
    """The user's local date, taken from the system context the orchestrator builds."""
    for block in system:
        found = re.search(r"Current local date and time: \w+ (\d{4}-\d{2}-\d{2})", block.get("text", ""))
        if found:
            return date.fromisoformat(found.group(1))
    return date.today()  # noqa: DTZ011 - only when the context is missing (unit tests)


def _day_label(day: date, today: date) -> str:
    if day == today:
        return "сегодня"
    if day == today + timedelta(days=1):
        return "завтра"
    return f"{WEEKDAYS[day.weekday()]}, {day.day} {MONTHS[day.month - 1]}"


def _minutes(slot: list[str]) -> int:
    (h1, m1), (h2, m2) = (map(int, t.split(":")) for t in slot)
    return (h2 * 60 + m2) - (h1 * 60 + m1)


def _duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h} ч {m} мин" if h and m else f"{h} ч" if h else f"{m} мин"


def _fill(slots: list[list[str]], tasks: list[dict[str, Any]]) -> list[str]:
    """Places tasks back to back into free windows (estimate, or 1 hour), with a 15-minute break."""
    lines: list[str] = []
    queue = list(tasks)
    for start, end in slots:
        cursor = sum(x * y for x, y in zip(map(int, start.split(":")), (60, 1), strict=True))
        limit = sum(x * y for x, y in zip(map(int, end.split(":")), (60, 1), strict=True))
        while queue:
            length = min(queue[0]["estimated_minutes"] or 60, 180)
            if cursor + length > limit:
                break
            task = queue.pop(0)
            lines.append(
                f"• {cursor // 60:02d}:{cursor % 60:02d}–{(cursor + length) // 60:02d}:"
                f"{(cursor + length) % 60:02d} — {task['title']}"
            )
            cursor += length + 15
    return lines


def _wanted_hours(text: str) -> int:
    found = re.search(r"(\d+)\s*(?:час|ч\b|h)", text)
    if found:
        return int(found.group(1))
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\w*\s+(?:свободн\w*\s+)?час", text):
            return value
    return 0


class _Turn:
    """One reply: calls tools through the orchestrator and remembers how many it made."""

    def __init__(self, handle_tool: ToolHandler, today: date) -> None:
        self.handle_tool = handle_tool
        self.today = today
        self.calls = 0
        self.denied: set[str] = set()

    def read(self, name: str, args: dict[str, Any]) -> Any:
        self.calls += 1
        outcome = self.handle_tool(name, args)
        if outcome.is_error:
            self.denied.add(name)
            return None
        return json.loads(outcome.content)

    def no_access(self, what: str) -> str:
        return f"Нет доступа к разделу «{what}». Разрешите его в настройках ассистента (кнопка «Изменить»)."

    # -- intents -----------------------------------------------------------------

    def free_time(self, text: str) -> str:
        hours = _wanted_hours(text)
        need = hours * 60
        lines: list[str] = []
        for n in range(7):
            day = self.today + timedelta(days=n)
            data = self.read("get_free_slots", {"date": day.isoformat()})
            if data is None:
                return self.no_access("Расписание")
            slots = [s for s in data["slots"] if _minutes(s) >= max(need, 30)]
            if slots:
                windows = ", ".join(f"{a}–{b}" for a, b in slots[:3])
                lines.append(f"• {_day_label(day, self.today)}: {windows}")
        if not lines:
            want = f" на {hours} ч подряд" if hours else ""
            return f"На ближайшие 7 дней свободных окон{want} в рабочем дне нет."
        head = f"Окна от {hours} ч подряд" if hours else "Свободные окна"
        return f"{head} на ближайшие 7 дней:\n" + "\n".join(lines)

    def plan(self) -> str:
        day = self.today + timedelta(days=1)
        events = self.read("get_schedule", {"from": day.isoformat(), "to": day.isoformat()})
        free = self.read("get_free_slots", {"date": day.isoformat()})
        tasks = self.read("get_tasks", {"status": "OPEN"})
        if events is None or free is None:
            return self.no_access("Расписание")
        parts = [f"План на завтра, {WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}:"]
        if events:
            parts.append("Уже в расписании:")
            parts += [f"• {e['start'][11:16]}–{e['end'][11:16]} {e['title']}" for e in events[:6]]
        slots = [s for s in free["slots"] if _minutes(s) >= 30]
        if tasks is None:
            parts.append(self.no_access("Задачи"))
            return "\n".join(parts)
        todo = sorted(tasks, key=lambda t: (PRIORITY_ORDER.get(t["priority"], 9), t["due"] or "9999-12-31"))
        if not slots:
            parts.append("Свободных окон в рабочем дне нет — лучше ничего не добавлять.")
        elif not todo:
            parts.append(f"Открытых задач нет. Свободно: {_duration(free['free_minutes'])}.")
        else:
            parts.append("Предлагаю занять свободные окна задачами по приоритету:")
            parts += _fill(slots, todo[:5])
            parts.append("Скажите «Событие: …», и я подготовлю блок в расписании.")
        return "\n".join(parts)

    def tasks(self) -> str:
        tasks = self.read("get_tasks", {"status": "OPEN"})
        if tasks is None:
            return self.no_access("Задачи")
        if not tasks:
            return "Открытых задач нет."
        overdue = [t for t in tasks if t["due"] and t["due"] < self.today.isoformat()]
        today = [t for t in tasks if t["due"] == self.today.isoformat()]
        parts = [f"Открытых задач: {len(tasks)}, на сегодня: {len(today)}, просрочено: {len(overdue)}."]
        parts += [f"• {t['title']}" for t in (overdue + today)[:5]]
        return "\n".join(parts)

    def habits(self) -> str:
        habits = self.read("get_habits", {"date": self.today.isoformat()})
        if habits is None:
            return self.no_access("Привычки")
        planned = [h for h in habits if h["planned_today"]]
        if not planned:
            return "На сегодня привычек не запланировано."
        done = [h for h in planned if h["status"] in ("DONE", "PARTIAL")]
        parts = [f"Сегодня отмечено {len(done)} из {len(planned)} привычек."]
        for h in planned[:6]:
            mark = "✓" if h in done else "○"
            streak = f", серия {h['streak']}" if h["streak"] else ""
            parts.append(f"{mark} {h['name']}{streak}")
        return "\n".join(parts)

    def goals(self) -> str:
        goals = self.read("get_goals", {})
        if goals is None:
            return self.no_access("Цели")
        if not goals:
            return "Активных целей нет."
        parts = ["Активные цели:"]
        parts += [f"• {g['title']} — {round(g['progress_pct'])}%" for g in goals[:6]]
        return "\n".join(parts)

    def week(self) -> str:
        data = self.read("get_analytics", {"period": "week", "date": self.today.isoformat()})
        if data is None:
            return self.no_access("Аналитика")

        def pct(metric: dict[str, Any]) -> str:
            return "нет данных" if metric["value"] is None else f"{round(metric['value'] * 100)}%"

        focus = data["time"]["focus_hours"]["value"]
        return "\n".join(
            [
                "Итоги этой недели:",
                f"• выполнение задач: {pct(data['tasks']['completion_rate'])}"
                f" ({data['tasks']['completed']} выполнено)",
                f"• регулярность привычек: {pct(data['habits']['consistency'])}",
                f"• фокус: {'нет данных' if focus is None else f'{focus:.1f} ч'}",
            ]
        )

    def draft(self, tool: str, args: dict[str, Any], done: str) -> str:
        self.calls += 1
        outcome = self.handle_tool(tool, args)
        return done if not outcome.is_error else outcome.content


class FakeProvider:
    name = "fake"
    model = "demo"

    def run(
        self,
        *,
        system: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        handle_tool: ToolHandler,
        max_iterations: int,
    ) -> RunResult:
        text = _last_user_text(messages)
        low = text.lower()
        turn = _Turn(handle_tool, _today(system))
        notes: list[str] = []
        title = text.split(":", 1)[1].strip() if ":" in text else ""

        if "ignore previous" in low:
            outcome = handle_tool("delete_everything", {})
            turn.calls += 1
            notes.append(outcome.content)
            reply = "Я не могу удалять данные. Я только готовлю черновики, которые вы подтверждаете."
        elif title and ("задач" in low or "task" in low):
            similar = turn.read("get_tasks", {"status": "OPEN", "q": title[:40]})
            reply = turn.draft(
                "propose_create_task",
                {"title": title, "priority": "MEDIUM", "assumptions": ["Срок не указан — без срока."]},
                "Подготовил черновик задачи — проверьте и подтвердите его.",
            )
            if similar:
                reply += f" Похожая открытая задача уже есть: «{similar[0]['title']}»."
        elif title and ("событ" in low or "event" in low):
            reply = turn.draft(
                "propose_create_event",
                {
                    "title": title,
                    "date": (turn.today + timedelta(days=1)).isoformat(),
                    "start": "10:00",
                    "end": "11:00",
                    "time_type": "PERSONAL",
                    "assumptions": ["Время не указано — предложено 10:00–11:00 завтра."],
                },
                "Подготовил черновик события — время можно поправить перед подтверждением.",
            )
        elif re.search(r"план|plan", low):  # a plan wins over "free time" words in the same request
            reply = turn.plan()
        elif re.search(r"свобод|окн|free", low):
            reply = turn.free_time(low)
        elif "завтра" in low:
            reply = turn.plan()
        elif "привыч" in low or "habit" in low:
            reply = turn.habits()
        elif re.search(r"\bцел[ьиея]|goal", low):
            reply = turn.goals()
        elif re.search(r"итог|недел|статист|аналит|week", low):
            reply = turn.week()
        elif re.search(r"задач|дел[аo]|task|сегодня", low):
            reply = turn.tasks()
        else:
            reply = CAPABILITIES

        return RunResult(
            text=reply,
            model=self.model,
            input_tokens=100,
            output_tokens=40,
            tool_calls=turn.calls,
            notes=notes,
        )
