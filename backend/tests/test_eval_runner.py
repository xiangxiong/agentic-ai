from __future__ import annotations

from app.eval_dataset import GOLDEN_DATASET
from app.eval_runner import run_local_evaluation


def _mock_route(user_input: str) -> dict[str, object]:
    for case in GOLDEN_DATASET:
        if case["input"] == user_input:
            return {
                "tool_name": case.get("expected_tool"),
                "tool_params": case.get("expected_params", {}),
            }
    return {"tool_name": "unknown", "tool_params": {}}

class TestRunLocalEvaluation:
    def test_mocked_local_report(self) -> None:
        report = run_local_evaluation(route_fn=_mock_route)

        assert report["total_cases"] == len(GOLDEN_DATASET)
        assert report["passed_cases"] == len(GOLDEN_DATASET)
        assert report["accuracy"] == 100.0
        assert report["error_analysis_matrix"] == []

    def test_mocked_local_failures(self) -> None:
        def always_wrong(_: str) -> dict[str, object]:
            return {"tool_name": "unknown", "tool_params": {}}

        report = run_local_evaluation(route_fn=always_wrong)

        assert report["passed_cases"] == 0
        assert len(report["error_analysis_matrix"]) == report["total_cases"]
