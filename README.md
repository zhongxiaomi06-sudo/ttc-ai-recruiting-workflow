# TTC AI Recruiting Workflow

AI-led recruiting workflow for JD ingestion, artifact classification, candidate sourcing, scoring, human task dispatch, and server deployment.

## What Is Included

- `ttc_daemon/`: FastAPI daemon, mission state machine, ingestion pipeline, Source talent adapters.
- `candidate-collector/`: local candidate collection helper.
- `scripts/`: local run, resume batch ingest, MySQL connection check, and environment check utilities.
- `deploy/`, `Dockerfile`, `docker-compose.yml`: server deployment assets.
- `ttc-feishu-bridge.user.js`, `ttc-chatgpt-reader.user.js`: browser userscripts.
- Architecture and deployment documentation in Markdown/HTML files.

## Current Shared Entry

The currently deployed project is served from the TalentMatch server:

- TalentMatch frontend: `https://yorkteam.cn`
- TTC workflow backend prefix: `https://yorkteam.cn/api/ttc`
- TTC workflow dashboard: `https://yorkteam.cn/api/ttc/dashboard`
- Health check: `https://yorkteam.cn/api/ttc/health`

On the server the TTC daemon runs behind nginx as a systemd service:

```bash
systemctl status ttc-daemon
systemctl restart ttc-daemon
journalctl -u ttc-daemon -f
```

The service working directory is `/opt/ttc-automation`, and the production
environment file is `/opt/ttc-automation/.env.server`.

## Local Development Run

Use this only for local debugging. The shared project should be accessed through
the TalentMatch server above.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: only needed when using automatic browser/page reading.
python3 -m playwright install chromium

cp .env.example .env
scripts/run_local_daemon.sh
```

Open the local daemon directly:

```text
http://127.0.0.1:8766/dashboard
```

## Public Resume Static Crawler

For public or explicitly authorized static HTML pages, start with the conservative
`httpx + BeautifulSoup` crawler:

```bash
python scripts/crawl_public_resumes_httpx.py \
  --seed "https://example.com/resumes/" \
  --max-pages 50 \
  --max-depth 1 \
  --output data/public_resume_crawl.jsonl
```

To push matched pages into the local candidate collector:

```bash
python scripts/crawl_public_resumes_httpx.py \
  --seed-file data/resume_seed_urls.txt \
  --send-collector \
  --collector-url http://127.0.0.1:8765
```

This tool only fetches static HTML, respects `robots.txt` by default, rate-limits
requests, and does not log in, replay cookies, bypass captchas, or evade platform
controls. Use Playwright only for authorized pages that genuinely need JavaScript
rendering.

If port `8766` is already in use, stop the old local process first:

```bash
lsof -nP -iTCP:8766 -sTCP:LISTEN
kill <PID>
```

`scripts/run_local_daemon.sh` automatically loads `.env` and `~/.ttc/mysql.env`
when they exist. For local write APIs it defaults `TTC_API_TOKEN` to
`localtest`; production uses the token from `.env.server`.

## Environment Configuration

For local development, copy `.env.example` to `.env` and fill in real values:

```bash
cp .env.example .env
```

Key variables:

- `TTC_API_TOKEN`: protects `/ingest/*` write APIs
- `TTC_FEISHU_NOTIFY_ENABLED=true` + `TTC_FEISHU_CHAT_ID=oc_xxx`: enables Feishu CLI group notifications
- `ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET/REGION`: Aliyun CLI credentials
- `TTC_LLM_*`: optional LLM provider for JD parsing/classification

`.env` is gitignored. Do not commit it.

For the TalentMatch server, use `.env.server.example` as the template:

```bash
cd /opt/ttc-automation
cp .env.server.example .env.server
vim .env.server
deploy/server_bootstrap.sh
```

The nginx config should include the TTC location block from
`deploy/nginx-talentmatch-ttc.conf`, which proxies `/api/ttc/*` to
`127.0.0.1:8766`.

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

## Precise talent matching agents

The production-oriented matching entrypoint is `scripts/llm_jd_match_report.py`. It runs each JD independently through these agents:

1. `RecallAgent`: multi-query, multi-page TTC recall and stable-ID deduplication.
2. `EnrichmentAgent`: optional profile enrichment without inventing missing resume content.
3. `QualityGateAgent`: grades data A/B/C and quarantines generated fixtures.
4. `HardFilterAgent`: applies location, age, experience, degree, and job-specific must-haves using pass/review/fail states.
5. `SemanticScoringAgent`: evidence-constrained semantic scoring; all scores are recomputed from configured dimension weights.
6. `AuditAgent`: prevents generated data, low-quality summaries, or unverified strong recommendations from entering final output.

Run a small validation batch:

```bash
venv/bin/python scripts/llm_jd_match_report.py \
  --limit 10 \
  --pages 1 \
  --enrich-limit 10 \
  --top-n 5
```

The JSON output separates `data` (verified recommendations), `review_pool` (missing evidence or unknown hard conditions), and `rejected`. A C-grade search summary is never promoted directly into the final recommendation list.
