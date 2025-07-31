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
    
    # Ensure questions are initialised
    if not questions_update:
        for q in get_personalized_questions():
            questions_update[q["id"]] = {
                "question": q["question"],
                "priority": q["priority"],
                "status": "not_started",
                "answers": [],
                "analysis": "",
                "last_asked": None,
                "follow_up_count": 0,
            }
    
    # Check if we need a new question (no current question OR current question is complete)
    need_new_question = (
        not state.question or 
        state.question.strip() == "" or
        (state.current_question_id and 
         state.current_question_id in questions_update and 
         questions_update[state.current_question_id]["status"] == "complete")
    )

    if need_new_question:
        
        # Check if all questions are complete
        all_complete = all(
            questions_update[qid]["status"] == "complete" 
            for qid in questions_update
        )
        
        # If all questions are complete, end the interview
        if all_complete:
            return {
                "question": "",
                "current_question_id": None,
                "questions": questions_update,
                "finished": True,
            }
        
        # Find available questions for each priority level, starting from highest priority
        for priority in PRIORITIES:
            available_questions = []
            for q in get_personalized_questions():
                if q["priority"] == priority:
                    qid = q["id"]
                    if questions_update[qid]["status"] == "not_started":
                        available_questions.append(q)
            
            # If we have questions at this priority level, use LLM to select intelligently
            if available_questions:
                # Only use LLM selection if we have conversation context (more than just welcome message)
                if len(state.messages) > 2:
                    selected_question = await select_question_with_llm(state, priority, available_questions)
                    # Contextualize the question for natural flow
                    contextualized_question = await contextualize_question_with_llm(state, selected_question["question"])
                else:
                    # For early conversation, just use the first available question
                    selected_question = available_questions[0]
                    contextualized_question = selected_question["question"]
                
                return {
                    "question": contextualized_question,
                    "current_question_id": selected_question["id"],
                    "questions": questions_update,
                }

    return {"questions": questions_update}


async def answer_analysis_node(state: State) -> dict:
    """Analyze the user's answer and update question status."""
    questions_update = state.questions.copy()
    
    # Initialize questions if empty
    if not questions_update:
        for q in get_personalized_questions():
            questions_update[q["id"]] = {
                "question": q["question"],
                "priority": q["priority"],
                "status": "not_started",
                "answers": [],
                "analysis": "",
                "last_asked": None,
                "follow_up_count": 0,
            }

    # Get the last 5 messages for context
    recent_messages = state.messages[-5:] if len(state.messages) >= 5 else state.messages
    user_messages = []
    for msg in recent_messages:
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
        (q["question"] for q in get_personalized_questions() if q["id"] == current_qid), 
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
        
        # Handle follow-up logic
        current_follow_up_count = questions_update[current_qid].get("follow_up_count", 0)
        
        if analysis_result.status == "complete":
            questions_update[current_qid]["status"] = "complete"
        elif analysis_result.status == "partial":
            if analysis_result.follow_up_needed and current_follow_up_count < 1:
                # Keep as partial for potential follow-up
                questions_update[current_qid]["status"] = "partial"
                questions_update[current_qid]["follow_up_count"] = current_follow_up_count + 1
            else:
                # Max follow-ups reached or no follow-up needed, mark as complete
                questions_update[current_qid]["status"] = "complete"
                questions_update[current_qid]["analysis"] += " (Marked complete after follow-up limit reached)"
        else:
            questions_update[current_qid]["status"] = "not_started"

    # Return only state updates when something actually changed to minimize noise
    # Note: With LangGraph Platform using stream_mode="updates", 
    # this state change will still be visible in the stream
    if questions_update != state.questions:
        return {"questions": questions_update}
    else:
        return {}  # No visible update if nothing changed


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
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_context()

    # TODO: Fix to handle non first session!
    if len(state.messages) == 1:
        return {
            "messages": [AIMessage(content=make_welcome_message(configuration))]
        }

    # Initialize the agent with tool binding. Change the agent or add more tools here.
    interview_agent = load_chat_model(configuration.model).bind_tools(TOOLS)

    # Format the system prompt. Customize this to change the agent's behavior.
    system_message = configuration.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat(),
        interviewee_name=configuration.interviewee_name,
        deceased_name=configuration.deceased_name
    )

    # Get the model's response
    response = cast(
        AIMessage,
        await interview_agent.ainvoke(
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
