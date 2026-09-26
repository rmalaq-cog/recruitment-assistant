from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.app.config import Settings


class RecruitmentCrewFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.config_dir = Path(__file__).parent / "config"

    def load_config(self) -> tuple[dict[str, Any], dict[str, Any]]:
        with (self.config_dir / "agents.yaml").open(encoding="utf-8") as agents_file:
            agents_config = yaml.safe_load(agents_file) or {}
        with (self.config_dir / "tasks.yaml").open(encoding="utf-8") as tasks_file:
            tasks_config = yaml.safe_load(tasks_file) or {}
        return agents_config, tasks_config

    def validate_config(self) -> list[str]:
        agents_config, tasks_config = self.load_config()
        errors: list[str] = []
        for agent_id in ("researcher", "evaluator", "recommender"):
            if agent_id not in agents_config:
                errors.append(f"Missing CrewAI agent config: {agent_id}")
        for task_id in ("research_candidates", "evaluate_candidates", "recommend_shortlist"):
            task_config = tasks_config.get(task_id)
            if not task_config:
                errors.append(f"Missing CrewAI task config: {task_id}")
                continue
            if "expected_output" not in task_config:
                errors.append(f"Missing expected_output for task: {task_id}")
        return errors

    def build(self) -> Any:
        from crewai import Agent, Crew, Process, Task

        agents_config, tasks_config = self.load_config()
        researcher = Agent(config=agents_config["researcher"], verbose=False)
        evaluator = Agent(config=agents_config["evaluator"], verbose=False)
        recommender = Agent(config=agents_config["recommender"], verbose=False)

        research_task = Task(config=tasks_config["research_candidates"], agent=researcher)
        evaluation_task = Task(config=tasks_config["evaluate_candidates"], agent=evaluator, context=[research_task])
        recommendation_task = Task(
            config=tasks_config["recommend_shortlist"],
            agent=recommender,
            context=[research_task, evaluation_task],
        )

        return Crew(
            agents=[researcher, evaluator, recommender],
            tasks=[research_task, evaluation_task, recommendation_task],
            process=Process.sequential,
            memory=False,
            max_rpm=self.settings.crewai_max_rpm,
            verbose=False,
        )