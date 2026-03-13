from google.adk.tools import ToolContext

def log_qa_pair(
    question: str,
    answer_summary: str,
    notes: str,
    tool_context: ToolContext,
) -> str:
    """
    Called by the root agent after each Q&A exchange.
    Saves a structured record to session state.

    Args:
        question: The exact question the agent asked.
        answer_summary: 1-2 sentence summary of what the candidate said.
        notes: Root agent's internal quality notes (e.g. "good STAR structure, no numbers").
    """
    history = tool_context.state.get("qa_history", [])
    history.append({
        "q_number": len(history) + 1,
        "question": question,
        "answer_summary": answer_summary,
        "notes": notes,
    })
    tool_context.state["qa_history"] = history
    return f"Logged Q{len(history)}. {len(history)} questions recorded so far."


def get_session_context(tool_context: ToolContext) -> dict:
    """
    Called by the root agent just before delegating to the evaluator.
    Returns everything the evaluator needs.
    """
    return {
        "mode": tool_context.state.get("mode", "General Interview"),
        "user_context": tool_context.state.get("user_context", {}),
        "qa_history": tool_context.state.get("qa_history", []),
        "total_questions": len(tool_context.state.get("qa_history", [])),
    }
