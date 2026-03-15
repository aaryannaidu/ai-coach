"""
Level 1 — Unit tests for session_tools.

Tests log_qa_pair and get_session_context with a mocked ToolContext.
No API key needed. Runs in < 1 second.

Run:
    cd backend && PYTHONPATH=. .venv/bin/python -m pytest tests/test_tools.py -v
"""

from unittest.mock import MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from live_agent.tools.session_tools import log_qa_pair, get_session_context


# ------------------------------------------------------------------ #
# helpers                                                             #
# ------------------------------------------------------------------ #

def make_ctx(initial_state: dict = None) -> MagicMock:
    """Return a minimal fake ToolContext backed by a real dict."""
    ctx = MagicMock()
    ctx.state = initial_state if initial_state is not None else {}
    return ctx


# ------------------------------------------------------------------ #
# log_qa_pair tests                                                   #
# ------------------------------------------------------------------ #

def test_log_first_qa():
    ctx = make_ctx()
    result = log_qa_pair("Tell me about yourself.", "Worked at Google for 3 years.", "solid, lacked depth", ctx)

    assert "Q1" in result
    assert len(ctx.state["qa_history"]) == 1
    entry = ctx.state["qa_history"][0]
    assert entry["q_number"] == 1
    assert entry["question"] == "Tell me about yourself."
    assert entry["answer_summary"] == "Worked at Google for 3 years."
    assert entry["notes"] == "solid, lacked depth"


def test_log_multiple_qa_pairs_accumulate():
    ctx = make_ctx()

    log_qa_pair("Question 1?", "Answer 1.", "note 1", ctx)
    log_qa_pair("Question 2?", "Answer 2.", "note 2", ctx)
    result = log_qa_pair("Question 3?", "Answer 3.", "note 3", ctx)

    assert "Q3" in result
    assert "3 questions recorded" in result
    assert len(ctx.state["qa_history"]) == 3
    assert ctx.state["qa_history"][2]["q_number"] == 3


def test_log_qa_returns_correct_count_string():
    ctx = make_ctx()
    log_qa_pair("Q1?", "A1.", "n1", ctx)
    result = log_qa_pair("Q2?", "A2.", "n2", ctx)
    assert "2 questions" in result


def test_log_qa_preserves_existing_history():
    """Verify that pre-existing history is not overwritten."""
    existing = [{"q_number": 1, "question": "Old Q", "answer_summary": "Old A", "notes": "old"}]
    ctx = make_ctx(initial_state={"qa_history": existing})

    log_qa_pair("New Q", "New A", "new note", ctx)

    assert len(ctx.state["qa_history"]) == 2
    assert ctx.state["qa_history"][0]["question"] == "Old Q"
    assert ctx.state["qa_history"][1]["question"] == "New Q"


# ------------------------------------------------------------------ #
# get_session_context tests                                           #
# ------------------------------------------------------------------ #

def test_get_session_context_empty_state():
    ctx = make_ctx()
    context = get_session_context(ctx)

    assert context["mode"] == "General Interview"   # default
    assert context["user_context"] == {}
    assert context["qa_history"] == []
    assert context["total_questions"] == 0


def test_get_session_context_with_data():
    ctx = make_ctx(initial_state={
        "mode": "Startup Pitch",
        "user_context": {"startup_name": "Acme", "one_liner": "We sell rockets"},
        "qa_history": [
            {"q_number": 1, "question": "What's the market size?", "answer_summary": "$1B TAM", "notes": "good numbers"},
        ],
    })
    context = get_session_context(ctx)

    assert context["mode"] == "Startup Pitch"
    assert context["user_context"]["startup_name"] == "Acme"
    assert context["total_questions"] == 1
    assert context["qa_history"][0]["question"] == "What's the market size?"


def test_get_session_context_total_questions_matches_history():
    ctx = make_ctx()
    for i in range(5):
        log_qa_pair(f"Q{i+1}?", f"A{i+1}.", f"note {i+1}", ctx)

    context = get_session_context(ctx)
    assert context["total_questions"] == 5
    assert len(context["qa_history"]) == 5


# ------------------------------------------------------------------ #
# round-trip test                                                     #
# ------------------------------------------------------------------ #

def test_full_roundtrip():
    """Log 3 Q&A pairs then retrieve and validate the full context."""
    ctx = make_ctx(initial_state={
        "mode": "General Interview",
        "user_context": {"role": "Product Manager", "company": "Google"},
    })

    log_qa_pair("Tell me about yourself.", "5 years in PM at scale-ups.", "good overview, missing metrics", ctx)
    log_qa_pair("Biggest product failure?", "Launched feature nobody used — learned to validate first.", "honest, good insight", ctx)
    log_qa_pair("Where do you see yourself in 5 years?", "CPO of a growth-stage company.", "generic, but acceptable", ctx)

    context = get_session_context(ctx)

    assert context["total_questions"] == 3
    assert context["mode"] == "General Interview"
    assert context["user_context"]["role"] == "Product Manager"
    assert context["qa_history"][1]["answer_summary"] == "Launched feature nobody used — learned to validate first."

    print("\n✅ Full round-trip test passed:")
    import json
    print(json.dumps(context, indent=2))
