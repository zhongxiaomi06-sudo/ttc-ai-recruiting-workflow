---
name: ttc
description: TTC AI 猎头工作流。用于 JD 摄入、人才搜索、候选人评分、电话任务派发和反馈闭环。
---

# TTC AI 猎头

## Overview

This skill orchestrates the TTC AI-headhunter workflow on the local daemon. It turns a JD or a search request into a ranked, evidence-backed call list, dispatches human phone-call tasks, and collects feedback for model calibration.

## Prerequisites

- TTC Daemon must be running at `http://127.0.0.1:8766`.
- `TTC_API_TOKEN` must be set if the daemon requires authentication.
- Source talent MySQL and/or candidate-collector should be configured.
- Feishu CLI notifications are optional but recommended (`TTC_FEISHU_NOTIFY_ENABLED=true`).

## Required Workflow

**Follow these steps in order. Do not skip steps.**

### Step 0: Verify daemon health

Call `health` or `status`. If the daemon is not reachable, pause and ask the user to run:

```bash
scripts/run_local_daemon.sh
```

### Step 1: Ingest the JD

Use `ingest_jd` with the JD text, URL, or Feishu document content. The daemon will create a `read_job`, classify it, normalize it, and route a high-confidence JD to a new Mission.

### Step 2: Monitor Mission progression

Poll `get_mission` until the state reaches one of:

- `human_pending` → phone-call tasks are ready
- `problem_pending` → human intervention is needed
- `closed` → workflow finished

### Step 3: Retrieve the call list

Use `get_call_list` to fetch ranked candidates with talking points, evidence, and verification questions.

### Step 4: Human phone calls

The daemon automatically creates `phone_caller` human tasks and notifies the recruiter via Feishu. The recruiter opens the HTML task page, calls the candidate, and submits feedback.

### Step 5: Feedback loop

After tasks are completed, the Mission moves to `feedback` and then `closed`. Use `submit_feedback` if you need to record feedback programmatically.

## Available Tools

- `health` — daemon health check
- `status` — counts of missions, tasks, artifacts
- `ingest_jd` — submit JD text or URL
- `get_mission` — mission state and tasks
- `step_mission` — manually advance a mission (debug)
- `get_call_list` — ranked candidates with scripts/evidence
- `get_human_task` — HTML task page
- `complete_human_task` — submit task outcome
- `get_source_talent_status` — check Source talent DB connectivity

## Practical Workflows

- **New JD from Feishu**: ingest the doc text → wait for `human_pending` → pull call list → notify recruiter.
- **Batch JDs**: ingest multiple JDs, list pending missions, prioritize by candidate count/score.
- **Candidate not reachable**: complete task with outcome `no_answer`; daemon records feedback.
- **JD unclear**: if Mission stalls in `problem_pending` with `jd_clarify`, ask the user for missing fields and resume.
- **Weekly review**: list closed missions and feedback to identify calibration opportunities.

## Tips for Maximum Productivity

- Always include the original JD text in `raw_text` for best classification accuracy.
- Let the daemon auto-advance; use `step_mission` only for debugging.
- Keep `TTC_FEISHU_NOTIFY_ENABLED=true` so recruiters get real-time task notifications.
- Use `get_source_talent_status` before large sourcing jobs to confirm DB connectivity.

## Troubleshooting

- **401 Unauthorized**: `TTC_API_TOKEN` mismatch; check `.env` and the plugin/tool request headers.
- **No candidates returned**: verify Source MySQL config (`~/.ttc/mysql.env`) and candidate-collector running on port 8765.
- **Feishu notifications not sent**: confirm `TTC_FEISHU_CHAT_ID` and that the bot is in the chat.
- **Mission stuck**: inspect `/dashboard` and task payloads; problem tasks include a `resume_action`.
