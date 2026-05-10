"""Future orchestration for the first complete experiment."""


def build_run_plan() -> dict[str, str]:
    """Return the named steps of the full experiment."""
    return {
        "step_01": "download_lichess_games",
        "step_02": "install_or_verify_maia2",
        "step_03": "parse_games",
        "step_04": "filter_middlegame_positions",
        "step_05": "run_policy_inference",
        "step_06": "score_complexity",
        "step_07": "render_flagged_positions",
        "step_08": "write_run_summary",
    }
