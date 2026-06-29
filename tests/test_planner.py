"""
Tests for the Planner module.

Tests goal decomposition logic, including:
- Successful plan generation (mocked LLM)
- Fallback plan when no API key is configured
- JSON parsing edge cases
"""

import pytest
from unittest.mock import patch, MagicMock
from src.orchestrator.planner import Planner, ExecutionPlan, Task


class TestPlannerFallback:
    """Test the planner when no LLM is available."""

    def test_fallback_plan_returns_single_task(self):
        """When the LLM is not available, planner should return a fallback plan."""
        with patch("src.orchestrator.planner.LLMClient") as mock_llm_client_cls:
            mock_llm = mock_llm_client_cls.get_instance.return_value
            mock_llm.available = False
            planner = Planner()
            plan = planner.decompose_goal("Test goal")

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.tasks) == 1
        assert plan.tasks[0].agent_type == "research"
        assert plan.goal == "Test goal"

    def test_fallback_plan_preserves_goal(self):
        """Fallback plan should preserve the original goal text."""
        with patch("src.orchestrator.planner.LLMClient") as mock_llm_client_cls:
            mock_llm = mock_llm_client_cls.get_instance.return_value
            mock_llm.available = False
            planner = Planner()
            goal = "Research 50 startups in the AI space"
            plan = planner.decompose_goal(goal)

        assert plan.goal == goal
        assert plan.tasks[0].parameters.get("raw_goal") == goal


class TestPlanParsing:
    """Test plan parsing from JSON data."""

    def test_parse_valid_plan(self):
        """Planner should correctly parse a well-formed JSON plan."""
        with patch("src.orchestrator.planner.LLMClient") as mock_llm_client_cls:
            mock_llm = mock_llm_client_cls.get_instance.return_value
            mock_llm.available = False
            planner = Planner()

        plan_data = {
            "summary": "Research and report on AI startups",
            "tasks": [
                {
                    "id": "task_1",
                    "description": "Search for AI startups",
                    "agent_type": "research",
                    "depends_on": [],
                    "parameters": {"search_query": "AI startups 2025"},
                },
                {
                    "id": "task_2",
                    "description": "Compile report",
                    "agent_type": "desktop",
                    "depends_on": ["task_1"],
                    "parameters": {"output_file": "report.txt"},
                },
            ],
        }

        plan = planner._parse_plan("Test goal", plan_data)

        assert plan.summary == "Research and report on AI startups"
        assert len(plan.tasks) == 2
        assert plan.tasks[0].id == "task_1"
        assert plan.tasks[1].depends_on == ["task_1"]

    def test_parse_empty_tasks(self):
        """Planner should handle empty task lists gracefully by returning a fallback plan."""
        with patch("src.orchestrator.planner.LLMClient") as mock_llm_client_cls:
            mock_llm = mock_llm_client_cls.get_instance.return_value
            mock_llm.available = False
            planner = Planner()

        plan = planner._parse_plan("Test", {"summary": "Empty", "tasks": []})
        assert len(plan.tasks) == 1
        assert plan.tasks[0].agent_type == "research"


class TestTaskModel:
    """Test the Task data model."""

    def test_task_defaults(self):
        task = Task(id="t1", description="Do something", agent_type="research")
        assert task.status == "pending"
        assert task.depends_on == []
        assert task.parameters == {}
        assert task.result == {}
