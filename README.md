---
title: incident-response-triage
emoji: 🚨
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
tags:
  - openenv
---

# 🚨 Incident Response Triage — OpenEnv

An OpenEnv-compliant environment where AI agents learn to triage production incidents like a senior SRE.

---

## 🎯 Environment Description

Real on-call engineers receive floods of alerts, logs, and metrics during production incidents. They must:
1. Identify the true root cause (not downstream symptoms)
2. Filter out noise alerts to reduce cognitive load
3. Escalate to the right team
4. Draft a concise, actionable incident summary

This environment simulates exactly that workflow with three progressively harder scenarios, providing partial reward signals across all four dimensions.

**Why this matters:** MTTR (Mean Time to Resolution) is a critical SRE KPI. Training agents to triage effectively could dramatically reduce incident response time.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/reset` | Start a new episode. Body: `{"task_id": "task1_easy"}` |
| POST | `/step` | Submit an action. Returns observation, reward, done, info |
| GET | `/state` | Current environment state (non-destructive) |
| GET | `/tasks` | List all tasks with difficulty |
| GET | `/health` | Health check |

---

## 📥 Observation Space

```json
{
  "task_id": "string",
  "step": "integer",
  "alerts": [
    {
      "id": "string",
      "service": "string",
      "severity": "low | medium | high | critical",
      "message": "string",
      "timestamp": "ISO8601",
      "metric_value": "float | null",
      "metric_threshold": "float | null"
    }
  ],
  "logs": [
    {
      "timestamp": "ISO8601",
      "service": "string",
      "level": "INFO | WARN | ERROR | FATAL",
      "message": "string"
    }
  ],
  "metrics": [
    {
      "service": "string",
      "name": "string",
      "value": "float",
      "unit": "string",
      "timestamp": "ISO8601"
    }
  ],
  "context": "object (deployment history, service maps, teams)",
  "prompt": "string (human-readable instruction)"
}
```

## 📤 Action Space

```json
{
  "root_cause": "string — identified root cause service or mechanism",
  "silenced_alert_ids": ["list of alert IDs to silence as noise"],
  "escalate_to": "string | null — team to escalate to",
  "incident_summary": "string — 2-4 sentence summary",
  "severity_assessment": "low | medium | high | critical",
  "proposed_fix": "string | null — optional remediation"
}
```

---

## 🏆 Tasks

### Task 1 — Easy (`task1_easy`)
**Scenario:** payment-service is fully down. PostgreSQL connection pool exhausted.  
**Signals:** Clear error logs, 2 relevant alerts, 1 noise alert (analytics CPU).  
**Agent must:** Identify DB connection failure, silence analytics alert, escalate to payments-team.  
**Expected score for frontier model:** 0.85–1.0

### Task 2 — Medium (`task2_medium`)
**Scenario:** Cascading failure. auth-service Redis connection fails, causing order-service and notification-service to error.  
**Signals:** 5 alerts (2 noise), 8 logs across 3 services, service dependency map.  
**Agent must:** Trace upstream to auth-service, not blame downstream symptoms, escalate to platform-team.  
**Expected score for frontier model:** 0.65–0.85

### Task 3 — Hard (`task3_hard`)
**Scenario:** Partial degradation. recommendation-service JVM memory leak → GC pressure → checkout latency. No full outage. No ERROR logs — only WARNs.  
**Signals:** 6 alerts (3 noise), 8 logs, deployment history showing 4x cache size increase.  
**Agent must:** Correlate heap metrics + GC pause logs + deployment history + dependency map. Must distinguish partial degradation from full outage.  
**Expected score for frontier model:** 0.40–0.70

---

## 🎁 Reward Function

Reward is computed across 4 components with partial progress signals:

| Component | Weight | What it measures |
|-----------|--------|------------------|
| `root_cause_score` | 35% | Correct identification of root cause (partial credit for right service, wrong mechanism) |
| `escalation_score` | 25% | Correct team escalated to |
| `summary_score` | 20% | Summary mentions key facts: service, mechanism, impact |
| `noise_filtering_score` | 20% | Noise alerts correctly silenced |
| `penalty` | up to -30% | False positives, missed escalations, wrong severity |

**Total = (weighted sum) − penalty, clamped to [0.0, 1.0]**

---

## 🚀 Setup & Usage

### Run locally

```bash
git clone <your-repo>
cd incident-response-env
pip install -r requirements.txt
uvicorn server.main:app --host 0.0.0.0 --port 7860
```

### Docker

```bash
docker build -t incident-response-env .
docker run -p 7860:7860 incident-response-env
```

### Run baseline inference

```bash
export OPENAI_API_KEY=your_key
export API_BASE_URL=http://localhost:7860
export MODEL_NAME=gpt-4o
python inference.py
```

### Validate OpenEnv compliance

```bash
pip install openenv-core
openenv validate
```

---

## 📊 Baseline Scores

| Task | Model | Score |
|------|-------|-------|
| task1_easy | gpt-4o | ~0.90 |
| task2_medium | gpt-4o | ~0.72 |
| task3_hard | gpt-4o | ~0.52 |

---

## 🔧 Environment Variables

| Variable | Description |
|----------|-------------|
| `API_BASE_URL` | Base URL of the deployed environment |
| `MODEL_NAME` | LLM model identifier for inference |
| `HF_TOKEN` | Hugging Face / API key |
| `OPENAI_API_KEY` | OpenAI API key for inference script |
