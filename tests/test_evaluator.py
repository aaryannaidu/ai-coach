"""
Level 2 — Direct evaluator agent test.

Sends a mock Q&A session to the evaluator_agent and prints the JSON report.
Uses InMemoryRunner — no voice, no browser. Takes ~5 seconds.

Run:
    cd backend && .venv/bin/python tests/test_evaluator.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from pathlib import Path
from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types
from live_agent.sub_agents.evaluator_agent import evaluator_agent

# Load API key from live_agent/.env
load_dotenv(dotenv_path=Path(__file__).parent.parent / "live_agent" / ".env", override=False)

APP_NAME = "test_evaluator"

MOCK_SESSION = """
Mode: General Interview — Behavioural
Role: Product Manager at Google

Q1: Tell me about a time you made a tough product decision under pressure.
A1: At my last role, we had 2 days to decide whether to delay a feature or ship with known bugs.
    I ran a quick risk-impact matrix and chose to delay — retention mattered more than the deadline.
Notes: Strong, clear decision-making. Could have quantified retention impact.

Q2: Describe a time you had a conflict with an engineer.
A2: An engineer disagreed with my prioritisation. I listened to their concerns and adjusted the roadmap.
Notes: Too vague — didn't explain what the conflict actually was or how it resolved.

Q3: What's your biggest weakness as a PM?
A3: I sometimes over-communicate, which slows things down. I've been working on being more concise.
Notes: Generic answer — didn't give specifics or show self-awareness.
"""


async def test_evaluator():
    # app_name must be the same in InMemoryRunner() AND create_session()
    runner = InMemoryRunner(agent=evaluator_agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id="test",
    )

    # run_async is an async generator — do NOT await it, iterate with async for
    async for event in runner.run_async(
        user_id="test",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=MOCK_SESSION)],
        ),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    print(part.text)


asyncio.run(test_evaluator())
