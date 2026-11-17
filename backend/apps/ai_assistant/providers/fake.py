# ruff: noqa: RUF001, RUF002 - Russian demo replies
"""Deterministic provider for tests, demos and CI. Never touches the network.

Behaviour, driven by the last user message:
- always reads today's tasks (exercises consent checks and context logging);
- "задач"/"task" + ":" → proposes CREATE_TASK with the text after the colon;
- "событ"/"event" + ":" → proposes CREATE_EVENT tomorrow 10:00–11:00;
- "ignore previous" → tries an unknown tool (must be rejected, nothing created).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from apps.ai_assistant.providers.base import RunResult, ToolHandler, ToolSpec


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m["role"] == "user" and isinstance(m["content"], str):
            return m["content"]
    return ""


class FakeProvider:
    name = "fake"
    model = "fake-1"

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
        lowered = text.lower()
        calls = 0
        notes: list[str] = []

        tasks = handle_tool("get_tasks", {"status": "OPEN"})
        calls += 1
        summary = "Нет доступа к задачам." if tasks.is_error else "Посмотрел ваши задачи."

        if "ignore previous" in lowered:
            outcome = handle_tool("delete_everything", {})
            calls += 1
            notes.append(outcome.content)

        title = text.split(":", 1)[1].strip() if ":" in text else ""
        if title and ("задач" in lowered or "task" in lowered):
            outcome = handle_tool(
                "propose_create_task",
                {"title": title, "priority": "MEDIUM", "assumptions": ["Срок не указан — без срока."]},
            )
            calls += 1
            summary += (
                " Подготовил черновик задачи — подтвердите его."
                if not outcome.is_error
                else f" {outcome.content}"
            )
        elif title and ("событ" in lowered or "event" in lowered):
            tomorrow = (date.today() + timedelta(days=1)).isoformat()  # noqa: DTZ011 - demo only
            outcome = handle_tool(
                "propose_create_event",
                {
                    "title": title,
                    "date": tomorrow,
                    "start": "10:00",
                    "end": "11:00",
                    "time_type": "PERSONAL",
                    "assumptions": ["Время не указано — предложено 10:00–11:00 завтра."],
                },
            )
            calls += 1
            summary += " Подготовил черновик события." if not outcome.is_error else f" {outcome.content}"

        return RunResult(
            text=summary, model=self.model, input_tokens=100, output_tokens=40, tool_calls=calls, notes=notes
        )
