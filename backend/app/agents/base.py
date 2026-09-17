from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Trace:
    """Ordered record of what every agent did -- this is what the
    'Why am I seeing this?' view renders."""

    steps: list[dict] = field(default_factory=list)

    def add(self, agent: str, action: str, detail: str, data: Any = None) -> None:
        self.steps.append(
            {
                "agent": agent,
                "action": action,
                "detail": detail,
                "data": data if data is None or isinstance(data, (dict, list, str, int, float, bool)) else str(data),
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def as_list(self) -> list[dict]:
        return list(self.steps)


class Agent:
    name = "agent"

    def __init__(self, trace: Trace | None = None) -> None:
        self.trace = trace or Trace()

    def log(self, action: str, detail: str, data: Any = None) -> None:
        self.trace.add(self.name, action, detail, data)
