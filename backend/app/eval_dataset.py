from __future__ import annotations
from typing import Any, Optional

GOLDEN_DATASET: list[dict[str, Any]] = [
    {
        "id": 1,
        "input": "帮我看看订单号 987654 现在的物流到哪了？",
        "expected_tool": "fetch_order_status",
        "expected_params": {"order_id": "987654"},
    },
    {
        "id": 2,
        "input": "客户不想要了，帮我把订单 987654 退款 200 元",
        "expected_tool": "apply_refund",
        "expected_params": {"order_id": "987654", "amount": 200.0},
    },
    {
        "id": 3,
        "input": "帮我查一下订单12345678的物流状态",
        "expected_tool": "fetch_order_status",
        "expected_params": {"order_id": "12345678"},
    },
    {
        "id": 4,
        "input": "TikTok 跨境小店因质量问题退货，运费谁承担？",
        "expected_tool": "query_sop_knowledge",
        "expected_params": {"query": "TikTok 跨境小店因质量问题退货运费谁承担"},
    },
    {
        "id": 5,
        "input": "去 Ozon 后台查一下订单 556677 的最新物流",
        "expected_tool": "call_shadowbot_fetch_logistics",
        "expected_params": {"order_id": "556677"},
    },
    {
        "id": 6,
        "input": "你好，今天天气怎么样？",
        "expected_tool": None,
        "expected_params": {},
    },
]

DATASET_NAME = "copilot-tool-routing-golden"
DATASET_DESCRIPTION = (
    "Copilot 工具路由黄金数据集：覆盖订单查询、退款、SOP 检索、"
    "ShadowBot 物流穿透与普通闲聊分支。"
)


def sync_golden_dataset(client: Any, dataset_name: str = DATASET_NAME) -> str:
    """Create or update the LangSmith dataset from GOLDEN_DATASET."""
    datasets = list(client.list_datasets(dataset_name=dataset_name))
    if datasets:
        dataset_id = datasets[0].id
    else:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description=DATASET_DESCRIPTION,
        )
        dataset_id = dataset.id

    existing_examples = list(client.list_examples(dataset_id=dataset_id))
    existing_by_case_id = {
        example.metadata.get("case_id"): example
        for example in existing_examples
        if example.metadata and example.metadata.get("case_id") is not None
    }

    for case in GOLDEN_DATASET:
        inputs = {"input": case["input"]}
        outputs = {
            "expected_tool": case.get("expected_tool"),
            "expected_params": case.get("expected_params", {}),
        }
        metadata = {"case_id": case["id"]}
        existing = existing_by_case_id.get(case["id"])
        if existing is not None:
            client.update_example(
                example_id=existing.id,
                inputs=inputs,
                outputs=outputs,
                metadata=metadata,
            )
        else:
            client.create_example(
                inputs=inputs,
                outputs=outputs,
                metadata=metadata,
                dataset_id=dataset_id,
            )

    return dataset_id

def build_local_examples() -> list[dict[str, Any]]:
    """Convert GOLDEN_DATASET into LangSmith-compatible example dicts."""
    examples: list[dict[str, Any]] = []
    for case in GOLDEN_DATASET:
        examples.append(
            {
                "inputs": {"input": case["input"]},
                "outputs": {
                    "expected_tool": case.get("expected_tool"),
                    "expected_params": case.get("expected_params", {}),
                },
                "metadata": {"case_id": case["id"]},
            }
        )
    return examples
