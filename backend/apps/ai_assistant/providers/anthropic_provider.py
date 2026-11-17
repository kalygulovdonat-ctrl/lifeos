"""Claude via the official Anthropic SDK (SDD §9.1).

A manual tool loop (not the beta tool runner) because the orchestrator must gate every tool
call on consent, record what data was shared, and stop after AI_MAX_TOOL_ITERATIONS.
The full `response.content` (including thinking blocks) is appended back unchanged.
"""

from __future__ import annotations

from typing import Any

import anthropic
from django.conf import settings

from apps.ai_assistant.providers.base import AIUnavailable, RunResult, ToolHandler, ToolSpec

MAX_TOKENS = 16_000
# Server-side refusal fallback (opt-in by default for this model family): on a policy decline
# the API re-runs the request on a fallback model it picks by refusal category.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        # Credentials come from the environment (ANTHROPIC_API_KEY or an `ant auth` profile).
        self.client = anthropic.Anthropic(timeout=settings.AI_TIMEOUT_S, max_retries=2)
        self.model = settings.AI_MODEL

    def _create(self, **kwargs: Any) -> Any:
        try:
            return self.client.beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                output_config={"effort": settings.AI_EFFORT},
                betas=[FALLBACK_BETA],
                fallbacks="default",
                **kwargs,
            )
        except anthropic.AuthenticationError as exc:
            raise AIUnavailable("authentication") from exc
        except anthropic.RateLimitError as exc:
            raise AIUnavailable("rate_limited") from exc
        except anthropic.APIConnectionError as exc:  # includes timeouts
            raise AIUnavailable("connection") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise AIUnavailable("server") from exc
            raise

    def run(
        self,
        *,
        system: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        handle_tool: ToolHandler,
        max_iterations: int,
    ) -> RunResult:
        tool_defs = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools
        ]
        convo = list(messages)
        result = RunResult(text="", model=self.model)
        texts: list[str] = []

        for iteration in range(max_iterations + 1):
            last = iteration == max_iterations
            response = self._create(
                system=system,
                messages=convo,
                tools=tool_defs,
                # On the final round tools are switched off so the model must answer in text.
                tool_choice={"type": "none"} if last else {"type": "auto"},
            )
            result.input_tokens += response.usage.input_tokens
            result.output_tokens += response.usage.output_tokens
            result.model = response.model
            result.stop_reason = response.stop_reason or "end_turn"
            texts = [b.text for b in response.content if b.type == "text"]

            if response.stop_reason == "refusal":
                result.notes.append("refusal")
                break
            if response.stop_reason == "pause_turn":
                convo.append({"role": "assistant", "content": response.content})
                continue
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_uses:
                break

            convo.append({"role": "assistant", "content": response.content})
            results = []
            for block in tool_uses:
                outcome = handle_tool(block.name, dict(block.input or {}))
                result.tool_calls += 1
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": outcome.content,
                        "is_error": outcome.is_error,
                    }
                )
            # All results of one turn go back in a single user message.
            convo.append({"role": "user", "content": results})

        result.text = "\n\n".join(t for t in texts if t.strip())
        return result
