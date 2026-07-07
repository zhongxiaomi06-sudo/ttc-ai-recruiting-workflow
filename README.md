# TTC AI Recruiting Workflow

AI-led recruiting workflow for JD ingestion, artifact classification, candidate sourcing, scoring, human task dispatch, and server deployment.

## What Is Included

- `ttc_daemon/`: FastAPI daemon, mission state machine, ingestion pipeline, Source talent adapters.
- `candidate-collector/`: local candidate collection helper.
- `scripts/`: local run, resume batch ingest, and MySQL connection check utilities.
- `deploy/`, `Dockerfile`, `docker-compose.yml`: server deployment assets.
- `ttc-feishu-bridge.user.js`, `ttc-chatgpt-reader.user.js`: browser userscripts.
- Architecture and deployment documentation in Markdown/HTML files.

## Local Run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium
scripts/run_local_daemon.sh
```

Open:

```text
http://127.0.0.1:8766/dashboard
```

## Source Talent MySQL

Keep credentials outside the repo:

```bash
mkdir -p ~/.ttc
chmod 700 ~/.ttc
vim ~/.ttc/mysql.env
```

Expected variables:

```bash
export TTC_MYSQL_HOST=...
export TTC_MYSQL_PORT=3306
export TTC_MYSQL_DATABASE=...
export TTC_MYSQL_USER=...
export TTC_MYSQL_PASSWORD=...
export TTC_SOURCE_TALENT_ENABLED=true
```

Verify:

```bash
source ~/.ttc/mysql.env
./venv/bin/python scripts/check_mysql_connection.py
```

## Safety

Do not commit resumes, SQLite databases, `.env` files, API keys, AccessKeys, generated auth QR images, or local virtual environments. The `.gitignore` is configured to exclude those by default.
