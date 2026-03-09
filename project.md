# InterviewAI — Live Interview Coach Agent
> Gemini Live Agent Challenge — **Live Agents** Category

---

## What We're Building

A real-time AI interview coach that users can talk to naturally. The agent listens to the user, asks relevant questions, gives live feedback, and helps them improve — all through a natural voice conversation.

The agent is **general-purpose**: users can practice for any type of interview by providing context upfront (job role, company, topic area, etc.). It also has a dedicated **Startup Pitch** mode for founders who want to practice investor pitches specifically.

---

## Core User Experience

1. User opens the app and selects a mode (General Interview or Startup Pitch)
2. User optionally provides context (job role, company, pitch deck text, etc.)
3. Agent starts a live voice conversation — asks questions, listens, responds naturally
4. Agent gives real-time feedback after each answer
5. Session ends with a summary and improvement tips

---

## Modes

### 🎙️ General Interview Mode
- User provides context: job title, company name, interview type (behavioural, technical, HR)
- Agent conducts a realistic mock interview based on that context
- Asks 5–8 questions, gives feedback after each
- Wraps up with an overall assessment

### 🚀 Startup Pitch Mode

Two sub-modes:

#### ⚡ Elevator Pitch (Short, No Dialogue)
- User speaks their pitch (~60 seconds) uninterrupted
- Agent listens to the full pitch without cutting in
- After the pitch ends, agent gives structured feedback:
  - Clarity of the problem/solution
  - Confidence and delivery
  - What landed well vs. what was weak
  - Suggested improvements

#### 💼 Full Pitch (Conversational)
- Agent plays the role of an investor
- Realistic back-and-forth conversation
- Agent asks probing questions (problem, market, traction, team, ask)
- Can interrupt naturally for clarification
- Feedback given after each answer + full summary at the end

---

## Hackathon Requirements

### Must-Haves (for submission)

- [ ] Real-time voice interaction (user talks, agent talks back — no typing)
- [ ] Interruption support in conversational modes
- [ ] Context-aware conversation (agent adapts based on user-provided info)
- [ ] At least one multimodal input (audio is the primary; video/camera optional bonus)
- [ ] Session feedback — agent gives structured feedback at end of session
- [ ] Backend hosted on Google Cloud
- [ ] Use a Gemini model
- [ ] Use Google GenAI SDK or ADK
- [ ] Use at least one Google Cloud service

### Submission Deliverables

- [ ] Text description (features, tech used, learnings)
- [ ] Public GitHub repo with spin-up instructions in README
- [ ] Proof of Google Cloud deployment (screen recording or code link)
- [ ] Architecture diagram
- [ ] Demo video (< 4 minutes, shows multimodal features working live)

---

## What's Out of Scope (for now)
- Mobile app
- User authentication / accounts
- Persistent user profiles across sessions
- Video body language analysis (nice to have, not required)
- Scoring leaderboard

---

## Open Questions / Decisions TBD
- Where exactly does user context get passed in? (text box before session, or spoken at start?)
- Do we store session transcripts? (Firestore — decide later)
- Camera input for body language — is there time to build this?
- Frontend framework and UI design (not decided yet)
