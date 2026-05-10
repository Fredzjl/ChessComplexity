"""Very small smoke checks for the scaffold."""

from src.pipelines.full_test import build_run_plan


def test_build_run_plan_contains_expected_steps() -> None:
    plan = build_run_plan()
    assert plan["step_01"] == "download_lichess_games"
    assert plan["step_08"] == "write_run_summary"
