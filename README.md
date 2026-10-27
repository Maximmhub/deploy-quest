# Deploy Quest

Обучающая игра: пошаговые тесты о том, как разместить веб-приложение на сервере — от локального запуска до домена с HTTPS. Для студентов и начинающих разработчиков, которые впервые публикуют своё приложение.

**Сайт:** https://quest.24maximka.ru · **Паспорт проекта:** [project_passport.md](project_passport.md)

Игра сама развёрнута тем путём, которому учит:

```
Браузер → DNS (quest.24maximka.ru → 51.250.75.179) → firewall (группа безопасности + UFW: 22, 80, 443)
        → Nginx :443 (HTTPS, Let's Encrypt) → uvicorn 127.0.0.1:8000 → FastAPI
        процессом управляет systemd (deploy-quest.service), ОС — Ubuntu 24.04 LTS в Yandex Cloud
```

## Локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env            # при необходимости поправьте значения
set -a && source .env && set +a # экспортировать переменные в текущую сессию (Linux/macOS)
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

На сервере те же строки попадают в `journalctl`:

```bash
journalctl -u deploy-quest -f              # смотреть в реальном времени
journalctl -u deploy-quest -n 50           # последние 50 строк
journalctl -u deploy-quest --since "10 min ago"
```

## Развёртывание на сервере

Сервер: Ubuntu 24.04 LTS, виртуальная машина в Yandex Cloud. Конфигурации лежат в папке [`deploy/`](deploy).

```bash
# 1. Пакеты и firewall
sudo apt update && sudo apt install -y git python3-venv nginx
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable

# 2. Код и окружение
git clone https://github.com/Maximmhub/deploy-quest.git ~/deploy-quest
cd ~/deploy-quest
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env          # отредактировать значения

# 3. Сервис systemd: автозапуск и перезапуск при падении
sudo cp deploy/deploy-quest.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now deploy-quest

# 4. Nginx как reverse proxy
sudo cp deploy/nginx-deploy-quest.conf /etc/nginx/sites-available/deploy-quest
sudo sed -i 's/quest.example.ru/quest.24maximka.ru/' /etc/nginx/sites-available/deploy-quest
sudo ln -s /etc/nginx/sites-available/deploy-quest /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# 5. DNS: A-запись quest.24maximka.ru → публичный IP сервера

# 6. HTTPS
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d quest.24maximka.ru
```

Приложение слушает только `127.0.0.1:8000`, поэтому снаружи порт 8000 недоступен. Пользователи приходят на 80/443, а Nginx передаёт запрос приложению.

### Управление сервисом

| Действие | Команда |
|---|---|
| Статус | `systemctl status deploy-quest` |
| Перезапуск | `sudo systemctl restart deploy-quest` |
| Остановка / запуск | `sudo systemctl stop deploy-quest` / `sudo systemctl start deploy-quest` |
| Логи | `journalctl -u deploy-quest -f` |
| Проверка конфига Nginx | `sudo nginx -t` |
| Кто слушает порты | `sudo ss -ltnp` |

### Обновление

```bash
cd ~/deploy-quest
git pull
.venv/bin/python -m pip install -r requirements.txt
sudo systemctl restart deploy-quest
curl -s http://127.0.0.1:8000/version
```

## Диагностика

Проверять по пути запроса, от приложения наружу:

```bash
systemctl status deploy-quest          # 1. процесс жив?
curl http://127.0.0.1:8000/health      # 2. приложение отвечает на сервере?
sudo ss -ltnp | grep -E ':80|:443|:8000'   # 3. кто слушает порты?
sudo nginx -t                          # 4. конфиг Nginx без ошибок?
curl -I https://quest.24maximka.ru     # 5. доступно снаружи?
```

| Симптом | Вероятная причина | Что сделать |
|---|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | Зависимости не установлены или запуск не из `.venv` | `.venv/bin/python -m pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'app_final'` | Запуск не из папки проекта | Проверить `WorkingDirectory` в unit-файле или выполнить `cd ~/deploy-quest` |
| `address already in use` | Порт 8000 занят: например, остался ручной запуск | `sudo ss -ltnp \| grep 8000`, остановить лишний процесс |
| Сервис в состоянии `activating (auto-restart)` | Приложение падает при старте, systemd перезапускает его | `journalctl -u deploy-quest -n 50`, читать traceback с конца |
| `502 Bad Gateway` в браузере | Nginx работает, но приложение за ним не запущено | `systemctl status deploy-quest`, затем логи |
| `Connection refused` | На порту никто не слушает | Проверить сервис и `ss -ltnp` |
| `Connection timed out` | Трафик режется firewall | `sudo ufw status`, правила группы безопасности в Yandex Cloud |
| Домен не открывается, а IP открывается | DNS ещё не обновился или ошибка в A-записи | `nslookup quest.24maximka.ru` |
| `Permission denied` при записи результатов | У пользователя сервиса нет прав на папку `data/` | `ls -la data`, проверить владельца |
