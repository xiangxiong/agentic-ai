from __future__ import annotations

from app.evaluators import (
    evaluate_param_extraction,
    evaluate_routing_pass,
    evaluate_tool_selection,
    params_match,
)

class TestParamsMatch:
    def test_exact_match(self) -> None:
        assert params_match({"order_id": "987654"}, {"order_id": "987654"})

    def test_numeric_coercion(self) -> None:
        assert params_match({"amount": 200}, {"amount": 200.0})

    def test_key_mismatch(self) -> None:
        assert not params_match({"order_id": "987654"}, {"order_id": "987654", "amount": 200})

    def test_query_param_requires_non_empty_string(self) -> None:
        assert params_match({"query": "TikTok 退货运费规则"}, {"query": "expected paraphrase"})
        assert not params_match({"query": "  "}, {"query": "expected paraphrase"})


class TestEvaluateToolSelection:
    def test_pass(self) -> None:
        result = evaluate_tool_selection(
            prediction={"tool_name": "fetch_order_status", "tool_params": {"order_id": "1"}},
            reference={"expected_tool": "fetch_order_status", "expected_params": {"order_id": "1"}},
        )
        assert result["score"] == 1

    def test_fail(self) -> None:
        result = evaluate_tool_selection(
            prediction={"tool_name": "apply_refund", "tool_params": {}},
            reference={"expected_tool": "fetch_order_status", "expected_params": {"order_id": "1"}},
        )
        assert result["score"] == 0


class TestEvaluateParamExtraction:
    def test_no_tool_expected(self) -> None:
        result = evaluate_param_extraction(
            prediction={"tool_name": None, "tool_params": {}},
            reference={"expected_tool": None, "expected_params": {}},
        )
        assert result["score"] == 1

    def test_skip_when_tool_mismatch(self) -> None:
        result = evaluate_param_extraction(
            prediction={"tool_name": "apply_refund", "tool_params": {"amount": 200}},
            reference={"expected_tool": "fetch_order_status", "expected_params": {"order_id": "1"}},
        )
        assert result["score"] == 0

class TestEvaluateRoutingPass:
    def test_full_pass(self) -> None:
        result = evaluate_routing_pass(
            prediction={"tool_name": "apply_refund", "tool_params": {"order_id": "987654", "amount": 200}},
            reference={
                "expected_tool": "apply_refund",
                "expected_params": {"order_id": "987654", "amount": 200.0},
            },
        )
        assert result["score"] == 1

    def test_reasoning_error(self) -> None:
        result = evaluate_routing_pass(
            prediction={"tool_name": "apply_refund", "tool_params": {"order_id": "987654", "amount": 200}},
            reference={
                "expected_tool": "fetch_order_status",
                "expected_params": {"order_id": "987654"},
            },
        )
        assert result["score"] == 0
        assert result["comment"] == "Reasoning Error"
