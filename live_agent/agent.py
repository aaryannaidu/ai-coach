from google.adk.agents import Agent
from .prompts.system_prompt import (
    build_interview_instruction,
    build_pitch_instruction,
    GENERAL_INTERVIEW_PROMPT,
    STARTUP_PITCH_PROMPT,
)

# ---------------------------------------------------------------
# Model
# gemini-2.5-flash-native-audio: Live API, bidirectional audio streaming.
# Used for both interview agents — real-time voice conversation.
# ---------------------------------------------------------------
MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"


# ---------------------------------------------------------------
# Factory functions
#
# In production, the backend calls these at session start,
# passing in the context the user filled in on the frontend
# (role, CV, JD, startup name, pitch mode, etc.).
#
# The context is injected into the system prompt so the agent
# is fully informed from the very first word — no warm-up Q&A needed.
# ---------------------------------------------------------------

def create_interview_agent(
    role: str = "",
    company: str = "",
    interview_type: str = "Behavioural",
    cv_text: str = "",
    job_description: str = "",
) -> Agent:
    """
    Create a General Interview Agent with user context baked in.
    Call this at session start from the session management layer.
    """
    return Agent(
        name="general_interview_agent",
        model=MODEL,
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
    )


def create_pitch_agent(
    startup_name: str = "",
    one_liner: str = "",
    mode: str = "Full Investor Q&A",
    focus_areas: str = "",
    pitch_deck_text: str = "",
) -> Agent:
    """
    Create a Startup Pitch Agent with founder context baked in.
    Call this at session start from the session management layer.
    """
    return Agent(
        name="startup_pitch_agent",
        model=MODEL,
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
    model=MODEL,
    description=(
        "InterviewAI — a real-time voice interview coach. "
        "Supports General Interview mode (mock job interviews) and "
        "Startup Pitch mode (investor pitch practice). "
        "Swap root_agent assignment to test each mode locally."
    ),
    instruction=STARTUP_PITCH_PROMPT,  # Default to interview mode for local dev
)
