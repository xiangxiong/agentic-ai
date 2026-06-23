from __future__ import annotations

import time
from typing import Any, Callable, Optional

from langsmith import Client
from langsmith.evaluation import evaluate

from app.config import Settings, get_settings
from app.eval_dataset import (
    GOLDEN_DATASET,
    build_local_examples,
    sync_golden_dataset,
)
from app.evaluators import (
    classify_routing_error,
    evaluate_param_extraction,
    evaluate_routing_pass,
    evaluate_tool_selection,
    langsmith_param_extraction_evaluator,
    langsmith_routing_pass_evaluator,
    langsmith_tool_selection_evaluator,
)
from app.observability import configure_langsmith


class MissingLangSmithConfigError(RuntimeError):
    pass


def _require_langsmith_api_key(settings: Settings) -> str:
    api_key = settings.langsmith_api_key
    if not api_key:
        raise MissingLangSmithConfigError(
            "LANGCHAIN_API_KEY or LANGSMITH_API_KEY is required for LangSmith evaluation."
        )
    return api_key


def build_copilot_service(settings: Settings) -> Any:
    from app.rag_service_sop import get_sop_rag_service
    from app.services.copilot_service import CopilotService

    return CopilotService(settings, get_sop_rag_service(settings))


def make_routing_target(copilot: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def target(inputs: dict[str, Any]) -> dict[str, Any]:
        return copilot.route_intent(inputs["input"])

    return target


def sync_dataset(
    settings: Optional[Settings] = None,
    dataset_name: Optional[str] = None,
) -> str:
    settings = settings or get_settings()
    _require_langsmith_api_key(settings)
    client = Client(api_key=settings.langsmith_api_key)
    return sync_golden_dataset(
        client,
        dataset_name=dataset_name or settings.langsmith_eval_dataset,
    )


def run_langsmith_evaluation(
    *,
    settings: Optional[Settings] = None,
    dataset_name: Optional[str] = None,
    experiment_prefix: str = "copilot-routing",
    max_concurrency: int = 2,
    sync: bool = True,
) -> Any:
    settings = settings or get_settings()
    _require_langsmith_api_key(settings)
    configure_langsmith(settings)

    resolved_dataset = dataset_name or settings.langsmith_eval_dataset
    client = Client(api_key=settings.langsmith_api_key)
    if sync:
        sync_golden_dataset(client, dataset_name=resolved_dataset)

    copilot = build_copilot_service(settings)
    return evaluate(
        make_routing_target(copilot),
        data=resolved_dataset,
        evaluators=[
            langsmith_tool_selection_evaluator,
            langsmith_param_extraction_evaluator,
            langsmith_routing_pass_evaluator,
        ],
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
        client=client,
        metadata={
            "model": settings.zhipu_model,
            "dataset": resolved_dataset,
        },
    )


def run_local_evaluation(
    *,
    settings: Optional[Settings] = None,
    route_fn: Optional[Callable[[str], dict[str, Any]]] = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    if route_fn is None:
        route = build_copilot_service(settings).route_intent
    else:
        route = route_fn

    passed_cases = 0
    error_analysis_matrix: list[dict[str, Any]] = []
    case_results: list[dict[str, Any]] = []
    start_time = time.time()

    for case in GOLDEN_DATASET:
        prediction = route(case["input"])
        reference = {
            "expected_tool": case.get("expected_tool"),
            "expected_params": case.get("expected_params", {}),
        }
        tool_result = evaluate_tool_selection(prediction=prediction, reference=reference)
        param_result = evaluate_param_extraction(prediction=prediction, reference=reference)
        pass_result = evaluate_routing_pass(prediction=prediction, reference=reference)
        passed = pass_result["score"] == 1

        if passed:
            passed_cases += 1
        else:
            error_analysis_matrix.append(
                {
                    "case_id": case["id"],
                    "input": case["input"],
                    "error_type": classify_routing_error(
                        tool_match=tool_result["score"] == 1,
                        params_match_result=param_result["score"] == 1,
                    ),
                    "expected": {
                        "tool": reference["expected_tool"],
                        "params": reference["expected_params"],
                    },
                    "actual": prediction,
                }
            )

        case_results.append(
            {
                "case_id": case["id"],
                "input": case["input"],
                "passed": passed,
                "prediction": prediction,
                "tool_accuracy": tool_result["score"],
                "param_accuracy": param_result["score"],
            }
        )

    total_cases = len(GOLDEN_DATASET)
    accuracy = (passed_cases / total_cases) * 100 if total_cases else 0.0

    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "accuracy": accuracy,
        "elapsed_seconds": time.time() - start_time,
        "case_results": case_results,
        "error_analysis_matrix": error_analysis_matrix,
        "local_examples": build_local_examples(),
    }


def print_local_report(report: dict[str, Any]) -> None:
    print("开始执行 Copilot 工具路由评估...\n" + "=" * 50)

    for case in report["case_results"]:
        status = "PASSED" if case["passed"] else "FAILED"
        print(f"\n评估案例 {case['case_id']}: {case['input']}")
        print(f" 结果: {status}")
        print("-" * 50)

    print("\n" + "=" * 50)
    print("最终评估报告")
    print(f"   - 总测试用例数: {report['total_cases']}")
    print(f"   - 成功通过件数: {report['passed_cases']}")
    print(f"   - 工具路由准确率: {report['accuracy']:.2f}%")
    print(f"   - 评估总耗时: {report['elapsed_seconds']:.2f} 秒")
    print("=" * 50)

    if report["error_analysis_matrix"]:
        print("\n错误分析矩阵:")
        for err in report["error_analysis_matrix"]:
            print(f" [用例 {err['case_id']}] 错误类型: {err['error_type']}")
            print(f"    - 期望结果: {err['expected']}")
            print(f"    - 实际输出: {err['actual']}")
    else:
        print("\n所有用例全部通过。")
