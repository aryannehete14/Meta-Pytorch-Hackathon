from server.models import (
    Observation, Action, Reward, EnvironmentState, AlertSeverity
)
from server import TASKS
from typing import Optional
import copy


class IncidentResponseEnvironment:
    """
    OpenEnv-compliant environment for Incident Response Triage.
    Manages episode state across step() / reset() / state() calls.
    """

    MAX_STEPS = 5  # single-turn task; allows re-attempts

    def __init__(self):
        self._task_id: str = "task1_easy"
        self._step: int = 0
        self._done: bool = False
        self._last_action: Optional[Action] = None
        self._last_reward: Optional[Reward] = None
        self._episode_rewards: list[float] = []
        self._current_obs: Optional[Observation] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def reset(self, task_id: str = "task1_easy") -> Observation:
        if task_id not in TASKS:
            raise ValueError(f"Unknown task_id '{task_id}'. Available: {list(TASKS.keys())}")
        self._task_id = task_id
        self._step = 0
        self._done = False
        self._last_action = None
        self._last_reward = None
        self._episode_rewards = []
        self._current_obs = TASKS[task_id].get_initial_observation()
        return copy.deepcopy(self._current_obs)

    def step(self, action: Action) -> tuple[Observation, Reward, bool, dict]:
        if self._done:
            raise RuntimeError("Episode is done. Call reset() to start a new episode.")
        if self._current_obs is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")

        # Grade the action
        reward: Reward = TASKS[self._task_id].grade(action)
        self._last_action = action
        self._last_reward = reward
        self._episode_rewards.append(reward.total)
        self._step += 1

        # Episode ends after one action (single-turn triage task)
        # or if perfect score achieved
        self._done = True

        # Update observation with step count
        self._current_obs.step = self._step

        info = {
            "task_id": self._task_id,
            "step": self._step,
            "episode_reward_sum": sum(self._episode_rewards),
            "feedback": reward.feedback,
        }

        return copy.deepcopy(self._current_obs), reward, self._done, info

    def state(self) -> EnvironmentState:
        return EnvironmentState(
            task_id=self._task_id,
            step=self._step,
            done=self._done,
            last_action=self._last_action,
            last_reward=self._last_reward,
            episode_rewards=list(self._episode_rewards),
        )

    def list_tasks(self) -> list[dict]:
        return [
            {
                "task_id": "task1_easy",
                "difficulty": "easy",
                "description": "Single service outage — payment-service DB connection failure. Clear logs, 1 noise alert.",
            },
            {
                "task_id": "task2_medium",
                "difficulty": "medium",
                "description": "Cascading failure — auth-service down causes 2 downstream services to fail. Must identify upstream root cause.",
            },
            {
                "task_id": "task3_hard",
                "difficulty": "hard",
                "description": "Partial degradation — recommendation-service memory leak causes checkout latency. Subtle, no clear error, requires correlating 4+ signals.",
            },
        ]
