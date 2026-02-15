# Deploy on Render (FastAPI)

Этот проект готов к деплою через `render.yaml`.

## Что уже подготовлено

- `render.yaml` в корне проекта
- Команда запуска под Render (`uvicorn main:app --host 0.0.0.0 --port $PORT`)
- Безопасный cloud-режим:
  - `PANDORA_REVIEW_ONLY_MODE=1`
  - `PANDORA_STRICT_DOCKER_RUNNERS=1`
  - Это отключает выполнение пользовательского кода на сервере.

## Важно про Free plan

- На Render Free web service нет постоянного диска.
- `academy.db` может сбрасываться после redeploy/restart/перемещения инстанса.
- Сервис может "засыпать" при простое.

Если нужен гарантированный persistence в Render:
- либо платный инстанс + Persistent Disk,
- либо миграция БД на внешний Postgres.

Официальные документы Render:

- FastAPI deploy: https://render.com/docs/deploy-fastapi
- First deploy (без оплаты на старте): https://render.com/docs/your-first-deploy
- Free instances (sleep + ограничения): https://render.com/docs/free
- Persistent disks (только paid instances): https://render.com/docs/disks
- Port binding и env `PORT`: https://render.com/docs/web-services
- Blueprint spec (`render.yaml`): https://render.com/docs/blueprint-spec

Комментарий Render про keep-alive пинги (через cron/uptime):  
https://community.render.com/t/do-web-services-on-a-free-tier-go-to-sleep-after-some-time-inactive/3303

## Деплой через Blueprint (рекомендуется)

1. Запушь проект в GitHub/GitLab/Bitbucket.
2. В Render: `New` -> `Blueprint`.
3. Подключи репозиторий, выбери ветку, нажми `Apply`.
4. После создания сервиса открой `Environment` и добавь секрет:
   - `PANDORA_BOOTSTRAP_ADMIN_PASSWORD` = надежный пароль админа.
5. Нажми `Manual Deploy` -> `Deploy latest commit`.
6. Проверь:
   - `https://<service>.onrender.com/ping`
   - `https://<service>.onrender.com/api/status`
   - `https://<service>.onrender.com/`
   - `https://<service>.onrender.com/admin`

## Ручной деплой без Blueprint

Поля в Render Web Service:

- `Runtime`: Python
- `Build Command`: `pip install -r requirements.txt`
- `Start Command`: `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1`
- `Health Check Path`: `/ping`

Env vars:

- `PANDORA_JWT_SECRET` (обязательно, длинная случайная строка)
- `PANDORA_BOOTSTRAP_ADMIN_PASSWORD` (обязательно)
- `PANDORA_REVIEW_ONLY_MODE=1`
- `PANDORA_STRICT_DOCKER_RUNNERS=1`
- `PANDORA_LOW_RESOURCE_MODE=1`
- `PANDORA_BOOTSTRAP_ADMIN_USER=admin`
- `PANDORA_BOOTSTRAP_ADMIN_DISPLAY=Sensei`

## Если нужен авточек кода (небезопасно)

Только на свой риск:

- `PANDORA_REVIEW_ONLY_MODE=0`
- и доступный sandbox runner (отдельно от web процесса).

Для публичного интернет-доступа не рекомендуется выполнять пользовательский код в том же процессе, где работает API.

## Keep-Alive через cron (опционально)

В проект добавлен workflow:

- `.github/workflows/render-keepalive.yml`

Как включить:

1. В GitHub -> `Settings` -> `Secrets and variables` -> `Actions`.
2. Создай secret `RENDER_KEEPALIVE_URL` со значением:
   - `https://<your-service>.onrender.com`
3. Убедись, что Actions включены для репозитория.

Что делает:

- Раз в 14 минут вызывает `GET /ping`.
- Если secret не задан, job автоматически пропускается.

Важно:

- Это может идти против идеи free-sleep режима.
- Render в любой момент может изменить политику/поведение.
- Гарантии отсутствия sleep на free нет.

## Backup в GitHub каждые 8 часов

В проект добавлены:

- `main.py` endpoint `GET /api/admin/backup/sqlite` (admin-only).
- `scripts/render_backup_pull.py` (логин + скачивание backup в `.db.gz`).
- `.github/workflows/render-backup.yml` (cron `0 */8 * * *`).

### Секреты GitHub для backup workflow

В `Settings -> Secrets and variables -> Actions` добавь:

- `PANDORA_BASE_URL` = `https://<your-service>.onrender.com`
- `PANDORA_BACKUP_USER` = admin username
- `PANDORA_BACKUP_PASS` = admin password

### Что делает backup workflow

1. Логинится в API.
2. Скачивает консистентный SQLite snapshot.
3. Сохраняет в `backups/academy_backup_YYYYMMDDTHHMMSSZ.db.gz`.
4. Удаляет старые backup-файлы (оставляет последние 21).
5. Публикует backup в отдельную ветку `backup-snapshots` (force-push orphan commit).

### Рекомендации безопасности

- Используй private repository для backup-файлов.
- Не публикуй `academy.db`/`backups/*` в публичный доступ.
- При необходимости добавь шифрование backup перед коммитом.
