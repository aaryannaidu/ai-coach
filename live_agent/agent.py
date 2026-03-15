from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.genai import types
from .tools.session_tools import log_qa_pair, get_session_context
from .prompts.system_prompt import (
    build_interview_instruction,
    build_pitch_instruction,
    GENERAL_INTERVIEW_PROMPT,
    STARTUP_PITCH_PROMPT,
)
from .sub_agents.evaluator_agent import evaluator_agent


# ---------------------------------------------------------------
# Session reset callback
#
# ADK reuses agent objects across sessions in adk web. Without
# this, qa_history and user_context from a previous session bleed
# into the next one. This callback fires at the very start of
# every new agent invocation and wipes those keys clean.
# ---------------------------------------------------------------

def _reset_session_state(callback_context: CallbackContext) -> None:
    """Clear session-scoped state at the start of every new turn.
    Fires before the LLM is called, so the agent always starts clean.
    Only resets on turn 1 (invocation_id == 0 in a fresh session).
    """
    state = callback_context.state
    # Reset only if this looks like a brand new session
    # (qa_history key absent OR session was just created)
    if "_session_initialised" not in state:
        state["qa_history"] = []
        state["mode"] = "Startup Pitch"
        state["user_context"] = {}
        state["_session_initialised"] = True

# ---------------------------------------------------------------
# Model
# gemini-2.5-flash-native-audio: Live API, bidirectional audio streaming.
# Used for both interview agents — real-time voice conversation.
# ---------------------------------------------------------------
MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

# Text model used in tests — Live API models don't support generateContent
# (the endpoint InMemoryRunner uses). Swap to this for automated testing.
TEXT_MODEL = "gemini-2.5-flash"


# ---------------------------------------------------------------
# Factory functions
#
# In production, the backend calls these at session start,
# passing in the context the user filled in on the frontend
# (role, CV, JD, startup name, pitch mode, etc.).
#
# The context is injected into the system prompt so the agent
# is fully informed from the very first word — no warm-up Q&A needed.
#
# Pass model=TEXT_MODEL (or any text model) in tests so InMemoryRunner
# can call generateContent. Live API models only work over WebSockets.
# ---------------------------------------------------------------

def create_interview_agent(
    role: str = "",
    company: str = "",
    interview_type: str = "Behavioural",
    cv_text: str = "",
    job_description: str = "",
    model: str = MODEL,
) -> Agent:
    """
    Create a General Interview Agent with user context baked in.
    Call this at session start from the session management layer.

    Args:
        model: Override the model. Use TEXT_MODEL in tests since Live API
               models (gemini-*-native-audio-*) do not support generateContent.
    """
    return Agent(
        name="general_interview_agent",
        model=model,
        description=(
            "A real-time AI interview coach for job seekers. "
            "Conducts realistic mock interviews tailored to the candidate's role, company, "
            "and interview type (Behavioural, Technical, or HR). Questions are informed by "
            "the candidate's CV and job description. Wraps up with honest, actionable feedback."
        ),
        instruction=build_interview_instruction(
            role=role,
            company=company,
            interview_type=interview_type,
            cv_text=cv_text,
            job_description=job_description,
        ),
        tools=[log_qa_pair, get_session_context],
        sub_agents=[evaluator_agent],
        before_agent_callback=_reset_session_state,
    )


def create_pitch_agent(
    startup_name: str = "",
    one_liner: str = "",
    mode: str = "Full Investor Q&A",
    focus_areas: str = "",
    pitch_deck_text: str = "",
    model: str = MODEL,
) -> Agent:
    """
    Create a Startup Pitch Agent with founder context baked in.
    Call this at session start from the session management layer.

    Args:
        model: Override the model. Use TEXT_MODEL in tests since Live API
               models (gemini-*-native-audio-*) do not support generateContent.
    """
    return Agent(
        name="startup_pitch_agent",
        model=model,
        description=(
            "A real-time AI pitch coach for startup founders. "
            "Supports Elevator Pitch mode (founder pitches uninterrupted → structured feedback) "
            "and Full Investor Q&A mode (sharp VC investor roleplay → probing questions → verdict). "
            "Tailored to the founder's startup and focus areas from the first word."
        ),
        instruction=build_pitch_instruction(
            startup_name=startup_name,
            one_liner=one_liner,
            mode=mode,
            focus_areas=focus_areas,
            pitch_deck_text=pitch_deck_text,
        ),
        tools=[log_qa_pair, get_session_context],
        sub_agents=[evaluator_agent],
        before_agent_callback=_reset_session_state,
    )


# ---------------------------------------------------------------
# root_agent — ADK requirement
#
# ADK web / adk run expects a module-level `root_agent` variable.
# For local testing we use base prompts (no context injected).
# In production, create_interview_agent() or create_pitch_agent()
# are called instead, with real user context from the frontend.
#
# To test a specific mode locally, swap the assignment below:
#   root_agent = create_interview_agent(role="Product Manager", company="Google")
#   root_agent = create_pitch_agent(startup_name="Acme", mode="Elevator Pitch")
# ---------------------------------------------------------------

root_agent = Agent(
    name="interview_ai",
    model=TEXT_MODEL,
    description=(
        "InterviewAI — a real-time voice interview coach. "
        "Supports General Interview mode (mock job interviews) and "
        "Startup Pitch mode (investor pitch practice). "
        "Swap root_agent assignment to test each mode locally."
    ),
    instruction=STARTUP_PITCH_PROMPT,  # Swap to GENERAL_INTERVIEW_PROMPT to test interview mode
    tools=[log_qa_pair, get_session_context],
    sub_agents=[evaluator_agent],
    before_agent_callback=_reset_session_state,
    generate_content_config=types.GenerateContentConfig(
        # Force the model to always evaluate whether to call a tool.
        # Without this, Gemini sometimes skips function calls entirely
        # when it thinks a plain text response is sufficient.
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="AUTO",
            )
        )
    ),
)
