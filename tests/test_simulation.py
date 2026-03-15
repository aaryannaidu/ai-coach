import asyncio
import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types as genai_types
from google.genai import Client

from live_agent.agent import create_interview_agent, TEXT_MODEL

def user_msg(text: str) -> genai_types.Content:
    return genai_types.Content(role="user", parts=[genai_types.Part(text=text)])

async def send_and_collect(runner, user_id, session_id, text: str) -> str:
    """Send one user message, collect agent text."""
    # InMemoryRunner yields all events, sometimes they are accumulated or chunks.
    # We will just collect all text parts and if it's accumulated, we take the last.
    # Alternatively, google.adk.runners yields `AgentOutput` events.
    # Let's just collect the text from the final event or cleanly join them if they are deltas.
    
    agent_text_parts = []
    
    result = runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg(text),
    )

    async for event in result:
        # Check if it has content and parts
        if hasattr(event, "content") and event.content:
            if hasattr(event.content, "parts") and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        agent_text_parts.append(part.text)
                    
    # If the text parts are growing larger (accumulated), we only want the last one.
    # We can handle this by joining them normally, but let's check if the last part contains the first part to avoid repeating.
    final_text = "".join(agent_text_parts)
    
    # Wait, actually, let's just use the last event's text if the model returns the whole string each event (which streaming sometimes does in higher level wrappers)
    # But usually it's deltas. Let's stick to "".join(agent_text_parts).
    return final_text.strip()


@pytest.mark.asyncio
async def test_full_interview_simulation():
    """
    Runs an AI (Gemini 2.0 Flash) as the 'Candidate' against the Interview Agent.
    """
    print("\n" + "="*60)
    print("STARTING E2E INTERVIEW SIMULATION (LLM VS LLM)")
    print("="*60)
    
    # Context details
    candidate_name = "Alex Chen"
    candidate_role = "Senior Product Manager"
    candidate_company = "Google"
    candidate_cv = (
        "Name: Alex Chen. "
        "Experience: 5 years total. "
        "Recent: 3 years as PM at Series B SaaS startup 'DataFlow', led the successful launch of their flagship mobile app from scratch to 50k MAU. "
        "Previous: 2 years as a Software Engineer at Infosys. "
        "Strengths: Data-driven decision making, cross-functional leadership, agile methodologies."
    )
    job_description = "Looking for a Senior PM to lead the Google Maps consumer experience team. Must have mobile app experience."

    # 1. Setup the Core Interview Agent
    interviewer = create_interview_agent(
        role=candidate_role,
        company=candidate_company,
        interview_type="Behavioural",
        cv_text=candidate_cv,
        job_description=job_description,
        model=TEXT_MODEL, 
    )
    
    runner = InMemoryRunner(agent=interviewer, app_name="test_sim")
    session = await runner.session_service.create_session(
        app_name="test_sim",
        user_id="candidate_123",
        state={
            "mode": "General Interview",
            "user_context": {
                "role": candidate_role,
                "company": candidate_company,
                "interview_type": "Behavioural",
            },
        },
    )
    
    # 2. Setup the "Simulated Human Candidate"
    candidate_client = Client()
    CANDIDATE_MODEL = 'gemini-2.5-flash-lite'
    
    # Give the candidate a clear persona
    candidate_system_instruction = (
        f"You are a candidate named {candidate_name} interviewing for a {candidate_role} role at {candidate_company}. "
        f"Your background: {candidate_cv} "
        "You are currently doing a live interview conversation via voice. "
        "RULES:\n"
        "1. Keep your answers conversational, natural, and relatively concise (no more than 3-4 sentences per answer).\n"
        "2. Play the role of a capable but realistic candidate. Give specific STAR answers when asked for examples.\n"
        "3. Wait for the interviewer to follow up, answer directly, and act entirely as the candidate.\n"
        "4. Start directly into your response. Do not use quotes, filler text, or actions like *smiles*."
    )
    
    # We use a ChatSession for the candidate so it remembers the flow of the conversation
    candidate_chat = candidate_client.chats.create(
        model=CANDIDATE_MODEL,
        config=genai_types.GenerateContentConfig(
            system_instruction=candidate_system_instruction,
            temperature=0.7,
        )
    )

    # 3. Start the Simulation
    # The session expects a trigger utterance to start
    candidate_statement = "Hi, I'm ready to begin the interview."
    print(f"\n👤 CANDIDATE [Flash]:\n{candidate_statement}")
    
    max_turns = 6  # Adjust this depending on how long you want the simulation to run
    
    for turn in range(max_turns):
        print("\n" + "-"*40)
        
        # A. Pass the candidate's answer to our Core Agent
        interviewer_response = await send_and_collect(
            runner, "candidate_123", session.id, candidate_statement
        )
        print(f"\n🤖 INTERVIEW COACH [Core Agent]:\n{interviewer_response}")
        
        if not interviewer_response:
            print("[System]: Interviewer did not respond! Ending simulation.")
            break
            
        # B. Check for wrap-up/end signals (simple heuristic)
        if "feedback" in interviewer_response.lower() and turn > 1:
            # Let the candidate say a quick thanks
            candidate_statement = "Thanks for the feedback!"
            print(f"\n👤 CANDIDATE [Flash]:\n{candidate_statement}")
            
            # Allow one more response just in case the interviewer is gracefully exiting
            final_response = await send_and_collect(
                runner, "candidate_123", session.id, candidate_statement
            )
            print(f"\n🤖 INTERVIEW COACH [Core Agent]:\n{final_response}")
            break
            
        # C. Have the simulated Human answer the question
        candidate_response_obj = candidate_chat.send_message(interviewer_response)
        candidate_statement = candidate_response_obj.text
        print(f"\n👤 CANDIDATE [Flash]:\n{candidate_statement}")
        
        # Free Tier Rate Limit is 10 requests per minute for 2.5-flash-lite. 
        # Adding a sleep here spaces out the 12+ API calls in this test so it passes reliably.
        await asyncio.sleep(6)

    print("\n" + "="*60)
    print("SIMULATION COMPLETE")
    print("="*60)
