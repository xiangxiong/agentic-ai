from __future__ import annotations
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_BACKEND_DIR / "reflection" / ".env")

from app.main import app

@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app)

def _make_completion(*, content: str | None = None, tool_calls: list[MagicMock] | None = None) -> MagicMock:
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response

def _make_tool_call(name: str, arguments: dict) -> MagicMock:
    import json

    function = MagicMock(spec=["name", "arguments"])
    function.name = name
    function.arguments = json.dumps(arguments)

    tool_call = MagicMock()
    tool_call.function = function
    return tool_call


class TestCopilotChatValidation:
    def test_missing_user_input_returns_422(self, api_client: TestClient) -> None:
        response = api_client.post("/api/copilot/chat", json={})

        assert response.status_code == 422

    def test_wrong_field_name_returns_422(self, api_client: TestClient) -> None:
        response = api_client.post("/api/copilot/chat", json={"message": "你好"})

        assert response.status_code == 422


class TestCopilotChatWithMockedLlm:
    @patch("app.main.client.chat.completions.create")
    def test_text_reply(self, mock_create: MagicMock, api_client: TestClient) -> None:
        mock_create.return_value = _make_completion(content="您好，有什么可以帮助您的吗？")

        response = api_client.post("/api/copilot/chat", json={"user_input": "你好"})

        assert response.status_code == 200
        assert response.json() == {
            "type": "TEXT",
            "decision": "REPLY",
            "response": "您好，有什么可以帮助您的吗？",
        }

    @patch("app.main.client.chat.completions.create")
    def test_fetch_order_status_executed(
        self, mock_create: MagicMock, api_client: TestClient
    ) -> None:
        mock_create.return_value = _make_completion(
            tool_calls=[_make_tool_call("fetch_order_status", {"order_id": "12345678"})]
        )

        response = api_client.post(
            "/api/copilot/chat",
            json={"user_input": "帮我查一下订单12345678的物流状态"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "TOOL_CALL"
        assert body["decision"] == "EXECUTED"
        assert body["tool_name"] == "fetch_order_status"
        assert body["arguments"] == {"order_id": "12345678"}
        assert "12345678" in body["content"]

    @patch("app.main.client.chat.completions.create")
    def test_apply_refund_executed_under_limit(
        self, mock_create: MagicMock, api_client: TestClient
    ) -> None:
        mock_create.return_value = _make_completion(
            tool_calls=[_make_tool_call("apply_refund", {"order_id": "12345678", "amount": 50})]
        )

        response = api_client.post(
            "/api/copilot/chat",
            json={"user_input": "客户要求对订单12345678退款50元，我同意退款"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["decision"] == "EXECUTED"
        assert body["tool_name"] == "apply_refund"
        assert body["arguments"]["amount"] == 50
        assert "50" in body["content"]

    @patch("app.main.client.chat.completions.create")
    def test_apply_refund_intercepted_over_limit(
        self, mock_create: MagicMock, api_client: TestClient
    ) -> None:
        mock_create.return_value = _make_completion(
            tool_calls=[_make_tool_call("apply_refund", {"order_id": "12345678", "amount": 200})]
        )

        response = api_client.post(
            "/api/copilot/chat",
            json={"user_input": "客户要求对订单12345678退款200元，我同意退款"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "TOOL_CALL"
        assert body["decision"] == "INTERCEPTED"
        assert body["tool_name"] == "apply_refund"
        assert body["arguments"]["amount"] == 200
        assert "100元" in body["reason"]

    @patch("app.main.client.chat.completions.create")
    def test_apply_refund_boundary_100_executed(
        self, mock_create: MagicMock, api_client: TestClient
    ) -> None:
        mock_create.return_value = _make_completion(
            tool_calls=[_make_tool_call("apply_refund", {"order_id": "12345678", "amount": 100})]
        )

        response = api_client.post(
            "/api/copilot/chat",
            json={"user_input": "客户要求对订单12345678退款100元，我同意退款"},
        )

        assert response.status_code == 200
        assert response.json()["decision"] == "EXECUTED"

    @patch("app.main.client.chat.completions.create")
    def test_apply_refund_boundary_101_intercepted(
        self, mock_create: MagicMock, api_client: TestClient
    ) -> None:
        mock_create.return_value = _make_completion(
            tool_calls=[_make_tool_call("apply_refund", {"order_id": "12345678", "amount": 101})]
        )

        response = api_client.post(
            "/api/copilot/chat",
            json={"user_input": "客户要求对订单12345678退款101元，我同意退款"},
        )

        assert response.status_code == 200
        assert response.json()["decision"] == "INTERCEPTED"

    @patch("app.main.client.chat.completions.create")
    def test_llm_error_returns_500(self, mock_create: MagicMock, api_client: TestClient) -> None:
        mock_create.side_effect = RuntimeError("API unavailable")

        response = api_client.post("/api/copilot/chat", json={"user_input": "你好"})

        assert response.status_code == 500
        assert "API unavailable" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("ZHIPU_API_KEY"), reason="ZHIPU_API_KEY is not set")
class TestCopilotChatIntegration:
    """Live tests against Zhipu. Run with: pytest -m integration tests/test_copilot_chat.py"""

    def test_live_greeting(self, api_client: TestClient) -> None:
        response = api_client.post("/api/copilot/chat", json={"user_input": "你好"})
        assert response.status_code == 200
        assert response.json()["type"] == "TEXT"
        assert response.json()["decision"] == "REPLY"

    def test_live_fetch_order_status(self, api_client: TestClient) -> None:
        response = api_client.post(
            "/api/copilot/chat",
            json={"user_input": "帮我查一下订单12345678的物流状态"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "TOOL_CALL"
        assert body["tool_name"] == "fetch_order_status"
        assert body["decision"] == "EXECUTED"

    def test_live_refund_intercepted(self, api_client: TestClient) -> None:
        response = api_client.post(
            "/api/copilot/chat",
            json={"user_input": "客户要求对订单12345678退款200元，我同意退款"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "TOOL_CALL"
        assert body["tool_name"] == "apply_refund"
        assert body["decision"] == "INTERCEPTED"
