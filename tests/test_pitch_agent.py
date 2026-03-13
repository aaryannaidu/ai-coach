"""
Level 2 — Integration tests for the Startup Pitch Agent.

Uses InMemoryRunner — real Gemini API calls, no voice, no microphone.
Tests both Elevator Pitch mode and Full Investor Q&A mode.

Prerequisites:
    GOOGLE_API_KEY set in backend/live_agent/.env (or env)

Run:
    cd backend && PYTHONPATH=. .venv/bin/python -m pytest tests/test_pitch_agent.py -v -s

The -s flag lets you see the agent's text responses in the terminal.
These tests take ~10-30 seconds each (live API calls).
"""

import asyncio
import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types as genai_types

from live_agent.agent import create_pitch_agent, TEXT_MODEL


# ------------------------------------------------------------------ #
# helpers                                                             #
# ------------------------------------------------------------------ #

def user_msg(text: str) -> genai_types.Content:
    return genai_types.Content(role="user", parts=[genai_types.Part(text=text)])


async def send_and_collect(runner, user_id, session_id, text: str) -> tuple[str, list]:
    """Send one user message, collect agent text and tool calls."""
    agent_text_parts = []
    tool_calls_seen = []

    result = runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg(text),
    )

    async for event in result:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    agent_text_parts.append(part.text)
                if hasattr(part, "function_call") and part.function_call:
                    tool_calls_seen.append(part.function_call.name)

    return "".join(agent_text_parts), tool_calls_seen


# ------------------------------------------------------------------ #
# Elevator Pitch Mode tests                                           #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_elevator_pitch_agent_listens_without_interrupting():
    """
    In Elevator Pitch mode, the agent should tell the user to go ahead
    and then wait. After the pitch, it should give structured feedback.
    """
    agent = create_pitch_agent(
        startup_name="SwiftRoute",
        one_liner="AI logistics platform that cuts last-mile delivery costs by 40%",
        mode="Elevator Pitch",
        focus_areas="problem clarity, market size, traction",
        model=TEXT_MODEL,
    )
    runner = InMemoryRunner(agent=agent, app_name="test_pitch")
    session = await runner.session_service.create_session(
        app_name="test_pitch",
        user_id="test_user",
        state={"mode": "Elevator Pitch", "user_context": {"startup_name": "SwiftRoute"}},
    )

    # First message — agent should invite the pitch, not ask questions
    response, _ = await send_and_collect(runner, "test_user", session.id, "I'm ready to pitch.")
    print(f"\n[Elevator Pitch opener]: {response[:300]}")
    assert len(response) > 10

    # Deliver the actual pitch
    pitch = (
        "SwiftRoute is an AI-powered logistics platform that reduces last-mile delivery costs "
        "by 40% for e-commerce companies. The problem: last-mile delivery accounts for 53% of "
        "total shipping costs, and most route optimisation tools are static. We use real-time "
        "traffic, weather, and demand signals to dynamically re-route drivers mid-shift. "
        "We're live with 3 mid-size e-commerce brands, processing 10,000 deliveries per day, "
        "and we've cut their delivery cost per order from $8.40 to $4.90. "
        "We're raising a $2M seed to expand to 20 enterprise customers in the next 12 months. "
        "That's my pitch."
    )
    response, tool_calls = await send_and_collect(runner, "test_user", session.id, pitch)
    print(f"\n[Elevator Pitch feedback]: {response[:500]}")
    print(f"[Tool calls]: {tool_calls}")

    # Agent should give substantive feedback after the pitch
    assert len(response) > 100, "Agent should give detailed feedback after the elevator pitch"

    # log_qa_pair may be called to record the pitch — that's fine
    # The key thing is the agent responds with feedback content


@pytest.mark.asyncio
async def test_elevator_pitch_logs_qa_pair():
    """
    After the pitch, agent should log it via log_qa_pair so the evaluator
    can score it at session end.
    """
    agent = create_pitch_agent(
        startup_name="NeuralDocs",
        one_liner="AI that auto-generates legal documents from plain English",
        mode="Elevator Pitch",
        model=TEXT_MODEL,
    )
    runner = InMemoryRunner(agent=agent, app_name="test_pitch")
    session = await runner.session_service.create_session(
        app_name="test_pitch",
        user_id="test_user",
        state={"mode": "Elevator Pitch", "user_context": {}},
    )

    await send_and_collect(runner, "test_user", session.id, "Ready to pitch.")

    pitch = (
        "NeuralDocs lets anyone generate contracts, NDAs, and legal agreements in seconds "
        "using plain English. Lawyers spend 60% of their time on routine document drafting. "
        "We use fine-tuned LLMs trained on 2 million legal documents. "
        "We have 200 paying customers at $99/month and are growing 30% month over month. "
        "We're raising $1.5M to hire 2 more engineers and expand enterprise sales. That's it."
    )
    response, tool_calls = await send_and_collect(runner, "test_user", session.id, pitch)

    print(f"\n[Feedback]: {response[:400]}")
    print(f"[Tool calls]: {tool_calls}")

    assert "log_qa_pair" in tool_calls, (
        f"Expected log_qa_pair after pitch delivery, saw: {tool_calls}"
    )


# ------------------------------------------------------------------ #
# Full Investor Q&A Mode tests                                        #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_investor_qa_agent_asks_probing_questions():
    """
    In Full Q&A mode, the agent should act as a VC and ask sharp questions.
    """
    agent = create_pitch_agent(
        startup_name="Ferment",
        one_liner="Subscription platform for independent craft brewers to sell direct-to-consumer",
        mode="Full Investor Q&A",
        focus_areas="market size, distribution moat, unit economics",
        model=TEXT_MODEL,
    )
    runner = InMemoryRunner(agent=agent, app_name="test_pitch")
    session = await runner.session_service.create_session(
        app_name="test_pitch",
        user_id="test_user",
        state={"mode": "Full Investor Q&A", "user_context": {"startup_name": "Ferment"}},
    )

    response, _ = await send_and_collect(
        runner, "test_user", session.id,
        "Hi, I'm Alex, founder of Ferment. We help craft brewers sell direct to consumers."
    )
    print(f"\n[VC opening question]: {response[:400]}")

    # Should ask a probing question, not just say hello
    assert len(response) > 30
    # The agent should be in VC mode — likely to ask about market, traction, or team


@pytest.mark.asyncio
async def test_investor_qa_logs_each_exchange():
    """
    After each Q&A exchange in Full mode, log_qa_pair should be called.
    """
    agent = create_pitch_agent(
        startup_name="Ferment",
        one_liner="D2C platform for craft brewers",
        mode="Full Investor Q&A",
        model=TEXT_MODEL,
    )
    runner = InMemoryRunner(agent=agent, app_name="test_pitch")
    session = await runner.session_service.create_session(
        app_name="test_pitch",
        user_id="test_user",
        state={"mode": "Full Investor Q&A", "user_context": {}},
    )

    # Opening
    await send_and_collect(runner, "test_user", session.id, "Hi, I'm pitching Ferment.")

    # Give a substantive answer to trigger tool call
    answer = (
        "The craft beer market is $30B in the US alone. There are 9,500 independent breweries, "
        "and 80% of them rely on distributor margins that eat 30-40% of revenue. "
        "We let them sell directly to consumers via a subscription box and local pickup, "
        "cutting out the middleman entirely. We have 45 breweries on the platform, "
        "averaging $2,400 MRR each."
    )
    response, tool_calls = await send_and_collect(runner, "test_user", session.id, answer)

    print(f"\n[VC response]: {response[:400]}")
    print(f"[Tool calls]: {tool_calls}")

    assert "log_qa_pair" in tool_calls, (
        f"Expected log_qa_pair after Q&A exchange, saw: {tool_calls}"
    )


@pytest.mark.asyncio
async def test_investor_qa_get_session_context_on_wrap_up():
    """
    When asked to wrap up, the agent should call get_session_context.
    """
    agent = create_pitch_agent(
        startup_name="Ferment",
        one_liner="D2C platform for craft brewers",
        mode="Full Investor Q&A",
        model=TEXT_MODEL,
    )
    runner = InMemoryRunner(agent=agent, app_name="test_pitch")
    session = await runner.session_service.create_session(
        app_name="test_pitch",
        user_id="test_user",
        state={"mode": "Full Investor Q&A", "user_context": {}},
    )

    # Short exchange
    await send_and_collect(runner, "test_user", session.id, "I'm pitching Ferment.")
    await send_and_collect(
        runner, "test_user", session.id,
        "We have 45 breweries paying $2,400/month on average. Growing 25% MoM."
    )

    # Trigger wrap-up
    response, tool_calls = await send_and_collect(
        runner, "test_user", session.id,
        "That's all the time I have — please give me your verdict and end the session."
    )

    print(f"\n[Verdict]: {response[:400]}")
    print(f"[Tool calls on wrap-up]: {tool_calls}")

    assert "get_session_context" in tool_calls, (
        f"Expected get_session_context on wrap-up, saw: {tool_calls}"
    )
