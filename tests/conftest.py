"""
Shared fixtures for InterviewAI test suite.

All agent tests use InMemoryRunner so nothing hits the real Live API
(no microphone, no audio stream, no WebSocket required).

To run all tests:
    cd backend && PYTHONPATH=. .venv/bin/python -m pytest tests/ -v

To run a specific file:
    cd backend && PYTHONPATH=. .venv/bin/python -m pytest tests/test_interview_agent.py -v
"""

import os
import pytest
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from google.genai import types as genai_types

# ------------------------------------------------------------------ #
# Load .env from live_agent/.env before any tests run                #
# This makes GOOGLE_API_KEY available for InMemoryRunner agent tests  #
# ------------------------------------------------------------------ #
_env_path = Path(__file__).parent.parent / "live_agent" / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


# ------------------------------------------------------------------ #
# helper: wrap a plain text string into types.Content (user turn)     #
# ------------------------------------------------------------------ #
def user_msg(text: str) -> genai_types.Content:
    return genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=text)],
    )


# ------------------------------------------------------------------ #
# helper: extract all text parts from an async result stream          #
# ------------------------------------------------------------------ #
async def collect_text(result_stream) -> str:
    """Drain an async-iterable of ADK events and return combined agent text."""
    chunks = []
    async for event in result_stream:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    chunks.append(part.text)
    return "".join(chunks)


# ------------------------------------------------------------------ #
# Re-export these so test files can import from conftest              #
# ------------------------------------------------------------------ #
__all__ = ["user_msg", "collect_text"]
