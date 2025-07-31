"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""

from datetime import UTC, datetime
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from react_agent.configuration import Configuration
from react_agent.state import InputState, State
from react_agent.tools import TOOLS
from react_agent.utils import load_chat_model, get_personalized_questions, get_message_text
from react_agent.prompts import QUESTION_SELECTION_PROMPT, QUESTION_CONTEXTUALIZATION_PROMPT, ANSWER_ANALYSIS_PROMPT

# Constants
PRIORITIES = [0, 1, 2, 3, 4, 5]

# Pydantic Models for Structured Responses
class AnswerAnalysis(BaseModel):
    """Model for structured answer analysis response."""
    completeness_percentage: int = Field(
        description="How fully the answer addresses the question (0-100)",
        ge=0, le=100
    )
    quality_score: int = Field(
        description="Quality rating of the answer (1-10)",
        ge=1, le=10
    )
    status: Literal["complete", "partial", "not_started"] = Field(
        description="Overall status of the question based on the answer"
    )
    brief_analysis: str = Field(
        description="Brief analysis of the answer quality and completeness"
    )
    follow_up_needed: bool = Field(
        description="Whether a follow-up question would be beneficial"
    )

# Node functions

async def select_question_with_llm(state: State, priority: int, available_questions: List[dict]) -> dict:
    """Use LLM to intelligently select the best question based on conversation context."""
    configuration = Configuration.from_context()
    
    # Get the last 5 messages for context
    last_messages = state.messages[-5:] if len(state.messages) >= 5 else state.messages
    conversation_context = "\n".join([
        f"{msg.__class__.__name__}: {get_message_text(msg)}" 
        for msg in last_messages
    ])
    
    # Format available questions for the LLM
    questions_text = "\n".join([
        f"ID: {q['id']} - {q['question']}"
        for q in available_questions
    ])
    
    # Create prompt for question selection using centralized template
    selection_prompt = QUESTION_SELECTION_PROMPT.format(
        conversation_context=conversation_context,
        priority=priority,
        questions_text=questions_text
    )

    # Get LLM for question selection
    llm = load_chat_model(configuration.model)
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content=selection_prompt)
        ])
        
        selected_id = response.content.strip()
        
        # Find the selected question
        for q in available_questions:
            if str(q["id"]) == selected_id:
                return q
                
        # Fallback to first question if selection fails
        return available_questions[0]
        
    except Exception:
        # Fallback to first question if LLM call fails
        return available_questions[0]


async def contextualize_question_with_llm(state: State, question: str) -> str:
    """Use LLM to rephrase the question to fit the conversation context."""
    configuration = Configuration.from_context()
    
    # Get the last 3 messages for immediate context
    last_messages = state.messages[-3:] if len(state.messages) >= 3 else state.messages
    recent_context = "\n".join([
        f"{msg.__class__.__name__}: {get_message_text(msg)}" 
        for msg in last_messages
    ])
    
    contextualization_prompt = QUESTION_CONTEXTUALIZATION_PROMPT.format(
        recent_context=recent_context,
        question=question,
        interviewee_name=configuration.interviewee_name,
        deceased_name=configuration.deceased_name
    )

    llm = load_chat_model(configuration.model)
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content=contextualization_prompt)
        ])
        
        return response.content.strip()
        
    except Exception:
        # Fallback to original question if LLM call fails
        return question


async def select_question_node(state: State) -> dict:
    """Select the next question to ask based on priority and status, using LLM for intelligent selection."""
    questions_update = state.questions.copy()
    configuration = Configuration.from_context()
    
    # Ensure questions are initialised
    if not questions_update:
        for q in get_personalized_questions(configuration.deceased_name):
            questions_update[q["id"]] = {
                "question": q["question"],
                "priority": q["priority"],
                "status": "not_started",
                "answers": [],
                "analysis": "",
                "last_asked": None,
                "follow_up_count": 0,
            }
    
    # For the very first interaction, just initialize and pass through
    if len(state.messages) <= 1:
        return {"questions": questions_update}
    
    # Check if we need a new question (no current question OR current question is complete)
    need_new_question = (
        not state.current_question_id or 
        (state.current_question_id in questions_update and 
         questions_update[state.current_question_id]["status"] == "complete")
    )
    
    # Also check if current question exists but is complete (redundant safety check)
    if (state.current_question_id and 
        state.current_question_id in questions_update and 
        questions_update[state.current_question_id]["status"] == "complete"):
        need_new_question = True

    if need_new_question:
        
        # Check if all questions are complete
        all_complete = all(
            questions_update[qid]["status"] == "complete" 
            for qid in questions_update
        )
        
        # If all questions are complete, end the interview
        if all_complete:
            return {
                "current_question_id": None,
                "questions": questions_update,
                "finished": True,
            }
        
        # Find available questions for each priority level, starting from highest priority
        for priority in PRIORITIES:
            available_questions = []
            for q in get_personalized_questions(configuration.deceased_name):
                if q["priority"] == priority:
                    qid = q["id"]
                    if questions_update[qid]["status"] == "not_started":
                        available_questions.append(q)
            
            # If we have questions at this priority level, use LLM to select intelligently
            if available_questions:
                # Only use LLM selection if we have conversation context (more than just welcome message)
                if len(state.messages) > 2:
                    selected_question = await select_question_with_llm(state, priority, available_questions)
                else:
                    # For early conversation, just use the first available question
                    selected_question = available_questions[0]
                
                # Mark the question as in progress
                questions_update[selected_question["id"]]["status"] = "in_progress"
                
                return {
                    "current_question_id": selected_question["id"],
                    "questions": questions_update,
                }

    return {"questions": questions_update}


async def answer_analysis_node(state: State) -> dict:
    """Analyze the user's answer and update question status."""
    questions_update = state.questions.copy()
    
    # Initialize questions if empty
    if not questions_update:
        configuration = Configuration.from_context()
        for q in get_personalized_questions(configuration.deceased_name):
            questions_update[q["id"]] = {
                "question": q["question"],
                "priority": q["priority"],
                "status": "not_started",
                "answers": [],
                "analysis": "",
                "last_asked": None,
                "follow_up_count": 0,
            }

    # Get user messages to count responses to current question
    user_messages = []
    for msg in state.messages:
        if hasattr(msg, 'content') and isinstance(msg, HumanMessage):
            content = msg.content
            # Ensure content is a string
            if isinstance(content, str):
                user_messages.append(content)
            elif isinstance(content, list):
                user_messages.append(" ".join(str(item) for item in content))
            else:
                user_messages.append(str(content))
    
    if not user_messages or not state.current_question_id:
        return {"questions": questions_update}

    latest_answer = user_messages[-1]
    current_qid = state.current_question_id
    configuration = Configuration.from_context()

    # Get the current question text
    question_text = next(
        (q["question"] for q in get_personalized_questions(configuration.deceased_name) if q["id"] == current_qid), 
        "Unknown"
    )

    
    # Analyze the answer using structured LLM response
    try:
        llm = load_chat_model(configuration.model)
        structured_llm = llm.with_structured_output(AnswerAnalysis)
        
        analysis_prompt = ANSWER_ANALYSIS_PROMPT.format(
            question=question_text,
            answer=latest_answer
        )
        
        analysis_result = await structured_llm.ainvoke([
            SystemMessage(content=analysis_prompt)
        ])
        
    except Exception as e:
        # Fallback analysis if structured output fails
        analysis_result = AnswerAnalysis(
            completeness_percentage=50,
            quality_score=5,
            status="partial",
            brief_analysis=f"Analysis error: {str(e)}",
            follow_up_needed=False
        )

    # Update the current question with the new answer and analysis
    if current_qid in questions_update:
        questions_update[current_qid]["answers"].append(latest_answer)
        questions_update[current_qid]["analysis"] = analysis_result.brief_analysis
        
        # Count total answers for this question after adding the new one
        total_answers = len(questions_update[current_qid]["answers"])
        
        # Mark as complete if:
        # 1. LLM says it's complete, OR
        # 2. We've had 2+ user responses to this question (time to move on)
        if analysis_result.status == "complete" or total_answers >= 2:
            questions_update[current_qid]["status"] = "complete"
            if total_answers >= 2:
                questions_update[current_qid]["analysis"] += " (Marked complete after 2+ responses)"
        elif analysis_result.status == "partial":
            questions_update[current_qid]["status"] = "partial"
        else:
            questions_update[current_qid]["status"] = "in_progress"

    return {"questions": questions_update}


def make_welcome_message(configuration: Configuration) -> str:
    """Create the opening welcome message for family interviews."""
    return (
        f"Hi {configuration.interviewee_name}, I'm Reflekta's biographer. I'm here to help preserve {configuration.deceased_name}'s life story so you and your family can connect with them for generations to come.\n\n"
        "I'll ask some questions to guide us, but feel free to answer in whatever way feels natural. If a memory takes you in a different direction, just go with it — I'll follow and ask more as we go.\n\n"
        f"To start: Could you tell me about your relationship with {configuration.deceased_name}?"
    )


async def interview_agent(state: State) -> Dict[str, List[AIMessage]]:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_context()

    # Handle first message with welcome
    if len(state.messages) == 1:
        return {
            "messages": [AIMessage(content=make_welcome_message(configuration))]
        }

    # Check if we have a selected question to ask
    if state.current_question_id and state.current_question_id in state.questions:
        current_question_data = state.questions[state.current_question_id]
        
        # If this question is in progress and we haven't asked it yet, ask it
        if current_question_data["status"] == "in_progress":
            # Contextualize the question based on recent conversation
            question_text = current_question_data["question"]
            
            # Try to contextualize if we have conversation history
            if len(state.messages) > 2:
                contextualized_question = await contextualize_question_with_llm(state, question_text)
            else:
                contextualized_question = question_text
            
            return {
                "messages": [AIMessage(content=contextualized_question)]
            }

    # For general conversation (no specific question to ask), use regular agent
    interview_agent_model = load_chat_model(configuration.model).bind_tools(TOOLS)

    # Format the system prompt
    system_message = configuration.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat(),
        interviewee_name=configuration.interviewee_name,
        deceased_name=configuration.deceased_name
    )

    # Get the model's response
    response = cast(
        AIMessage,
        await interview_agent_model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }

    # Return the model's response as a list to be added to existing messages
    return {"messages": [response]}


def route_model_output(state: State) -> Literal["__end__", "tools"]:
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call ("__end__" or "tools").
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    # If there is no tool call, then we finish
    if not last_message.tool_calls:
        return "__end__"
    # Otherwise we execute the requested actions
    return "tools"



# Define a new graph

builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Define the nodes we will cycle between
builder.add_node("select_question", select_question_node)
builder.add_node("answer_analysis", answer_analysis_node)
builder.add_node(interview_agent)
builder.add_node("tools", ToolNode(TOOLS))

# Set the entrypoint as `select_question`
# This means that this node is the first one called
builder.add_edge("__start__", "answer_analysis")

# Add edge from select_question to interview_agent
builder.add_edge("answer_analysis", "select_question")
builder.add_edge("select_question", "interview_agent")

# Add a conditional edge to determine the next step after `interview_agent`
builder.add_conditional_edges(
    "interview_agent",
    # After interview_agent finishes running, the next node(s) are scheduled
    # based on the output from route_model_output
    route_model_output,
)

# Add a normal edge from `tools` to `interview_agent`
# This creates a cycle: after using tools, we always return to the model
builder.add_edge("tools", "interview_agent")



# Compile the builder into an executable graph
graph = builder.compile(name="ReAct Agent")
