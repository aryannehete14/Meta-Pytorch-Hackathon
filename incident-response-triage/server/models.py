from pydantic import BaseModel, Field
from typing import Any, Optional
from enum import Enum


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketCategory(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    COMPLAINT = "complaint"
    LEGAL = "legal"
    SPAM = "spam"


# ── Observation ────────────────────────────────────────────────────────────────

class Alert(BaseModel):
    id: str
    service: str
    severity: AlertSeverity
    message: str
    timestamp: str
    metric_value: Optional[float] = None
    metric_threshold: Optional[float] = None


class LogEntry(BaseModel):
    timestamp: str
    service: str
    level: str
    message: str


class Metric(BaseModel):
    service: str
    name: str
    value: float
    unit: str
    timestamp: str


class Observation(BaseModel):
    task_id: str
    step: int
    alerts: list[Alert]
    logs: list[LogEntry]
    metrics: list[Metric]
    context: dict[str, Any] = Field(default_factory=dict)
    prompt: str  # human-readable instruction to the agent


# ── Action ─────────────────────────────────────────────────────────────────────

class Action(BaseModel):
    root_cause: str = Field(
        description="The identified root cause of the incident (service name or description)"
    )
    silenced_alert_ids: list[str] = Field(
        default_factory=list,
        description="List of alert IDs the agent considers noise and wants to silence"
    )
    escalate_to: Optional[str] = Field(
        default=None,
        description="Team or person to escalate to. None if agent resolves autonomously."
    )
    incident_summary: str = Field(
        description="A concise incident summary draft (2-4 sentences)"
    )
    severity_assessment: AlertSeverity = Field(
        description="Agent's overall severity assessment of the incident"
    )
    proposed_fix: Optional[str] = Field(
        default=None,
        description="Short proposed remediation action"
    )


# ── Reward ─────────────────────────────────────────────────────────────────────

def _strict_clamp(v: float) -> float:
    """Clamp to strictly open interval (0.001, 0.999) as required by validator."""
    return round(max(0.001, min(0.999, v)), 4)


class Reward(BaseModel):
    total: float = Field(ge=0.001, le=0.999, description="Overall reward strictly in (0,1)")
    root_cause_score: float = Field(ge=0.0, le=1.0)
    noise_filtering_score: float = Field(ge=0.0, le=1.0)
    escalation_score: float = Field(ge=0.0, le=1.0)
    summary_score: float = Field(ge=0.0, le=1.0)
    penalty: float = Field(ge=0.0, le=1.0, description="Penalty subtracted from total")
    feedback: str = ""


# ── State ──────────────────────────────────────────────────────────────────────

class EnvironmentState(BaseModel):
    task_id: str
    step: int
    done: bool
    last_action: Optional[Action] = None
    last_reward: Optional[Reward] = None
    episode_rewards: list[float] = Field(default_factory=list)