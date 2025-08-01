"""Define the configurable parameters for the agent."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Annotated

from langchain_core.runnables import ensure_config
from langgraph.config import get_config

from react_agent import prompts


@dataclass(kw_only=True)
class Configuration:
    """The configuration for the agent."""

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions. "
            "This prompt sets the context and behavior for the agent. "
        },
    )

    deceased_name: str = field(
        default="Robert Chen",
        metadata={
            "description": "The name of the deceased person being memorialized. "
            "This will be used throughout the interview to personalize questions."
        },
    )

    interviewee_name: str = field(
        default="Sarah Chen",
        metadata={
            "description": "The name of the person being interviewed. "
            "This helps personalize the conversation and build rapport."
        },
    )

    elder_id: str = field(
        default="",
        metadata={
            "description": "The unique identifier of the elder being interviewed. "
            "This is used for thread isolation and ensuring interviews are specific to each elder."
        },
    )

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="openai/gpt-4.1-nano",
        metadata={
            "description": "The name of the language model to use for the agent's main interactions. "
            "Should be in the form: provider/model-name."
        },
    )

    max_search_results: int = field(
        default=10,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )

    @classmethod
    def from_context(cls, state=None) -> Configuration:
        """Create a Configuration instance from a RunnableConfig object and optionally from state."""
        try:
            config = get_config()
        except RuntimeError:
            config = None
        config = ensure_config(config)
        configurable = config.get("configurable") or {}
        _fields = {f.name for f in fields(cls) if f.init}
        
        # Debug logging
        print(f"DEBUG: Configuration.from_context() called")
        print(f"DEBUG: Raw config: {config}")
        print(f"DEBUG: Configurable: {configurable}")
        print(f"DEBUG: Available fields: {_fields}")
        
        filtered_config = {k: v for k, v in configurable.items() if k in _fields}
        print(f"DEBUG: Filtered config: {filtered_config}")
        
        # Check state for name fields as fallback if not in config
        if state:
            print(f"DEBUG: State provided - deceased_name: {getattr(state, 'deceased_name', 'not found')}, interviewee_name: {getattr(state, 'interviewee_name', 'not found')}")
            if 'deceased_name' not in filtered_config and hasattr(state, 'deceased_name') and state.deceased_name:
                filtered_config['deceased_name'] = state.deceased_name
                print(f"DEBUG: Using deceased_name from state: {state.deceased_name}")
            if 'interviewee_name' not in filtered_config and hasattr(state, 'interviewee_name') and state.interviewee_name:
                filtered_config['interviewee_name'] = state.interviewee_name
                print(f"DEBUG: Using interviewee_name from state: {state.interviewee_name}")
            if 'elder_id' not in filtered_config and hasattr(state, 'elder_id') and state.elder_id:
                filtered_config['elder_id'] = state.elder_id
                print(f"DEBUG: Using elder_id from state: {state.elder_id}")
        
        instance = cls(**filtered_config)
        print(f"DEBUG: Created Configuration - deceased_name: {instance.deceased_name}, interviewee_name: {instance.interviewee_name}")
        
        return instance
