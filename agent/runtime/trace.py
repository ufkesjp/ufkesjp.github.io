"""Structured JSON logging for one agent run.

Every field here exists because Run 2's checkpoint or Run 3's eval harness
needs to assert against it later: the guard decision (refusal rate), each
tool call with its arguments/result/error flag (tool-call precision and
recovery rate), token counts and latency (cost), and the final answer
(answer accuracy). Nothing here is derived after the fact from prose — it's
recorded as the run happens.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACE_DIR = Path(__file__).resolve().parents[2] / "eval_boards" / "data" / "traces"


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    result: Any = None
    is_error: bool = False  # the tool call itself raised
    is_empty: bool = False  # the tool executed fine but found nothing


@dataclass
class Trace:
    question: str
    guard_decision: dict | None = None
    refused: bool = False
    asked_clarification: bool = False
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    token_usage: list[dict] = field(default_factory=list)
    iterations: int = 0
    final_answer: str | None = None
    model: str | None = None
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    latency_seconds: float | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        return data


def write_trace(trace: Trace, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace.to_dict(), indent=2, default=str))
