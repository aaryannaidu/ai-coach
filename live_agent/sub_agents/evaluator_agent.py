from google.adk.agents import Agent
from ..prompts.evaluator_prompt import EVALUATOR_PROMPT

evaluator_agent = Agent(
    name="evaluator_agent",
    model="gemini-2.5-flash",
    description=(
        "Scores all interview answers and generates a complete session report. "
        "Called once at the end of the session with the full Q&A history."
    ),
    instruction=EVALUATOR_PROMPT,
)
