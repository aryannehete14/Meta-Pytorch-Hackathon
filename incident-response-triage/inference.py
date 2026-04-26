#!/usr/bin/env python3
"""
Baseline inference script for Incident Response Triage OpenEnv.
Updated to ensure scores are strictly within the range (0, 1).
"""

import os
import json
import time
import httpx
from openai import OpenAI

# ── Config from environment variables ─────────────────────────────────────────
LLM_KEY = os.environ["API_KEY"]
LLM_BASE = os.environ["API_BASE_URL"].rstrip("/")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o")

ENV_URL = "https://KeyaChaudhary-incident-response-triage.hf.space"
TASKS = ["task1_easy", "task2_medium", "task3_hard"]

client = OpenAI(api_key=LLM_KEY, base_url=LLM_BASE)

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) performing incident triage.
Respond with ONLY valid JSON. Identify the root cause, silence noise, and propose a fix."""

def normalize_score(score: float) -> float:
    """
    Forces scores into the strict (0, 1) range.
    1.0 becomes 0.99
    0.0 becomes 0.01
    """
    try:
        val = float(score)
        if val >= 1.0:
            return 0.99
        if val <= 0.0:
            return 0.01
        return round(val, 3)
    except:
        return 0.01

def call_env(method: str, endpoint: str, payload: dict = None) -> dict:
    url = f"{ENV_URL.rstrip('/')}{endpoint}"
    with httpx.Client(timeout=30) as http:
        if method == "POST":
            r = http.post(url, json=payload or {})
        else:
            r = http.get(url)
        r.raise_for_status()
        return r.json()

def run_task(task_id: str) -> dict:
    obs = call_env("POST", "/reset", {"task_id": task_id})

    print(f"[START] task={task_id} step=0", flush=True)

    user_message = f"TASK: {task_id}\nALERTS: {json.dumps(obs['alerts'])}"

    t0 = time.time()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.0,
    )
    latency_ms = int((time.time() - t0) * 1000)

    raw_action = response.choices[0].message.content.strip()
    if "{" in raw_action:
        raw_action = raw_action[raw_action.find("{"):raw_action.rfind("}")+1]
    
    action_dict = json.loads(raw_action)
    print(f"[STEP] task={task_id} step=1 latency_ms={latency_ms}", flush=True)

    step_result = call_env("POST", "/step", {"task_id": task_id, **action_dict})
    
    # Apply strict normalization to the individual task score
    final_score = normalize_score(step_result["reward"]["total"])

    print(f"[END] task={task_id} score={final_score:0.3f} steps=1", flush=True)

    return {
        "task_id": task_id,
        "reward": final_score
    }

def main():
    print(f"[START] event=baseline_run_begin model={MODEL_NAME} tasks={len(TASKS)}", flush=True)

    results = []
    for task_id in TASKS:
        try:
            result = run_task(task_id)
            results.append(result)
        except Exception as e:
            # Fallback score must also be strictly > 0
            print(f"[END] task={task_id} score=0.001 steps=0 error={str(e)}", flush=True)
            results.append({"task_id": task_id, "reward": 0.001})

    # Ensure the average reward is also normalized
    raw_avg = sum(r["reward"] for r in results) / len(results)
    avg_reward = normalize_score(raw_avg)

    print(f"[END] event=baseline_run_complete average_reward={avg_reward:0.3f}", flush=True)

if __name__ == "__main__":
    main()