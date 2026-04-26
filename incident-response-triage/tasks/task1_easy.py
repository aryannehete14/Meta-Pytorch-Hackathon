"""
Task 1 — EASY
Scenario: The payment-service is down. One clear error in logs.
One obvious root cause. No noise alerts.
Agent must: identify root cause, silence 1 noise alert, escalate to payments team,
write a summary.
"""

from server.models import Alert, LogEntry, Metric, Observation, Action, Reward, AlertSeverity, _strict_clamp

TASK_ID = "task1_easy"

# Ground truth
CORRECT_ROOT_CAUSE_KEYWORDS = ["payment-service", "payment service", "database connection", "db connection", "postgres"]
NOISE_ALERT_IDS = {"alert-003"}          # CPU spike on unrelated service
CORRECT_ESCALATION = "payments-team"
CORRECT_SEVERITY = AlertSeverity.HIGH


def get_initial_observation() -> Observation:
    return Observation(
        task_id=TASK_ID,
        step=0,
        alerts=[
            Alert(
                id="alert-001",
                service="payment-service",
                severity=AlertSeverity.CRITICAL,
                message="payment-service health check FAILED — no response on port 8080",
                timestamp="2024-06-01T02:13:00Z",
                metric_value=0.0,
                metric_threshold=1.0,
            ),
            Alert(
                id="alert-002",
                service="payment-service",
                severity=AlertSeverity.HIGH,
                message="payment-service error rate spiked to 100% over last 5 minutes",
                timestamp="2024-06-01T02:13:15Z",
                metric_value=100.0,
                metric_threshold=5.0,
            ),
            Alert(
                id="alert-003",
                service="analytics-service",
                severity=AlertSeverity.LOW,
                message="analytics-service CPU usage at 78% — scheduled batch job running",
                timestamp="2024-06-01T02:12:00Z",
                metric_value=78.0,
                metric_threshold=80.0,
            ),
        ],
        logs=[
            LogEntry(
                timestamp="2024-06-01T02:12:45Z",
                service="payment-service",
                level="ERROR",
                message="Failed to acquire database connection from pool: connection refused to postgres:5432",
            ),
            LogEntry(
                timestamp="2024-06-01T02:12:46Z",
                service="payment-service",
                level="ERROR",
                message="PostgreSQL connection pool exhausted — all 20 connections timed out",
            ),
            LogEntry(
                timestamp="2024-06-01T02:12:47Z",
                service="payment-service",
                level="FATAL",
                message="Service entering crash loop — unable to process any requests without DB",
            ),
            LogEntry(
                timestamp="2024-06-01T02:12:00Z",
                service="analytics-service",
                level="INFO",
                message="Nightly aggregation job started — expected to use elevated CPU for 20 min",
            ),
        ],
        metrics=[
            Metric(service="payment-service", name="error_rate", value=100.0, unit="%", timestamp="2024-06-01T02:13:00Z"),
            Metric(service="payment-service", name="db_connections_active", value=0.0, unit="count", timestamp="2024-06-01T02:13:00Z"),
            Metric(service="payment-service", name="response_time_p99", value=30000.0, unit="ms", timestamp="2024-06-01T02:13:00Z"),
            Metric(service="analytics-service", name="cpu_usage", value=78.0, unit="%", timestamp="2024-06-01T02:13:00Z"),
        ],
        context={
            "on_call_engineer": "You",
            "incident_start": "2024-06-01T02:12:45Z",
            "services_affected": ["payment-service"],
            "teams": ["payments-team", "platform-team", "analytics-team"],
        },
        prompt=(
            "You are the on-call SRE. An incident has fired. Review the alerts, logs, and metrics. "
            "Identify the root cause, silence any noise alerts that are unrelated, decide who to escalate to "
            "(choose from: payments-team, platform-team, analytics-team), and draft a concise incident summary."
        ),
    )


def grade(action: Action) -> Reward:
    feedback_parts = []
    penalty = 0.0

    # 1. Root cause (0.0–1.0)
    rc_lower = action.root_cause.lower()
    root_cause_score = 1.0 if any(kw in rc_lower for kw in CORRECT_ROOT_CAUSE_KEYWORDS) else 0.0
    if root_cause_score == 0.0:
        feedback_parts.append("❌ Root cause missed — logs clearly show postgres connection failure.")
    else:
        feedback_parts.append("✅ Root cause correctly identified.")

    # 2. Noise filtering (0.0–1.0)
    silenced = set(action.silenced_alert_ids)
    correctly_silenced = silenced & NOISE_ALERT_IDS
    incorrectly_silenced = silenced - NOISE_ALERT_IDS
    noise_filtering_score = len(correctly_silenced) / len(NOISE_ALERT_IDS)
    if incorrectly_silenced:
        penalty += 0.1 * len(incorrectly_silenced)
        feedback_parts.append(f"⚠️ Incorrectly silenced real alerts: {incorrectly_silenced}")
    if correctly_silenced:
        feedback_parts.append("✅ Noise alert correctly silenced.")
    else:
        feedback_parts.append("❌ Noise alert not silenced — analytics CPU alert is unrelated scheduled job.")

    # 3. Escalation (0.0–1.0)
    escalation_score = 1.0 if action.escalate_to and CORRECT_ESCALATION in action.escalate_to.lower().replace(" ", "-") else 0.0
    if escalation_score == 0.0:
        feedback_parts.append(f"❌ Wrong escalation target. Expected: {CORRECT_ESCALATION}.")
    else:
        feedback_parts.append("✅ Escalated to the correct team.")

    # 4. Summary quality (0.0–1.0) — heuristic checks
    summary_lower = action.incident_summary.lower()
    summary_score = 0.0
    if "payment" in summary_lower:
        summary_score += 0.4
    if any(kw in summary_lower for kw in ["database", "postgres", "db", "connection"]):
        summary_score += 0.4
    if len(action.incident_summary) >= 50:
        summary_score += 0.2
    summary_score = min(summary_score, 1.0)
    feedback_parts.append(f"Summary score: {summary_score:.2f}")

    # Severity penalty
    if action.severity_assessment not in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
        penalty += 0.1
        feedback_parts.append("⚠️ Severity under-assessed — payment outage is HIGH/CRITICAL.")

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
        root_cause_score=root_cause_score,
        noise_filtering_score=noise_filtering_score,
        escalation_score=escalation_score,
        summary_score=round(summary_score, 4),
        penalty=round(penalty, 4),
        feedback=" | ".join(feedback_parts),
    )