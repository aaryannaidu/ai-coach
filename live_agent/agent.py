from google.adk.agents import Agent

# ---------------------------------------------------------------
# Model: Gemini 2.5 Flash Live Preview
# This model supports the Live API (bidirectional audio streaming)
# and native function calling — perfect for our real-time coach.
# ---------------------------------------------------------------
MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

root_agent = Agent(
    name="pitch_coach_agent",
    model=MODEL,
    description=(
        "A real-time startup pitch coach that conducts mock investor interviews. "
        "Listens to the founder's pitch, asks probing follow-up questions, "
        "gives specific feedback, and helps them improve their pitch."
    ),
)
