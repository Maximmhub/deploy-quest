"""Deploy Quest — обучающая игра: как разместить приложение на сервере.

Игра состоит из шагов (steps). В каждом шаге несколько тестовых вопросов.
Правильные ответы хранятся только на сервере: браузер получает вопросы
без ответов, а проверку выполняет маршрут POST /api/answer.
"""

import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Настройки из переменных окружения
# ---------------------------------------------------------------------------
APP_NAME = os.getenv("APP_NAME", "Deploy Quest")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_AUTHOR = os.getenv("APP_AUTHOR", "Student")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DATA_PATH = os.getenv("DATA_PATH", "data/scores.db")
POINTS_PER_QUESTION = int(os.getenv("POINTS_PER_QUESTION", "10"))

BASE_DIR = Path(__file__).resolve().parent
STEPS_FILE = BASE_DIR / "steps.json"
INDEX_FILE = BASE_DIR / "static" / "index.html"

# ---------------------------------------------------------------------------
# Логирование: в терминал при ручном запуске, в journalctl под systemd
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("deploy_quest")

# ---------------------------------------------------------------------------
# Данные игры
# ---------------------------------------------------------------------------
def load_steps() -> list[dict[str, Any]]:
    with STEPS_FILE.open(encoding="utf-8") as f:
        return json.load(f)["steps"]


STEPS = load_steps()
STEPS_BY_ID = {s["id"]: s for s in STEPS}
TOTAL_QUESTIONS = sum(len(s["questions"]) for s in STEPS)
MAX_SCORE = TOTAL_QUESTIONS * POINTS_PER_QUESTION

# Поля вопроса, которые нельзя отдавать в браузер
SECRET_FIELDS = {"answer", "accepted", "explanation", "output"}


def public_question(q: dict[str, Any]) -> dict[str, Any]:
    """Вопрос без правильного ответа и объяснения."""
    return {k: v for k, v in q.items() if k not in SECRET_FIELDS}


def normalize_command(text: str) -> str:
    """Приводит команду к сравнимому виду: пробелы, регистр, кавычки."""
    text = text.strip().strip("`").strip()
    if text.startswith("$ "):
        text = text[2:]
    text = text.replace("'", '"')
    return " ".join(text.split()).lower()


def check_answer(question: dict[str, Any], answer: Any) -> bool:
    qtype = question["type"]
    if qtype == "single":
        return isinstance(answer, str) and answer == question["answer"]
    if qtype == "multi":
        return isinstance(answer, list) and set(answer) == set(question["answer"])
    if qtype == "order":
        return isinstance(answer, list) and answer == question["answer"]
    if qtype == "command":
        if not isinstance(answer, str):
            return False
        accepted = {normalize_command(a) for a in question["accepted"]}
        return normalize_command(answer) in accepted
    return False


def correct_answer_view(question: dict[str, Any]) -> Any:
    if question["type"] == "command":
        return question["accepted"][0]
    return question["answer"]


# ---------------------------------------------------------------------------
# Хранилище результатов (SQLite из стандартной библиотеки)
# ---------------------------------------------------------------------------
def db_connect() -> sqlite3.Connection:
    Path(DATA_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS scores (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               player TEXT NOT NULL,
               score INTEGER NOT NULL,
               created_at TEXT DEFAULT CURRENT_TIMESTAMP
           )"""
    )
    return conn


# ---------------------------------------------------------------------------
# Приложение
# ---------------------------------------------------------------------------
app = FastAPI(title=APP_NAME, version=APP_VERSION)
log.info(
    "Starting %s v%s: %d steps, %d questions, data=%s",
    APP_NAME, APP_VERSION, len(STEPS), TOTAL_QUESTIONS, DATA_PATH,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - started) * 1000
    log.info("%s %s -> %d (%.1f ms)", request.method, request.url.path,
             response.status_code, ms)
    return response


class AnswerIn(BaseModel):
    step_id: int
    question_id: str
    answer: str | list[str]


class ScoreIn(BaseModel):
    player: str = Field(min_length=1, max_length=40)
    score: int = Field(ge=0)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(INDEX_FILE)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"name": APP_NAME, "version": APP_VERSION}


@app.get("/info")
def info():
    return {
        "name": APP_NAME,
        "author": APP_AUTHOR,
        "steps": len(STEPS),
        "questions": TOTAL_QUESTIONS,
        "max_score": MAX_SCORE,
    }


@app.get("/api/steps")
def list_steps():
    return [
        {
            "id": s["id"],
            "title": s["title"],
            "goal": s["goal"],
            "icon": s.get("icon", "server"),
            "questions": len(s["questions"]),
        }
        for s in STEPS
    ]


@app.get("/api/steps/{step_id}")
def get_step(step_id: int):
    step = STEPS_BY_ID.get(step_id)
    if step is None:
        log.warning("Step %s not found", step_id)
        raise HTTPException(status_code=404, detail=f"Шаг {step_id} не найден")
    return {
        "id": step["id"],
        "title": step["title"],
        "goal": step["goal"],
        "intro": step["intro"],
        "host": step.get("host", "laptop"),
        "icon": step.get("icon", "server"),
        "questions": [public_question(q) for q in step["questions"]],
    }


@app.post("/api/answer")
def answer(payload: AnswerIn):
    step = STEPS_BY_ID.get(payload.step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Шаг не найден")
    question = next(
        (q for q in step["questions"] if q["id"] == payload.question_id), None
    )
    if question is None:
        raise HTTPException(status_code=404, detail="Вопрос не найден")

    correct = check_answer(question, payload.answer)
    log.info("Answer step=%s question=%s correct=%s",
             payload.step_id, payload.question_id, correct)
    return {
        "correct": correct,
        "points": POINTS_PER_QUESTION if correct else 0,
        "correct_answer": correct_answer_view(question),
        "explanation": question["explanation"],
        # Имитация вывода терминала показывается только после верной команды
        "output": question.get("output", []) if correct else [],
    }


@app.get("/api/cheatsheet")
def cheatsheet():
    return [
        {"step": s["id"], "title": s["title"], "commands": s.get("cheatsheet", [])}
        for s in STEPS
    ]


@app.post("/api/scores", status_code=201)
def save_score(payload: ScoreIn):
    if payload.score > MAX_SCORE:
        raise HTTPException(
            status_code=422, detail=f"Максимально возможный счёт: {MAX_SCORE}"
        )
    player = payload.player.strip()
    with db_connect() as conn:
        conn.execute("INSERT INTO scores (player, score) VALUES (?, ?)",
                     (player, payload.score))
    log.info("Score saved: player=%s score=%d", player, payload.score)
    return {"player": player, "score": payload.score}


@app.get("/api/leaderboard")
def leaderboard(limit: int = Query(10, ge=1, le=100)):
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT player, MAX(score) AS best FROM scores "
            "GROUP BY player ORDER BY best DESC, player LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"place": i + 1, "player": p, "score": s}
            for i, (p, s) in enumerate(rows)]
