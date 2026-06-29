import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.chat_service import ConversationStore

@pytest.mark.asyncio
async def test_conversation_store_trims_old_messages() -> None:
    store = ConversationStore(max_messages=2)

    await store.append("session-1", [HumanMessage(content="one")])
    await store.append("session-1", [AIMessage(content="two")])
    history = await store.append("session-1", [HumanMessage(content="three")])

    assert len(history) == 2
    assert history[0].content == "two"
    assert history[1].content == "three"
