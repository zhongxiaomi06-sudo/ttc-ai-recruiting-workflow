"""Jinja2 HTML rendering for Dashboard, Mission detail and Human Task pages."""

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)
env.filters["fromjson"] = lambda s: json.loads(s) if s else {}



def _json_load(s: Any) -> Any:
    try:
        return json.loads(s) if isinstance(s, str) else (s or {})
    except Exception:
        return {}


def render_dashboard(missions: list[dict], tasks: list[dict]) -> str:
    return env.get_template("dashboard.html").render(missions=missions, tasks=tasks)


def render_mission(mission: dict, artifact: dict, tasks: list[dict], runs: list[dict]) -> str:
    return env.get_template("mission.html").render(
        mission=mission,
        artifact=artifact,
        jd_struct=_json_load(mission.get("jd_struct")),
        candidates=_json_load(mission.get("candidates_json")),
        scores=_json_load(mission.get("scores_json")),
        call_list=_json_load(mission.get("call_list_json")),
        tasks=tasks,
        runs=runs,
    )


def render_human_task(task: dict, mission: dict) -> str:
    payload = _json_load(task.get("payload_json"))
    jd_struct = _json_load(mission.get("jd_struct"))
    template_map = {
        "phone_call": "task_call.html",
        "client_review": "task_review.html",
        "problem_solve": "task_problem.html",
    }
    template = template_map.get(task["task_type"], "task_problem.html")
    return env.get_template(template).render(task=task, mission=mission, payload=payload, jd_struct=jd_struct)
