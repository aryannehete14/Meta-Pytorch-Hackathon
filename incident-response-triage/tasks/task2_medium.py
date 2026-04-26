"""
Task 2 — MEDIUM
Scenario: Cascading failure. order-service and notification-service are both
throwing errors, but the REAL root cause is auth-service returning 503s.
Multiple noise alerts. Agent must trace upstream dependency failure.
"""

from server.models import Alert, LogEntry, Metric, Observation, Action, Reward, AlertSeverity, _strict_clamp

TASK_ID = "task2_medium"

CORRECT_ROOT_CAUSE_KEYWORDS = ["auth-service", "auth service", "authentication", "token validation", "jwt"]
NOISE_ALERT_IDS = {"alert-m004", "alert-m005"}   # disk usage warn + scheduled maintenance
CORRECT_ESCALATION = "platform-team"
CORRECT_SEVERITY = AlertSeverity.CRITICAL


def get_initial_observation() -> Observation:
    return Observation(
        task_id=TASK_ID,
        step=0,
        alerts=[
            Alert(
                id="alert-m001",
                service="order-service",
                severity=AlertSeverity.CRITICAL,
                message="order-service: 94% of requests returning HTTP 401 Unauthorized",
                timestamp="2024-06-02T14:22:00Z",
                metric_value=94.0,
                metric_threshold=1.0,
            ),
            Alert(
                id="alert-m002",
                service="notification-service",
                severity=AlertSeverity.HIGH,
                message="notification-service: Failed to dispatch 1,200 email jobs in last 10 min — auth token invalid",
                timestamp="2024-06-02T14:22:30Z",
                metric_value=1200.0,
                metric_threshold=0.0,
            ),
            Alert(
                id="alert-m003",
                service="auth-service",
                severity=AlertSeverity.CRITICAL,
                message="auth-service: p99 latency 28,000ms — service not responding",
                timestamp="2024-06-02T14:21:45Z",
                metric_value=28000.0,
                metric_threshold=500.0,
            ),
            Alert(
                id="alert-m004",
                service="logging-service",
                severity=AlertSeverity.LOW,
                message="logging-service: disk usage at 72% — within normal operating range",
                timestamp="2024-06-02T14:20:00Z",
                metric_value=72.0,
                metric_threshold=85.0,
            ),
            Alert(
                id="alert-m005",
                service="batch-runner",
                severity=AlertSeverity.LOW,
                message="batch-runner: scheduled maintenance window active — reduced throughput expected",
                timestamp="2024-06-02T14:15:00Z",
                metric_value=None,
                metric_threshold=None,
            ),
        ],
        logs=[
            LogEntry(
                timestamp="2024-06-02T14:21:30Z",
                service="auth-service",
                level="ERROR",
                message="Redis cache connection timeout after 30s — token store unavailable",
            ),
            LogEntry(
                timestamp="2024-06-02T14:21:31Z",
                service="auth-service",
                level="ERROR",
                message="JWT validation fallback failed — cannot reach token introspection endpoint",
            ),
            LogEntry(
                timestamp="2024-06-02T14:21:45Z",
                service="auth-service",
                level="FATAL",
                message="auth-service entering degraded mode — all token validations returning 503",
            ),
            LogEntry(
                timestamp="2024-06-02T14:22:00Z",
                service="order-service",
                level="ERROR",
                message="Upstream auth-service returned 503 on token validation — rejecting request with 401",
            ),
            LogEntry(
                timestamp="2024-06-02T14:22:01Z",
                service="order-service",
                level="ERROR",
                message="Circuit breaker OPEN for auth-service dependency — all order requests failing fast",
            ),
            LogEntry(
                timestamp="2024-06-02T14:22:20Z",
                service="notification-service",
                level="WARN",
                message="Auth token refresh failed — received 503 from auth-service, retrying in 30s",
            ),
            LogEntry(
                timestamp="2024-06-02T14:22:30Z",
                service="notification-service",
                level="ERROR",
                message="Max retries exceeded on auth refresh — dropping 1200 queued notification jobs",
            ),
            LogEntry(
                timestamp="2024-06-02T14:20:00Z",
                service="logging-service",
                level="INFO",
                message="Disk usage check: 72% — within operational thresholds. No action required.",
            ),
        ],
        metrics=[
            Metric(service="auth-service", name="p99_latency_ms", value=28000.0, unit="ms", timestamp="2024-06-02T14:22:00Z"),
            Metric(service="auth-service", name="error_rate", value=100.0, unit="%", timestamp="2024-06-02T14:22:00Z"),
            Metric(service="auth-service", name="redis_connections", value=0.0, unit="count", timestamp="2024-06-02T14:22:00Z"),
            Metric(service="order-service", name="error_rate", value=94.0, unit="%", timestamp="2024-06-02T14:22:00Z"),
            Metric(service="notification-service", name="jobs_failed", value=1200.0, unit="count", timestamp="2024-06-02T14:22:30Z"),
            Metric(service="logging-service", name="disk_usage", value=72.0, unit="%", timestamp="2024-06-02T14:22:00Z"),
        ],
        context={
            "service_dependency_map": {
                "order-service": ["auth-service", "postgres"],
                "notification-service": ["auth-service", "sendgrid"],
                "auth-service": ["redis-cache", "postgres"],
            },
            "teams": ["payments-team", "platform-team", "notifications-team"],
            "on_call_engineer": "You",
        },
        prompt=(
            "You are the on-call SRE. Multiple services are alerting simultaneously. "
            "Use the logs, metrics, and dependency map to trace the ROOT upstream cause. "
            "Silence noise alerts, escalate to the correct team "
            "(choose from: payments-team, platform-team, notifications-team), "
            "and write a clear incident summary that identifies the chain of failure."
        ),
    )


def grade(action: Action) -> Reward:
    feedback_parts = []
    penalty = 0.0

    # 1. Root cause — must identify auth-service (not the downstream symptoms)
    rc_lower = action.root_cause.lower()
    if any(kw in rc_lower for kw in CORRECT_ROOT_CAUSE_KEYWORDS):
        root_cause_score = 1.0
        feedback_parts.append("✅ Correctly identified auth-service as upstream root cause.")
    elif any(kw in rc_lower for kw in ["order-service", "notification-service"]):
        root_cause_score = 0.2   # partial — found a symptom, not the cause
        penalty += 0.1
        feedback_parts.append("⚠️ Identified downstream symptom, not upstream root cause (auth-service).")
    else:
        root_cause_score = 0.0
        feedback_parts.append("❌ Root cause incorrect.")

    # 2. Noise filtering
    silenced = set(action.silenced_alert_ids)
    correctly_silenced = silenced & NOISE_ALERT_IDS
    incorrectly_silenced = silenced - NOISE_ALERT_IDS
    noise_filtering_score = len(correctly_silenced) / len(NOISE_ALERT_IDS)
    if incorrectly_silenced:
        penalty += 0.1 * len(incorrectly_silenced)
        feedback_parts.append(f"⚠️ Silenced real alerts: {incorrectly_silenced}")
    feedback_parts.append(f"Noise filtering: {len(correctly_silenced)}/{len(NOISE_ALERT_IDS)} correct.")

    # 3. Escalation — platform-team owns auth + redis infra
    escalation_score = 1.0 if action.escalate_to and "platform" in action.escalate_to.lower() else 0.0
    if escalation_score == 0.0:
        feedback_parts.append("❌ Wrong escalation — platform-team owns auth-service and Redis.")
    else:
        feedback_parts.append("✅ Correctly escalated to platform-team.")

    # 4. Summary — should mention cascading + auth + redis/upstream
    summary_lower = action.incident_summary.lower()
    summary_score = 0.0
    if "auth" in summary_lower:
        summary_score += 0.3
    if any(kw in summary_lower for kw in ["cascad", "downstream", "upstream", "dependency"]):
        summary_score += 0.3
    if any(kw in summary_lower for kw in ["redis", "cache", "token"]):
        summary_score += 0.2
    if len(action.incident_summary) >= 60:
        summary_score += 0.2
    summary_score = min(summary_score, 1.0)
    feedback_parts.append(f"Summary score: {summary_score:.2f}")

    # Severity check
    if action.severity_assessment != AlertSeverity.CRITICAL:
        penalty += 0.05
        feedback_parts.append("⚠️ Should be CRITICAL — multiple services fully impacted.")

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