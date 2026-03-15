# InterviewAI — Build Plan

> Last updated: 10 Mar 2026  
> Repo root: `backend/`  
> Run locally: `cd backend && adk web`

---

## What's Done ✅

| Item | Status |
|---|---|
| `live_agent/agent.py` — Interview + Pitch agent definitions + factory functions | ✅ Done |
| `live_agent/prompts/system_prompt.py` — Both system prompts + context injection helpers | ✅ Done |
| `.gitignore` — `.env`, `__pycache__`, `.adk/`, `.venv/` excluded | ✅ Done |
| `adk web` server boots and connects to Gemini Live API | ✅ Working |

---

## Architecture Overview

```
Root Agent (Interview or Pitch — Live Audio, gemini-2.5-flash-native-audio)
│
│   Runs the live voice conversation end-to-end.
│   Uses tools to log Q&A pairs into session state.
│   Delegates to sub-agents ONCE at session end only.
│
├── Tools (not agents — lightweight, no extra API calls)
│   ├── log_qa_pair(question, answer_summary, notes)
│   │   Called by root after every exchange. Saves to session state.
│   └── get_session_context()
│       Called by root before delegating to evaluator.
│
├── Evaluator Agent (gemini-2.5-flash, text)
│   Called ONCE at end of session.
│   Receives all Q&A pairs + session context.
│   Returns per-answer scores + full report JSON.
│   Replaces both the old scoring_agent AND feedback_agent.
│
└── Vision Agent (gemini-2.5-flash, multimodal) [OPTIONAL]
    Called ONCE at end of session (or per-answer if camera is enabled).
    Receives captured JPEG frames from the camera.
    Returns body language analysis.
```

### Why this is better than per-answer scoring

| Concern | Old Plan (4 agents) | This Plan (3 agents) |
|---|---|---|
| API calls per session | ~10–15 (scoring × 8 + feedback + vision) | 2–3 (evaluator + optional vision) |
| Conversation flow | Scoring agent pauses audio after each answer | Root agent flows uninterrupted |
| Context plumbing | Root shuttles JSON between 3 sub-agents | Tools write to session state, evaluator gets it all at once |
| Complexity | 4 agents, 4 prompts, tricky coordination | 3 agents, 3 prompts, clean linear flow |

### Data flow — how context moves through the session

```
SESSION START
  Frontend sends context (role, company, CV, mode, etc.)
  Backend calls create_interview_agent() or create_pitch_agent()
  Session state initialized: { mode, user_context, qa_history: [] }

CONVERSATION LOOP (5–8 rounds)
  1. Root agent asks a question (voice)
  2. User answers (voice → Live API auto-transcribes)
  3. Root agent:
      a. Gives brief verbal feedback ("That's clear — let me push deeper on X")
      b. Calls log_qa_pair(question, summary, notes) ← TOOL
      c. Moves to the next question

SESSION END
  1. Root agent: "Let me compile your results..."
  2. Calls get_session_context() ← TOOL — retrieves full Q&A history
  3. Delegates to evaluator_agent with the full context
  4. Evaluator returns structured JSON report
  5. Root agent speaks key highlights (overall score, top strength, top tip)
  6. Report JSON is sent to frontend for the /report page
```


---

## What's Next — Ordered Build Steps

---

### Step 1 — Session Tools `[DO THIS NEXT]`

**Files to create:**
- `live_agent/tools/__init__.py`
- `live_agent/tools/session_tools.py`

**Time estimate:** ~30 minutes

These are the two tools the root agent calls to maintain structured state during the conversation. They're plain Python functions — no extra API calls, no latency.

#### `tools/session_tools.py`

```python
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
```

#### Wire into root agent in `agent.py`

```python
from .tools.session_tools import log_qa_pair, get_session_context

root_agent = Agent(
    ...
    tools=[log_qa_pair, get_session_context],
)
```

#### How to test (no voice needed)

```bash
# Run this directly — no adk web, no microphone
.venv/bin/python tests/test_tools.py
```

```python
# tests/test_tools.py
from unittest.mock import MagicMock
from live_agent.tools.session_tools import log_qa_pair, get_session_context

def test_log_and_retrieve():
    ctx = MagicMock()
    ctx.state = {}

    result = log_qa_pair("Tell me about yourself.", "Worked at Google for 3 years.", "solid, lacked depth", ctx)
    assert "Q1" in result

    context = get_session_context(ctx)
    assert context["total_questions"] == 1
    assert context["qa_history"][0]["question"] == "Tell me about yourself."
    print("✅ Tools test passed:", context)

test_log_and_retrieve()
```

---

### Step 2 — Update Root Agent System Prompt

**Files to modify:** `live_agent/prompts/system_prompt.py`  
**Time estimate:** ~30 minutes

Add tool-calling instructions to both prompts so the root agent knows when and how to use its tools.

Add this section to both `GENERAL_INTERVIEW_PROMPT` and `STARTUP_PITCH_PROMPT`:

```
## Session Logging (IMPORTANT — do this after every answer)

You have two tools available: log_qa_pair and get_session_context.

After the user finishes each answer:
1. Give one brief verbal response (acknowledge + transition).
2. Immediately call log_qa_pair with:
   - question: the exact question you just asked
   - answer_summary: 1–2 sentence summary of what they said
   - notes: your honest internal assessment ("strong STAR, good numbers" / "vague, no specifics, deflected")
3. Move to the next question. Do not mention the tool call out loud.

## Ending the Session

After 5–8 questions:
1. Say: "That's all the questions — let me put together your results."
2. Call get_session_context to retrieve the full session history.
3. Delegate to the evaluator_agent — it will score everything and generate the report.
4. Once you receive the report back, speak only the highlights:
   - Your overall score and quick impression (1 sentence)
   - Your strongest moment with a specific example
   - The single biggest thing to fix, with concrete advice
   - Two preparation tips
5. Close warmly. The full written report will appear on screen.
```

#### How to test (no voice needed)

Use `adk web` text mode — just type messages instead of speaking. The trace panel shows tool calls:
- After each text message, you should see `log_qa_pair` appear in the trace
- When you type "end the session", you should see `get_session_context` in the trace

---

### Step 3 — Evaluator Agent

**Files to create:**
- `live_agent/sub_agents/__init__.py`
- `live_agent/sub_agents/evaluator_agent.py`
- `live_agent/prompts/evaluator_prompt.py`

**Time estimate:** ~1 hour

This replaces both the old `scoring_agent` and `feedback_agent`. Called once, scores everything, returns the full report.

#### `prompts/evaluator_prompt.py`

```python
EVALUATOR_EXAMPLE_PROMPT = """
You are a precise interview evaluation engine.

You will receive a complete session record containing:
- The interview mode and context (role, company, interview type, etc.)
- A numbered list of Q&A pairs with the interviewer's internal notes per answer

Your job: score every answer individually, then produce an overall session report.

Return ONLY valid JSON — no markdown, no explanation, just the JSON object.

Output format:
{
  "per_answer_scores": [
    {
      "q_number": 1,
      "relevance": <1-10>,
      "clarity": <1-10>,
      "depth": <1-10>,
      "overall": <weighted average, 1 decimal>,
      "note": "<one-sentence specific observation>"
    }
  ],
  "overall_score": <weighted average across all answers, 1 decimal>,
  "category_scores": {
    "communication": <1-10>,
    "content_quality": <1-10>,
    "structure": <1-10>
  },
  "summary": "<2 sentence honest overall impression>",
  "strongest_moment": "<specific Q number and why — be concrete>",
  "biggest_weakness": "<specific pattern observed — not generic advice>",
  "tips": [
    "<actionable tip 1 — specific to what you observed>",
    "<actionable tip 2>",
    "<actionable tip 3>"
  ]
}

Scoring rubric:
- relevance: Did the answer actually address what was asked?
- clarity: Was it easy to follow? Good structure (STAR, clear narrative)?
- depth: Did they go deep enough? Numbers, specifics, real examples?
- overall: Weighted — depth 40%, relevance 30%, clarity 30%
""".strip()
```

#### `sub_agents/evaluator_agent.py`

```python
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
```

#### Wire into root agent

```python
from .sub_agents.evaluator_agent import evaluator_agent

root_agent = Agent(
    ...
    tools=[log_qa_pair, get_session_context],
    sub_agents=[evaluator_agent],
)
```

#### How to test (no voice needed — direct agent call)

```python
# tests/test_evaluator.py
import asyncio
from google.adk.runners import InMemoryRunner
from live_agent.sub_agents.evaluator_agent import evaluator_agent

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
    runner = InMemoryRunner(agent=evaluator_agent)
    session = await runner.session_service.create_session(app_name="test", user_id="test")
    result = await runner.run_async(
        user_id="test",
        session_id=session.id,
        new_message=MOCK_SESSION,
    )
    for event in result:
        if event.content:
            print(event.content.parts[0].text)

asyncio.run(test_evaluator())
```

Run it:
```bash
cd backend && .venv/bin/python tests/test_evaluator.py
```

You'll get a full JSON report printed in the terminal. No voice, no browser, takes ~5 seconds.

---

### Step 4 — Enable Live API Transcription

**Files to modify:** `live_agent/agent.py`  
**Time estimate:** ~30 minutes

Transcription gives the root agent clean text from the user's speech — needed for the tool calls to have meaningful content.

```python
from google.genai.types import AudioTranscriptionConfig

config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    input_audio_transcription=AudioTranscriptionConfig(),
    output_audio_transcription=AudioTranscriptionConfig(),
)
```

This is built into the Live API — no extra cost, no extra model call.

---

### Step 5 — Vision Agent [OPTIONAL BONUS]

**Files to create:**
- `live_agent/sub_agents/vision_agent.py`
- `live_agent/prompts/vision_prompt.py`

**Time estimate:** ~2 hours

Called once at session end. Receives captured JPEG frames (1 frame per answer). Returns body language analysis included in the report.

#### Output shape

```json
{
  "posture": "upright, slightly leaning forward — good engagement",
  "eye_contact": "low — looking down frequently",
  "expression": "nervous, occasional smile when discussing achievements",
  "gestures": "fidgeting with hands visible",
  "energy": "moderate — increased toward the end",
  "tip": "Maintain eye contact with the camera and keep hands relaxed"
}
```

#### How to test (no camera, no voice)

Use a static image:
```python
# tests/test_vision.py
import asyncio, base64
from google.adk.runners import InMemoryRunner
from live_agent.sub_agents.vision_agent import vision_agent

async def test_vision():
    with open("tests/fixtures/test_frame.jpg", "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    runner = InMemoryRunner(agent=vision_agent)
    session = await runner.session_service.create_session(app_name="test", user_id="test")
    result = await runner.run_async(
        user_id="test",
        session_id=session.id,
        new_message=f"Analyse this frame for body language: data:image/jpeg;base64,{b64}",
    )
    for event in result:
        if event.content:
            print(event.content.parts[0].text)

asyncio.run(test_vision())
```

---

### Step 6 — Session Persistence

**Files to create:** `live_agent/utils/session_store.py`  
**Time estimate:** ~45 minutes

Save the final report so the `/report` page has something to display after the voice call ends.

**For hackathon MVP:** local JSON files — zero setup:
```
.sessions/
└── <session_id>.json    # evaluator JSON + vision JSON + metadata
```

```python
# utils/session_store.py
import json, os, uuid
from datetime import datetime

SESSIONS_DIR = ".sessions"

def save_report(session_id: str, report: dict) -> str:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    report["saved_at"] = datetime.utcnow().isoformat()
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    return path

def load_report(session_id: str) -> dict:
    path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    with open(path) as f:
        return json.load(f)
```

**For production:** swap to Firestore — same interface, just different backend.

---

### Step 7 — Frontend

**Time estimate:** ~3–4 hours

#### Pages

```
/ (home)
  - Mode picker: "Job Interview" vs "Startup Pitch"
  - Context form (role, company, CV, or startup name, pitch mode)
  - "Start Session" button

/session
  - Live audio visualiser (waveform / pulsing orb)
  - Camera preview (optional, for vision feature)
  - Real-time transcript display (from Live API transcription)
  - End session button

/report/<session_id>
  - Overall score + category breakdown
  - Per-question scores with individual notes
  - Body language summary (if vision was enabled)
  - Actionable tips
  - Start new session button
```

#### What to hook up

1. Mode picker → POST to backend → create correct agent with context
2. Live audio → WebSocket to ADK server
3. Camera → capture 1 JPEG per answer → send through WebSocket
4. Transcript → display live from transcription events
5. End session → evaluator fires → navigate to `/report/<session_id>`

---

### Step 8 — Google Cloud Deployment

**Time estimate:** ~1–2 hours

Required for hackathon submission.

1. Switch `.env` to `GOOGLE_GENAI_USE_VERTEXAI=TRUE`
2. Set `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION`
3. Write `Dockerfile` for the backend
4. Deploy to **Cloud Run**: `gcloud run deploy`
5. Deploy frontend to **Firebase Hosting** or **Cloud Run**

---

## File Structure (target)

```
backend/
├── .gitignore                    ✅
├── plan.md                       ✅ (this file)
├── project.md                    ✅
└── live_agent/
    ├── .env                      ✅ (gitignored)
    ├── __init__.py               ✅
    ├── agent.py                  ✅ (add tools + evaluator sub-agent)
    │
    ├── tools/                    🔜 Step 1
    │   ├── __init__.py
    │   └── session_tools.py      (log_qa_pair, get_session_context)
    │
    ├── prompts/
    │   ├── __init__.py           ✅
    │   ├── system_prompt.py      ✅ (update with tool-calling instructions — Step 2)
    │   ├── evaluator_prompt.py   🔜 Step 3
    │   └── vision_prompt.py      🔜 Step 5
    │
    ├── sub_agents/               🔜 Step 3
    │   ├── __init__.py
    │   ├── evaluator_agent.py    (replaces scoring + feedback agents)
    │   └── vision_agent.py       🔜 Step 5
    │
    └── utils/                    🔜 Step 6
        └── session_store.py

tests/
    ├── test_tools.py             🔜 Step 1 (unit test, no API key needed)
    ├── test_evaluator.py         🔜 Step 3 (direct agent call, ~5s)
    ├── test_vision.py            🔜 Step 5 (static image, no camera)
    └── fixtures/
        └── test_frame.jpg        🔜 Step 5 (any JPEG headshot for testing)
```

---

## How to Test Without Voice

Voice testing is slow — you have to talk through a full session every time. Use this test pyramid instead:

### Level 1 — Unit tests for tools (fastest, no API key needed)

```bash
cd backend && .venv/bin/python tests/test_tools.py
```

- Tests `log_qa_pair` and `get_session_context` with a mocked `ToolContext`
- Runs in <1 second
- No network, no API key
- Run this every time you change `session_tools.py`

### Level 2 — Direct agent tests (5–10 seconds, uses API)

```bash
cd backend && .venv/bin/python tests/test_evaluator.py
cd backend && .venv/bin/python tests/test_vision.py
```

- Calls the evaluator or vision agent directly using `InMemoryRunner`
- You write mock Q&A data as a string — no session, no audio
- Prints full JSON output to terminal
- Use this to iterate on prompts quickly — change the evaluator_prompt, re-run, see the output

### Level 3 — Text mode in adk web (2-3 minutes, no microphone)

```bash
cd backend && source .venv/bin/activate && adk web
# Go to http://localhost:8000
# Type messages instead of speaking
```

- Tests the full conversation flow without voice
- The trace panel on the right shows every tool call and sub-agent delegation
- Use this when you want to verify the root agent is calling tools at the right time
- Checklist for this level:
  - [ ] `log_qa_pair` appears in trace after each typed answer
  - [ ] `get_session_context` appears when you type "end the session"
  - [ ] `evaluator_agent` delegation appears and returns JSON

### Level 4 — Full voice test (only at milestones)

```bash
cd backend && source .venv/bin/activate && adk web
# Speak a full mock session
```

- Only do this when Levels 1–3 all pass
- Do a full 3-question session (not 8 — keep it short)
- Listen for: natural flow, no awkward pauses, correct wrap-up behaviour

### Iterating on prompts quickly

The fastest way to tune the evaluator or vision prompts:

1. Edit the prompt in `prompts/evaluator_prompt.py`
2. Run `tests/test_evaluator.py` — see output in 5 seconds
3. Repeat until the JSON shape and quality look right
4. Only then test in voice

No need to open a browser or speak a word.

---

## Priority Order (hackathon crunch)

| Priority | Step | Time | Why |
|---|---|---|---|
| **1** | Step 1 — Session tools | 30 min | Foundation. Everything else depends on this. |
| **2** | Step 2 — Update root prompt | 30 min | Root agent needs to know about its tools. |
| **3** | Step 3 — Evaluator agent | 1 hr | Main payoff — scoring + full report in one call. |
| **4** | Step 4 — Live transcription | 30 min | Needed for tools to get clean text from voice. |
| **5** | Step 7 — Frontend | 3–4 hrs | Judges need to see and interact with it. |
| **6** | Step 8 — Cloud deploy | 1–2 hrs | Required for submission. |
| **7** | Step 5 — Vision agent | 2 hrs | Impressive bonus — skip only if truly no time. |
| **8** | Step 6 — Session persistence | 45 min | Only needed if the report page is in scope. |

### Checklist before each push

```
[ ] adk web starts without errors
[ ] Agent loads and connects to Live API
[ ] Level 2 tests pass (test_evaluator.py)
[ ] Level 3 text-mode session works, tools visible in trace
[ ] No .env or __pycache__ in git status
```
