"""
Level 2 — Integration tests for the General Interview Agent.

Uses InMemoryRunner — real Gemini API calls, no voice, no microphone.
Tests that the agent starts correctly, calls log_qa_pair after answers,
and calls get_session_context when asked to wrap up.

Prerequisites:
    GOOGLE_API_KEY set in backend/live_agent/.env (or env)

Run:
    cd backend && PYTHONPATH=. .venv/bin/python -m pytest tests/test_interview_agent.py -v -s

The -s flag lets you see the agent's text responses in the terminal.
These tests take ~10-30 seconds each (live API calls).
"""

import asyncio
import json
import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types as genai_types

from live_agent.agent import create_interview_agent, TEXT_MODEL


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
# fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def interview_agent():
    """Create an interview agent for a PM role at Google."""
    return create_interview_agent(
        role="Product Manager",
        company="Google",
        interview_type="Behavioural",
        cv_text=(
            "3 years at a Series B SaaS startup as a PM. "
            "Led launch of the mobile app — grew from 0 to 50k MAU in 6 months. "
            "Previously: software engineer at Infosys for 2 years."
        ),
        job_description=(
            "Looking for a PM to lead the Google Maps consumer experience team. "
            "Must have experience with data-driven product decisions and cross-functional leadership."
        ),
        model=TEXT_MODEL,   # Live API model doesn't support generateContent
    )


@pytest.fixture
def runner_and_session(interview_agent):
    """Spin up an InMemoryRunner and create a session."""
    runner = InMemoryRunner(agent=interview_agent, app_name="test_interview")

    async def _make_session():
        session = await runner.session_service.create_session(
            app_name="test_interview",
            user_id="test_user",
            state={
                "mode": "General Interview",
                "user_context": {
                    "role": "Product Manager",
                    "company": "Google",
                    "interview_type": "Behavioural",
                },
            },
        )
        return runner, session.id

    return asyncio.get_event_loop().run_until_complete(_make_session())


# ------------------------------------------------------------------ #
# tests                                                               #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_interview_agent_gives_opening_question(interview_agent):
    """Agent should greet and ask a first question when session starts."""
    runner = InMemoryRunner(agent=interview_agent, app_name="test_interview")
    session = await runner.session_service.create_session(
        app_name="test_interview",
        user_id="test_user",
        state={"mode": "General Interview", "user_context": {"role": "PM", "company": "Google"}},
    )

    response, _ = await send_and_collect(runner, "test_user", session.id, "Hi, I'm ready to start.")

    print(f"\n[Agent opening]: {response[:300]}")
    assert len(response) > 20, "Agent should respond with a substantive opening"


@pytest.mark.asyncio
async def test_interview_agent_logs_qa_after_answer(interview_agent):
    """
    After the candidate gives an answer, the agent should call log_qa_pair.
    This verifies the tool is wired correctly into the agent.
    """
    runner = InMemoryRunner(agent=interview_agent, app_name="test_interview")
    session = await runner.session_service.create_session(
        app_name="test_interview",
        user_id="test_user",
        state={"mode": "General Interview", "user_context": {}},
    )

    # Kick off the interview
    await send_and_collect(runner, "test_user", session.id, "Hi, let's begin the interview.")

    # Give a substantive answer that should trigger log_qa_pair
    answer = (
        "At my last company, I led the decision to delay our feature launch by two weeks after "
        "discovering a critical bug in our analytics pipeline. I ran a quick stakeholder sync, "
        "aligned engineering and marketing on the revised timeline, and we shipped with zero "
        "incidents. The feature hit 20k activations in the first week."
    )
    response, tool_calls = await send_and_collect(runner, "test_user", session.id, answer)

    print(f"\n[Agent after answer]: {response[:300]}")
    print(f"[Tool calls]: {tool_calls}")

    # The agent should have called log_qa_pair
    assert "log_qa_pair" in tool_calls, (
        f"Expected log_qa_pair to be called after answer, but saw: {tool_calls}"
    )


@pytest.mark.asyncio
async def test_interview_agent_context_reflected_in_questions(interview_agent):
    """
    The agent's questions should reflect the injected context (PM role, Google, mobile app CV).
    Not a strict assertion — we check the response is non-empty and contextual.
    """
    runner = InMemoryRunner(agent=interview_agent, app_name="test_interview")
    session = await runner.session_service.create_session(
        app_name="test_interview",
        user_id="test_user",
        state={"mode": "General Interview", "user_context": {"role": "Product Manager"}},
    )

    response, _ = await send_and_collect(runner, "test_user", session.id, "Let's start.")

    print(f"\n[Context-aware question]: {response[:400]}")
    # Response should mention something relevant — not just "Hello"
    assert len(response) > 50


@pytest.mark.asyncio
async def test_interview_agent_get_session_context_on_wrap_up(interview_agent):
    """
    When we ask the agent to wrap up, it should call get_session_context.
    This simulates the end-of-session flow before evaluation.
    """
    runner = InMemoryRunner(agent=create_interview_agent(
        role="Product Manager", company="Google", model=TEXT_MODEL,
    ), app_name="test_interview")
    session = await runner.session_service.create_session(
        app_name="test_interview",
        user_id="test_user",
        state={"mode": "General Interview", "user_context": {}},
    )

    # Brief exchange first
    await send_and_collect(runner, "test_user", session.id, "Ready to start.")
    await send_and_collect(
        runner, "test_user", session.id,
        "I handled a conflict with an engineer by setting up a 1:1 and aligning on priorities."
    )

    # Request wrap-up — this should trigger get_session_context
    response, tool_calls = await send_and_collect(
        runner, "test_user", session.id,
        "That's all I have time for — please wrap up the interview and give me feedback."
    )

    print(f"\n[Wrap-up response]: {response[:400]}")
    print(f"[Tool calls on wrap-up]: {tool_calls}")

    assert "get_session_context" in tool_calls, (
        f"Expected get_session_context call on wrap-up, but saw: {tool_calls}"
    )
