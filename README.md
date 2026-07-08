# TTC AI Recruiting Workflow

AI-led recruiting workflow for JD ingestion, artifact classification, candidate sourcing, scoring, human task dispatch, and server deployment.

## What Is Included

- `ttc_daemon/`: FastAPI daemon, mission state machine, ingestion pipeline, Source talent adapters.
- `candidate-collector/`: local candidate collection helper.
- `scripts/`: local run, resume batch ingest, MySQL connection check, and environment check utilities.
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

`scripts/run_local_daemon.sh` will automatically load `.env` if present.

## Environment Configuration

Copy `.env.example` to `.env` and fill in real values:

```bash
cp .env.example .env
```

Key variables:

- `TTC_API_TOKEN`: protects `/ingest/*` write APIs
- `TTC_FEISHU_NOTIFY_ENABLED=true` + `TTC_FEISHU_CHAT_ID=oc_xxx`: enables Feishu CLI group notifications
- `ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET/REGION`: Aliyun CLI credentials
- `TTC_LLM_*`: optional LLM provider for JD parsing/classification

`.env` is gitignored. Do not commit it.

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

## Feishu CLI Notifications

The daemon uses `lark-cli` to send task notifications to a group. The bot must be a member of the chat.

1. Install [lark-cli](https://open.larksuite.com/document/tools-and-resources/lark-cli) and authenticate (`lark-cli auth login`).
2. Create a group and add the bot, or use an existing group.
3. Set `TTC_FEISHU_CHAT_ID` in `.env`.
4. Verify:

```bash
./scripts/check_env.sh
```

## Aliyun CLI

Configure the provided AccessKey:

```bash
aliyun configure set --profile ttc --mode AK \
  --access-key-id $ALIBABA_CLOUD_ACCESS_KEY_ID \
  --access-key-secret $ALIBABA_CLOUD_ACCESS_KEY_SECRET \
  --region $ALIBABA_CLOUD_REGION
```

Verify:

```bash
aliyun --profile ttc sts GetCallerIdentity
```

## Safety

Do not commit resumes, SQLite databases, `.env` files, API keys, AccessKeys, generated auth QR images, or local virtual environments. The `.gitignore` is configured to exclude those by default.
