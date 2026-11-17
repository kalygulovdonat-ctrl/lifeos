"""Provider-neutral contract (SDD §9.2). Providers own their tool loop; the orchestrator owns tools."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolOutcome:
    content: str
    is_error: bool = False


# Called for every tool the model uses; returns what the model sees as the tool result.
ToolHandler = Callable[[str, dict[str, Any]], ToolOutcome]


@dataclass
class RunResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    stop_reason: str = "end_turn"
    notes: list[str] = field(default_factory=list)


class AIUnavailable(Exception):
    """Provider down, timed out or not configured → AI_PROVIDER_UNAVAILABLE (NFR-013)."""


class AIProvider(Protocol):
    name: str

    def run(
        self,
        *,
        system: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        handle_tool: ToolHandler,
        max_iterations: int,
    ) -> RunResult: ...
