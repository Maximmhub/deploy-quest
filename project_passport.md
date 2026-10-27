# Паспорт проекта Deploy Quest

| Поле | Значение |
|---|---|
| **Git repository** | https://github.com/Maximmhub/deploy-quest |
| **Server OS** | Ubuntu 24.04 LTS |
| **Hosting type** | VPS: виртуальная машина в Yandex Cloud (Compute Cloud), 2 vCPU, 2 ГБ RAM, 20 ГБ SSD |
| **Public IP** | 51.250.75.179 (статический) |
| **Application port** | 8000, только на 127.0.0.1 (снаружи закрыт, доступ через Nginx) |
| **Public URL** | https://quest.24maximka.ru |
| **Process manager** | systemd, сервис `deploy-quest.service`: `enable` для автозапуска при загрузке, `Restart=always` для перезапуска при падении |
| **Reverse proxy** | Nginx: принимает запросы на 80/443, завершает HTTPS (сертификат Let's Encrypt через certbot, автопродление) и передаёт их на 127.0.0.1:8000 |
| **Log command** | `journalctl -u deploy-quest -f` |
| **Restart command** | `sudo systemctl restart deploy-quest` |

## Маршрут запроса

```
Браузер
  → DNS: quest.24maximka.ru → A-запись → 51.250.75.179
  → firewall: группа безопасности Yandex Cloud и UFW пропускают 22, 80, 443
  → Nginx :443 (HTTPS; запрос на :80 перенаправляется на https)
  → proxy_pass http://127.0.0.1:8000
  → uvicorn → FastAPI (app_final.py)
  процесс запущен systemd от пользователя maxim, код в /home/maxim/deploy-quest
```

## Проверка

| Что | Команда | Ожидаемый результат |
|---|---|---|
| Сервис жив | `systemctl status deploy-quest` | `active (running)` |
| Приложение на сервере | `curl http://127.0.0.1:8000/health` | `{"status":"ok"}` |
| Снаружи | `curl https://quest.24maximka.ru/version` | имя и версия |
| CI | вкладка Actions в репозитории | последний запуск зелёный, есть artifact `deploy-quest` |
