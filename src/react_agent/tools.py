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
from react_agent.prompts import ANSWER_ANALYSIS_PROMPT

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
    qs = (
        get_personalized_questions()
        if priority is None
        else [q for q in get_personalized_questions() if q["priority"] == priority]
    )
    return [f"ID: {q['id']} | {q['question']}" for q in qs]


@tool(args_schema=SelectQuestionArgs)
def select_question(id: str) -> str:
    """Select a question by ID and return its text."""
    for q in get_personalized_questions():
        if str(q["id"]) == id:
            return q["question"]
    return "Question not found."





TOOLS: List[Callable[..., Any]] = [select_question, list_questions]
