# Deploy Quest

Обучающая игра: пошаговые тесты о том, как разместить веб-приложение на сервере — от локального запуска до домена с HTTPS. Для студентов и начинающих разработчиков, которые впервые публикуют своё приложение.

> Раздел про сервер, systemd, Nginx и диагностику будет дополнен после деплоя.

## Локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env            # при необходимости поправьте значения
set -a && source .env && set +a # экспортировать переменные в текущую сессию
python -m uvicorn app_final:app --host 127.0.0.1 --port 8000
```

Игра: http://127.0.0.1:8000 · документация API: http://127.0.0.1:8000/docs

Для разработки можно добавить `--reload`. Для обычной работы (и на сервере) запускайте без него.

## Проверка

```bash
curl http://127.0.0.1:8000/health    # {"status":"ok"}
curl http://127.0.0.1:8000/version   # имя и версия
```

## Тесты

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -v
```

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `APP_NAME` | Deploy Quest | Название в `/version` и `/docs` |
| `APP_VERSION` | 0.1.0 | Версия приложения |
| `APP_AUTHOR` | Student | Автор в `/info` |
| `LOG_LEVEL` | INFO | Уровень логов: DEBUG, INFO, WARNING |
| `DATA_PATH` | data/scores.db | Файл SQLite с таблицей лидеров |
| `POINTS_PER_QUESTION` | 10 | XP за правильный ответ |

## API

| Метод и путь | Назначение |
|---|---|
| `GET /` | Страница игры |
| `GET /health` | Проверка работоспособности |
| `GET /version` | Версия приложения |
| `GET /info` | Автор, число шагов и вопросов |
| `GET /api/steps` | Список шагов |
| `GET /api/steps/{step_id}` | Вопросы шага без правильных ответов |
| `POST /api/answer` | Проверка ответа, объяснение, XP |
| `GET /api/cheatsheet` | Шпаргалка команд по всем шагам |
| `POST /api/scores` | Сохранить результат игрока |
| `GET /api/leaderboard?limit=10` | Таблица лидеров |

## Логи

Приложение пишет в stdout: старт сервиса, каждый запрос (метод, путь, статус, время) и каждый ответ игрока. При ручном запуске логи видны в терминале.
