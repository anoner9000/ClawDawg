from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AgentView:
    agent: str
    snapshot: dict[str, Any] | None
    bus_events: int | None
    recent: list[str]
    raw: str
    parse_error: str | None = None


@dataclass
class TaskView:
    task_id: str
    state: str
    bus_events: int | None
    latest_by_agent: list[str]
    raw: str


def _extract_first_json_block(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    end = -1
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def parse_agent_output(agent: str, text: str) -> AgentView:
    snapshot = _extract_first_json_block(text)
    parse_error = None if snapshot is not None else "Could not parse snapshot JSON"

    bus_events = None
    m = re.search(r"^BUS_EVENTS:\s*(\d+)\s*$", text, flags=re.M)
    if m:
        bus_events = int(m.group(1))

    recent: list[str] = []
    rec_idx = text.find("RECENT:")
    if rec_idx != -1:
        for line in text[rec_idx:].splitlines()[1:]:
            if line.startswith("  - "):
                recent.append(line[4:])
            elif line.strip() and not line.startswith(" "):
                break

    return AgentView(agent=agent, snapshot=snapshot, bus_events=bus_events, recent=recent, raw=text, parse_error=parse_error)


def parse_task_output(task_id: str, text: str) -> TaskView:
    state = "unknown"
    m_state = re.search(r"^STATE:\s*(.+)$", text, flags=re.M)
    if m_state:
        state = m_state.group(1).strip()

    bus_events = None
    m_bus = re.search(r"^BUS_EVENTS:\s*(\d+)\s*$", text, flags=re.M)
    if m_bus:
        bus_events = int(m_bus.group(1))

    latest_by_agent: list[str] = []
    idx = text.find("LATEST_BY_AGENT:")
    if idx != -1:
        for line in text[idx:].splitlines()[1:]:
            if line.startswith("  - "):
                latest_by_agent.append(line[4:])
            elif line.strip() and not line.startswith(" "):
                break

    return TaskView(task_id=task_id, state=state, bus_events=bus_events, latest_by_agent=latest_by_agent, raw=text)


def read_receipt(path: Path) -> dict[str, Any]:
    stat = path.stat()
    try:
        body = path.read_text(encoding="utf-8")
    except Exception as exc:
        body = f"[read error] {exc}"
    return {
        "path": str(path),
        "name": path.name,
        "task_id": path.parent.name,
        "mtime": int(stat.st_mtime),
        "preview": body[:1200],
        "raw": body,
    }
