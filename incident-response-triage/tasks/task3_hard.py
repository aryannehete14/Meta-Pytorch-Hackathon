"""
Task 3 — HARD
Scenario: Partial degradation — NOT a full outage. Checkout is slow but not down.
Metrics look mostly fine at first glance. The real cause is a memory leak in
recommendation-service causing GC pressure that cascades into checkout latency.
Multiple misleading alerts. Agent must correlate 4+ signals to find the subtle cause.
No obvious error logs — only warnings and unusual patterns.
"""

from server.models import Alert, LogEntry, Metric, Observation, Action, Reward, AlertSeverity, _strict_clamp

TASK_ID = "task3_hard"

CORRECT_ROOT_CAUSE_KEYWORDS = [
    "recommendation-service", "recommendation service",
    "memory leak", "memory pressure", "gc pressure",
    "garbage collection", "heap", "oom",
]
NOISE_ALERT_IDS = {"alert-h003", "alert-h005", "alert-h006"}
CORRECT_ESCALATION_TEAMS = ["backend-team", "backend team", "recommendations-team", "recommendations team"]
CORRECT_SEVERITY = AlertSeverity.HIGH


def get_initial_observation() -> Observation:
    return Observation(
        task_id=TASK_ID,
        step=0,
        alerts=[
            Alert(
                id="alert-h001",
                service="checkout-service",
                severity=AlertSeverity.HIGH,
                message="checkout-service: p95 latency 4,200ms — SLA breach (threshold: 2,000ms)",
                timestamp="2024-06-03T19:05:00Z",
                metric_value=4200.0,
                metric_threshold=2000.0,
            ),
            Alert(
                id="alert-h002",
                service="recommendation-service",
                severity=AlertSeverity.MEDIUM,
                message="recommendation-service: average response time elevated to 1,800ms (normal: 200ms)",
                timestamp="2024-06-03T19:03:00Z",
                metric_value=1800.0,
                metric_threshold=500.0,
            ),
            Alert(
                id="alert-h003",
                service="cdn-service",
                severity=AlertSeverity.LOW,
                message="cdn-service: cache hit rate dropped to 81% (normal fluctuation)",
                timestamp="2024-06-03T19:00:00Z",
                metric_value=81.0,
                metric_threshold=85.0,
            ),
            Alert(
                id="alert-h004",
                service="recommendation-service",
                severity=AlertSeverity.HIGH,
                message="recommendation-service: JVM heap usage at 94% — GC cycles taking 800ms each",
                timestamp="2024-06-03T19:04:30Z",
                metric_value=94.0,
                metric_threshold=85.0,
            ),
            Alert(
                id="alert-h005",
                service="email-service",
                severity=AlertSeverity.LOW,
                message="email-service: promotional campaign sending — elevated outbound volume",
                timestamp="2024-06-03T19:00:00Z",
                metric_value=None,
                metric_threshold=None,
            ),
            Alert(
                id="alert-h006",
                service="search-service",
                severity=AlertSeverity.LOW,
                message="search-service: index rebuild in progress — minor query delay expected",
                timestamp="2024-06-03T18:55:00Z",
                metric_value=None,
                metric_threshold=None,
            ),
        ],
        logs=[
            LogEntry(
                timestamp="2024-06-03T18:55:00Z",
                service="recommendation-service",
                level="WARN",
                message="Heap allocation rate exceeding baseline: 850MB/min (normal: 120MB/min)",
            ),
            LogEntry(
                timestamp="2024-06-03T19:00:00Z",
                service="recommendation-service",
                level="WARN",
                message="Full GC triggered — stop-the-world pause of 620ms — heap freed 8% only",
            ),
            LogEntry(
                timestamp="2024-06-03T19:02:00Z",
                service="recommendation-service",
                level="WARN",
                message="Full GC triggered again — pause 810ms — memory not being released: possible leak in model cache",
            ),
            LogEntry(
                timestamp="2024-06-03T19:03:00Z",
                service="checkout-service",
                level="WARN",
                message="Call to recommendation-service timed out after 2,000ms — using fallback recommendations",
            ),
            LogEntry(
                timestamp="2024-06-03T19:03:30Z",
                service="checkout-service",
                level="WARN",
                message="Fallback recommendation fetch also slow (1,800ms) — downstream dependency degraded",
            ),
            LogEntry(
                timestamp="2024-06-03T19:04:00Z",
                service="checkout-service",
                level="WARN",
                message="Thread pool saturation at 87% — slow upstream responses holding threads",
            ),
            LogEntry(
                timestamp="2024-06-03T19:04:30Z",
                service="recommendation-service",
                level="ERROR",
                message="OutOfMemoryError imminent — heap 94% — reducing feature computation to emergency mode",
            ),
            LogEntry(
                timestamp="2024-06-03T19:00:00Z",
                service="cdn-service",
                level="INFO",
                message="Cache hit rate fluctuation — within acceptable variance for time of day",
            ),
        ],
        metrics=[
            # Checkout metrics — latency issue but not error rate
            Metric(service="checkout-service", name="p95_latency_ms", value=4200.0, unit="ms", timestamp="2024-06-03T19:05:00Z"),
            Metric(service="checkout-service", name="p50_latency_ms", value=1100.0, unit="ms", timestamp="2024-06-03T19:05:00Z"),
            Metric(service="checkout-service", name="error_rate", value=2.1, unit="%", timestamp="2024-06-03T19:05:00Z"),
            Metric(service="checkout-service", name="thread_pool_saturation", value=87.0, unit="%", timestamp="2024-06-03T19:05:00Z"),
            # Recommendation service — the smoking gun
            Metric(service="recommendation-service", name="jvm_heap_usage", value=94.0, unit="%", timestamp="2024-06-03T19:04:30Z"),
            Metric(service="recommendation-service", name="gc_pause_ms", value=810.0, unit="ms", timestamp="2024-06-03T19:04:00Z"),
            Metric(service="recommendation-service", name="heap_alloc_rate_mb_min", value=850.0, unit="MB/min", timestamp="2024-06-03T19:04:00Z"),
            Metric(service="recommendation-service", name="p99_latency_ms", value=3800.0, unit="ms", timestamp="2024-06-03T19:04:30Z"),
            # Noise
            Metric(service="cdn-service", name="cache_hit_rate", value=81.0, unit="%", timestamp="2024-06-03T19:05:00Z"),
        ],
        context={
            "service_dependency_map": {
                "checkout-service": ["recommendation-service", "inventory-service", "payment-service"],
                "recommendation-service": ["ml-feature-store", "redis-cache"],
            },
            "deployment_history": [
                {"service": "recommendation-service", "version": "v2.4.1", "deployed_at": "2024-06-03T17:30:00Z", "change": "Updated ML model cache — increased cache size 4x"},
                {"service": "checkout-service", "version": "v3.1.0", "deployed_at": "2024-06-02T10:00:00Z", "change": "Minor UI copy change"},
            ],
            "teams": ["backend-team", "platform-team", "recommendations-team", "frontend-team"],
            "on_call_engineer": "You",
            "business_impact": "Checkout page slow — conversion rate dropped 18% in last 15 min",
        },
        prompt=(
            "You are the on-call SRE. The checkout page is degraded but NOT fully down. "
            "Error rates look low but latency is high. Correlate the alerts, logs, metrics, "
            "AND deployment history to find the non-obvious root cause. "
            "Silence noise alerts, determine the correct escalation team "
            "(choose from: backend-team, platform-team, recommendations-team, frontend-team), "
            "and write a precise incident summary that explains the failure chain and business impact. "
            "NOTE: This is a subtle partial degradation — be precise about what is and is not failing."
        ),
    )


def grade(action: Action) -> Reward:
    feedback_parts = []
    penalty = 0.0

    # 1. Root cause — must identify recommendation-service memory leak / GC pressure
    rc_lower = action.root_cause.lower()
    if any(kw in rc_lower for kw in ["memory leak", "gc pressure", "garbage collection", "heap", "oom", "out of memory"]):
        root_cause_score = 1.0
        feedback_parts.append("✅ Precisely identified memory leak / GC pressure as root cause.")
    elif "recommendation" in rc_lower:
        root_cause_score = 0.6   # found the right service but not the mechanism
        feedback_parts.append("⚠️ Correctly identified recommendation-service but missed memory leak mechanism.")
    elif "checkout" in rc_lower:
        root_cause_score = 0.1
        penalty += 0.15
        feedback_parts.append("❌ Identified downstream symptom (checkout latency) not upstream root cause.")
    else:
        root_cause_score = 0.0
        feedback_parts.append("❌ Root cause incorrect.")

    # 2. Noise filtering — 3 noise alerts to silence
    silenced = set(action.silenced_alert_ids)
    correctly_silenced = silenced & NOISE_ALERT_IDS
    incorrectly_silenced = silenced - NOISE_ALERT_IDS
    noise_filtering_score = len(correctly_silenced) / len(NOISE_ALERT_IDS)
    if incorrectly_silenced:
        penalty += 0.1 * len(incorrectly_silenced)
        feedback_parts.append(f"⚠️ Incorrectly silenced: {incorrectly_silenced}")
    feedback_parts.append(f"Noise filtering: {len(correctly_silenced)}/{len(NOISE_ALERT_IDS)}.")

    # 3. Escalation — backend-team or recommendations-team both acceptable
    escalation_score = 0.0
    if action.escalate_to:
        esc = action.escalate_to.lower().replace("-", " ")
        if any(team.replace("-", " ") in esc for team in CORRECT_ESCALATION_TEAMS):
            escalation_score = 1.0
            feedback_parts.append("✅ Correct escalation team.")
        else:
            feedback_parts.append("❌ Wrong escalation — backend-team or recommendations-team owns the JVM service.")
    else:
        penalty += 0.1
        feedback_parts.append("❌ No escalation provided — this requires human involvement.")

    # 4. Summary — should mention: partial degradation, memory/GC, recommendation-service, business impact
    summary_lower = action.incident_summary.lower()
    summary_score = 0.0
    if any(kw in summary_lower for kw in ["partial", "degraded", "degradation", "slow", "latency"]):
        summary_score += 0.2
    if "recommendation" in summary_lower:
        summary_score += 0.2
    if any(kw in summary_lower for kw in ["memory", "heap", "gc", "garbage", "leak"]):
        summary_score += 0.3
    if any(kw in summary_lower for kw in ["checkout", "conversion", "business", "impact"]):
        summary_score += 0.15
    if len(action.incident_summary) >= 80:
        summary_score += 0.15
    summary_score = min(summary_score, 1.0)
    feedback_parts.append(f"Summary score: {summary_score:.2f}")

    # Severity penalty — this is HIGH, not CRITICAL (service not fully down)
    if action.severity_assessment == AlertSeverity.LOW:
        penalty += 0.15
        feedback_parts.append("⚠️ Severity too low — checkout SLA breach is HIGH.")
    elif action.severity_assessment == AlertSeverity.MEDIUM:
        penalty += 0.05
        feedback_parts.append("⚠️ Severity slightly under-assessed — should be HIGH.")

    penalty = min(penalty, 0.3)
    total = (
        0.35 * root_cause_score +
        0.20 * noise_filtering_score +
        0.25 * escalation_score +
        0.20 * summary_score
    ) - penalty
    total = _strict_clamp(total)

    return Reward(
        total=round(total, 4),
        root_cause_score=round(root_cause_score, 4),
        noise_filtering_score=round(noise_filtering_score, 4),
        escalation_score=escalation_score,
        summary_score=round(summary_score, 4),
        penalty=round(penalty, 4),
        feedback=" | ".join(feedback_parts),
    )