import os
import tempfile

# Тесты пишут результаты во временную базу, а не в рабочую data/scores.db.
# Переменную нужно задать до импорта приложения.
os.environ["DATA_PATH"] = os.path.join(tempfile.mkdtemp(), "test_scores.db")

from fastapi.testclient import TestClient  # noqa: E402

from app_final import STEPS, app, normalize_command  # noqa: E402

client = TestClient(app)


def first_question(qtype):
    """Первый вопрос нужного типа из данных игры."""
    for step in STEPS:
        for q in step["questions"]:
            if q["type"] == qtype:
                return step["id"], q
    raise AssertionError(f"Нет вопроса типа {qtype}")


# --- служебные маршруты ----------------------------------------------------

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version():
    response = client.get("/version")
    assert response.status_code == 200
    assert "version" in response.json()


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# --- шаги ------------------------------------------------------------------

def test_list_steps():
    response = client.get("/api/steps")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(STEPS)
    assert data[0]["id"] == 1


def test_get_step_hides_answers():
    response = client.get("/api/steps/1")
    assert response.status_code == 200
    for q in response.json()["questions"]:
        assert "answer" not in q
        assert "accepted" not in q
        assert "explanation" not in q


def test_unknown_step_returns_404():
    response = client.get("/api/steps/999")
    assert response.status_code == 404


def test_step_id_must_be_number():
    response = client.get("/api/steps/abc")
    assert response.status_code == 422


# --- проверка ответов ------------------------------------------------------

def test_single_correct_answer():
    step_id, q = first_question("single")
    response = client.post("/api/answer", json={
        "step_id": step_id, "question_id": q["id"], "answer": q["answer"],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is True
    assert body["points"] > 0
    assert body["explanation"]


def test_single_wrong_answer():
    step_id, q = first_question("single")
    wrong = next(o["id"] for o in q["options"] if o["id"] != q["answer"])
    response = client.post("/api/answer", json={
        "step_id": step_id, "question_id": q["id"], "answer": wrong,
    })
    body = response.json()
    assert body["correct"] is False
    assert body["points"] == 0
    assert body["correct_answer"] == q["answer"]


def test_multi_answer_order_does_not_matter():
    step_id, q = first_question("multi")
    response = client.post("/api/answer", json={
        "step_id": step_id, "question_id": q["id"],
        "answer": list(reversed(q["answer"])),
    })
    assert response.json()["correct"] is True


def test_order_answer_must_be_exact():
    step_id, q = first_question("order")
    shuffled = list(reversed(q["answer"]))
    response = client.post("/api/answer", json={
        "step_id": step_id, "question_id": q["id"], "answer": shuffled,
    })
    assert response.json()["correct"] is False


def test_command_with_extra_spaces_is_accepted():
    step_id, q = first_question("command")
    messy = "   " + q["accepted"][0].replace(" ", "   ") + "  "
    response = client.post("/api/answer", json={
        "step_id": step_id, "question_id": q["id"], "answer": messy,
    })
    assert response.json()["correct"] is True


def test_normalize_command():
    assert normalize_command("$  Python3 -m venv   .venv ") == "python3 -m venv .venv"


def test_unknown_question_returns_404():
    response = client.post("/api/answer", json={
        "step_id": 1, "question_id": "nope", "answer": "a",
    })
    assert response.status_code == 404


# --- результаты ------------------------------------------------------------

def test_save_score_and_leaderboard():
    response = client.post("/api/scores", json={"player": "Tester", "score": 30})
    assert response.status_code == 201

    board = client.get("/api/leaderboard?limit=5").json()
    assert any(row["player"] == "Tester" and row["score"] == 30 for row in board)


def test_score_above_maximum_is_rejected():
    response = client.post("/api/scores", json={"player": "Cheater", "score": 10**6})
    assert response.status_code == 422


def test_leaderboard_limit_validation():
    response = client.get("/api/leaderboard?limit=0")
    assert response.status_code == 422


def test_cheatsheet_covers_all_steps():
    sheet = client.get("/api/cheatsheet").json()
    assert len(sheet) == len(STEPS)
    assert all(item["commands"] for item in sheet)


def test_command_output_only_after_correct_answer():
    step_id, q = next(
        (s["id"], q) for s in STEPS for q in s["questions"] if q.get("output")
    )
    ok = client.post("/api/answer", json={
        "step_id": step_id, "question_id": q["id"], "answer": q["accepted"][0],
    }).json()
    bad = client.post("/api/answer", json={
        "step_id": step_id, "question_id": q["id"], "answer": "rm -rf /",
    }).json()
    assert ok["output"] == q["output"]
    assert bad["output"] == []
