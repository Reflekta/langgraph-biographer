"""This module provides example tools for web scraping and search functionality.


These tools are intended as free examples to get started. For production use,
consider implementing more robust and specialized tools tailored to your needs.
"""

from typing import Any, Callable, List, Optional, cast

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.types import Command
from langchain_core.messages import ToolMessage, SystemMessage
from typing_extensions import Annotated

from react_agent.configuration import Configuration
from react_agent.state import State
from react_agent.utils import get_personalized_questions, load_chat_model, get_message_text
# from react_agent.prompts import TOOL_QUESTION_SELECTION_PROMPT, TOOL_QUESTION_CONTEXTUALIZATION_PROMPT

# Initialize LLM for analysis
def get_analysis_llm():
    """Get LLM for answer analysis and cross-question matching."""
    return ChatOpenAI(model="gpt-4.1-nano", temperature=0.1)



### Pydantic models for the tools. ###
class ListQuestionsArgs(BaseModel):
    priority: Optional[int] = Field(
        None, description="Priority level to filter by (1-5)"
    )

class SelectQuestionArgs(BaseModel):
    id: str = Field(description="ID of the question to select")

class SelectNextQuestionArgs(BaseModel):
    priority: Optional[int] = Field(
        None, description="Priority level to focus on (0-4). If not specified, will check all priorities starting from highest."
    )
    
### TOOLS ###


@tool(args_schema=ListQuestionsArgs)
def list_questions(priority: Optional[int] = None) -> List[str]:
    """List all biographical questions, optionally filtered by priority."""
    from react_agent.configuration import Configuration
    configuration = Configuration.from_context()
    
    qs = (
        get_personalized_questions(configuration.deceased_name)
        if priority is None
        else [q for q in get_personalized_questions(configuration.deceased_name) if q["priority"] == priority]
    )
    return [f"ID: {q['id']} | {q['question']}" for q in qs]


@tool(args_schema=SelectQuestionArgs)
def select_question(id: str) -> str:
    """Select a question by ID and return its text."""
    from react_agent.configuration import Configuration
    configuration = Configuration.from_context()
    
    for q in get_personalized_questions(configuration.deceased_name):
        if str(q["id"]) == id:
            return q["question"]
    return "Question not found."


@tool(args_schema=SelectNextQuestionArgs)
def select_next_question(state: Annotated[State, "Current conversation state"], priority: Optional[int] = None) -> str:
    """Intelligently select the next best question based on conversation context and priority."""
    
    # Get conversation context (last 5 messages)
    messages = state.messages
    last_messages = messages[-5:] if len(messages) >= 5 else messages
    conversation_context = "\n".join([
        f"{msg.__class__.__name__}: {get_message_text(msg)}" 
        for msg in last_messages
    ])
    
    # Get questions for the specified priority or find the best priority
    questions_to_check = state.questions.copy()
    
    # Ensure questions are initialized
    if not questions_to_check:
        configuration = Configuration.from_context()
        for q in get_personalized_questions(configuration.deceased_name):
            questions_to_check[q["id"]] = {
                "question": q["question"],
                "priority": q["priority"],
                "status": "not_started",
                "answers": [],
                "analysis": "",
                "last_asked": None,
            }
    
    # Find available questions for the priority level
    priorities_to_check = [priority] if priority is not None else [0, 1, 2, 3, 4, 5]
    
    for pri in priorities_to_check:
        available_questions = []
        configuration = Configuration.from_context()
        for q in get_personalized_questions(configuration.deceased_name):
            if q["priority"] == pri:
                qid = q["id"]
                if qid in questions_to_check and questions_to_check[qid]["status"] == "not_started":
                    available_questions.append(q)
        
        if available_questions:
            # If we have conversation context, use LLM to select intelligently
            if len(messages) > 2:
                try:
                    configuration = Configuration.from_context()
                    llm = load_chat_model(configuration.model)
                    
                    # Format available questions for the LLM
                    questions_text = "\n".join([
                        f"ID: {q['id']} - {q['question']}"
                        for q in available_questions
                    ])
                    
                    selection_prompt = TOOL_QUESTION_SELECTION_PROMPT.format(
                        conversation_context=conversation_context,
                        priority=pri,
                        questions_text=questions_text
                    )
                    
                    response = llm.invoke([SystemMessage(content=selection_prompt)])
                    selected_question_text = response.content.strip()
                    
                    # Also contextualize the question for natural flow
                    recent_messages = messages[-3:] if messages else []
                    recent_context = "\n".join([
                        f"{msg.__class__.__name__}: {get_message_text(msg)}" 
                        for msg in recent_messages
                    ])
                    
                    contextualization_prompt = TOOL_QUESTION_CONTEXTUALIZATION_PROMPT.format(
                        recent_context=recent_context,
                        selected_question_text=selected_question_text,
                        interviewee_name=configuration.interviewee_name,
                        deceased_name=configuration.deceased_name
                    )
                    
                    contextualized_response = llm.invoke([SystemMessage(content=contextualization_prompt)])
                    return contextualized_response.content.strip()
                    
                except Exception:
                    # Fallback to first available question
                    return available_questions[0]["question"]
            else:
                # For early conversation, just return the first available question
                return available_questions[0]["question"]
    
    return "No available questions found for the specified priority level."






TOOLS: List[Callable[..., Any]] = [select_question, list_questions]
