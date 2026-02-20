from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .cli import run_query_status
from .config import ATTENTION_TYPES, POLL_AGENTS_SECS, POLL_TASKS_SECS, QUERY_STATUS_CLI, STATUS_AGENTS_DIR, STATUS_TASKS_DIR
from .parsers import parse_agent_output, parse_task_output, read_receipt

app = FastAPI(title="OpenClaw Control Plane UI")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


def runtime_ready() -> bool:
    return STATUS_AGENTS_DIR.exists() or STATUS_TASKS_DIR.exists() or QUERY_STATUS_CLI.exists()


def discover_agents() -> list[str]:
    if not STATUS_AGENTS_DIR.exists():
        return []
    names = []
    for p in sorted(STATUS_AGENTS_DIR.glob("*.latest.json")):
        names.append(p.name.removesuffix(".latest.json"))
    return names


def discover_tasks() -> list[str]:
    if not STATUS_TASKS_DIR.exists():
        return []
    return sorted([p.name for p in STATUS_TASKS_DIR.iterdir() if p.is_dir()])


def discover_receipts(task_id: str | None = None) -> list[dict]:
    base = STATUS_TASKS_DIR
    if not base.exists():
        return []
    pattern = f"{task_id}/*-report.md" if task_id else "*/*-report.md"
    receipts = [read_receipt(p) for p in base.glob(pattern)]
    return sorted(receipts, key=lambda r: r["mtime"], reverse=True)


def collect_agent_views() -> list[dict]:
    cards = []
    for agent in discover_agents():
        res = run_query_status("--agent", agent)
        parsed = parse_agent_output(agent, res.stdout)
        snapshot = parsed.snapshot or {}
        status = str(snapshot.get("status", "")).lower()
        typ = str(snapshot.get("type", ""))
        flagged = status in {"error", "blocked"} or typ in ATTENTION_TYPES
        cards.append({"agent": agent, "result": res, "parsed": parsed, "flagged": flagged})
    return cards


def collect_task_views() -> list[dict]:
    rows = []
    for task_id in discover_tasks():
        res = run_query_status("--task-id", task_id)
        parsed = parse_task_output(task_id, res.stdout)
        rows.append({"task_id": task_id, "result": res, "parsed": parsed})
    return rows


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    cards = collect_agent_views()
    tasks = collect_task_views()[:15]
    attention = any(c["flagged"] for c in cards)
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "runtime_ready": runtime_ready(),
            "attention": attention,
            "agent_cards": cards,
            "tasks": tasks,
            "poll_agents_s": POLL_AGENTS_SECS,
            "poll_tasks_s": POLL_TASKS_SECS,
        },
    )


@app.get("/agents", response_class=HTMLResponse)
def agents(request: Request):
    return templates.TemplateResponse(
        "agents.html",
        {"request": request, "agent_cards": collect_agent_views(), "poll_agents_s": POLL_AGENTS_SECS},
    )


@app.get("/agents/{agent}", response_class=HTMLResponse)
def agent_detail(request: Request, agent: str):
    res = run_query_status("--agent", agent)
    parsed = parse_agent_output(agent, res.stdout)
    return templates.TemplateResponse("agent_detail.html", {"request": request, "agent": agent, "result": res, "parsed": parsed})


@app.get("/tasks", response_class=HTMLResponse)
def tasks(request: Request):
    return templates.TemplateResponse("tasks.html", {"request": request, "tasks": collect_task_views(), "poll_tasks_s": POLL_TASKS_SECS})


@app.get("/tasks/{task_id}", response_class=HTMLResponse)
def task_detail(request: Request, task_id: str):
    res = run_query_status("--task-id", task_id)
    parsed = parse_task_output(task_id, res.stdout)
    receipts = discover_receipts(task_id)
    return templates.TemplateResponse(
        "task_detail.html",
        {"request": request, "task_id": task_id, "result": res, "parsed": parsed, "receipts": receipts},
    )


@app.get("/receipts", response_class=HTMLResponse)
def receipts(request: Request):
    return templates.TemplateResponse(
        "receipts.html",
        {"request": request, "receipts": discover_receipts(), "poll_tasks_s": POLL_TASKS_SECS},
    )


@app.get("/partials/banner", response_class=HTMLResponse)
def banner_partial(request: Request):
    attention = any(c["flagged"] for c in collect_agent_views())
    return templates.TemplateResponse("partials/banner.html", {"request": request, "attention": attention, "runtime_ready": runtime_ready()})


@app.get("/partials/agent-cards", response_class=HTMLResponse)
def agent_cards_partial(request: Request):
    return templates.TemplateResponse("partials/agent_cards.html", {"request": request, "agent_cards": collect_agent_views()})


@app.get("/partials/task-table", response_class=HTMLResponse)
def task_table_partial(request: Request):
    return templates.TemplateResponse("partials/task_table.html", {"request": request, "tasks": collect_task_views()})


@app.get("/partials/receipts-list", response_class=HTMLResponse)
def receipts_list_partial(request: Request):
    return templates.TemplateResponse("partials/receipts_list.html", {"request": request, "receipts": discover_receipts()})
