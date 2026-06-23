from __future__ import annotations

from typing import Any, Optional


def params_match(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    if set(actual.keys()) != set(expected.keys()):
        return False

    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if key == "query":
            if not isinstance(actual_value, str) or not actual_value.strip():
                return False
            continue
        if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
            if float(expected_value) != float(actual_value):
                return False
        elif actual_value != expected_value:
            return False
    return True


def classify_routing_error(
    *,
    tool_match: bool,
    params_match_result: bool,
) -> Optional[str]:
    if tool_match and params_match_result:
        return None
    if not tool_match:
        return "Reasoning Error"
    return "Extraction Error"


def evaluate_tool_selection(
    *,
    prediction: dict[str, Any],
    reference: dict[str, Any],
) -> dict[str, Any]:
    expected_tool = reference.get("expected_tool")
    actual_tool = prediction.get("tool_name")
    tool_match = actual_tool == expected_tool
    score = 1 if tool_match else 0

    return {
        "key": "tool_accuracy",
        "score": score,
        "comment": (
            f"expected={expected_tool!r}, actual={actual_tool!r}"
            if not tool_match
            else "tool matched"
        ),
    }


def evaluate_param_extraction(
    *,
    prediction: dict[str, Any],
    reference: dict[str, Any],
) -> dict[str, Any]:
    expected_tool = reference.get("expected_tool")
    actual_tool = prediction.get("tool_name")
    expected_params = reference.get("expected_params") or {}
    actual_params = prediction.get("tool_params") or {}

    if expected_tool is None:
        score = 1 if actual_tool is None else 0
        return {
            "key": "param_accuracy",
            "score": score,
            "comment": "no tool expected" if score else f"unexpected tool: {actual_tool!r}",
        }

    if actual_tool != expected_tool:
        return {
            "key": "param_accuracy",
            "score": 0,
            "comment": "skipped because tool selection mismatched",
        }

    matched = params_match(actual_params, expected_params)
    return {
        "key": "param_accuracy",
        "score": 1 if matched else 0,
        "comment": (
            f"expected={expected_params!r}, actual={actual_params!r}"
            if not matched
            else "params matched"
        ),
    }


def evaluate_routing_pass(
    *,
    prediction: dict[str, Any],
    reference: dict[str, Any],
) -> dict[str, Any]:
    tool_result = evaluate_tool_selection(prediction=prediction, reference=reference)
    param_result = evaluate_param_extraction(prediction=prediction, reference=reference)
    passed = tool_result["score"] == 1 and param_result["score"] == 1
    error_type = classify_routing_error(
        tool_match=tool_result["score"] == 1,
        params_match_result=param_result["score"] == 1,
    )

    return {
        "key": "routing_pass",
        "score": 1 if passed else 0,
        "comment": "passed" if passed else error_type,
    }


def langsmith_tool_selection_evaluator(run: Any, example: Any) -> dict[str, Any]:
    return evaluate_tool_selection(
        prediction=run.outputs or {},
        reference=example.outputs or {},
    )


def langsmith_param_extraction_evaluator(run: Any, example: Any) -> dict[str, Any]:
    return evaluate_param_extraction(
        prediction=run.outputs or {},
        reference=example.outputs or {},
    )


def langsmith_routing_pass_evaluator(run: Any, example: Any) -> dict[str, Any]:
    return evaluate_routing_pass(
        prediction=run.outputs or {},
        reference=example.outputs or {},
    )
