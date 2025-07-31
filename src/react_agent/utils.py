"""Utility & helper functions."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

import json
import pathlib
from typing import List, Dict, Optional

def get_message_text(msg: BaseMessage) -> str:
    """Get the text content of a message."""
    content = msg.content
    if isinstance(content, str):
        return content
    elif isinstance(content, dict):
        return content.get("text", "")
    else:
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()


def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    """Load a chat model from a fully specified name.

    Args:
        fully_specified_name (str): String in the format 'provider/model'.
    """
    provider, model = fully_specified_name.split("/", maxsplit=1)
    return init_chat_model(model, model_provider=provider)




_Q_PATH = pathlib.Path(__file__).parent / "questions.json"


def _load_question_bank() -> List[Dict]:
    """Load questions from JSON file and assign sequential IDs if missing."""

    if not _Q_PATH.exists():
        raise FileNotFoundError(f"Question bank not found: {_Q_PATH}")

    data = json.loads(_Q_PATH.read_text())

    # Ensure every entry has an ID; assign sequentially starting at 1
    for idx, q in enumerate(data, 1):
        q.setdefault("id", idx)
    return data


BIOGRAPHICAL_QUESTIONS: List[Dict] = _load_question_bank()

DEFAULT_SUBJECT_INFO = {
    "NAME": "Paul Matusky",
    # The person being asked the questions
    "interviewee_name": "Jono Matusky",  # placeholder; replace as needed
    # default gender-neutral pronouns for the elder
    "pronoun_subject": "he",  # he/she/they
    "pronoun_object": "him",  # him/her/them
    "pronoun_possessive": "his",  # his/her/thei
}


def load_biographical_questions(priority: Optional[int] = None) -> List[Dict]:
    """Return biographical questions, optionally filtered by priority."""

    if priority is None:
        return BIOGRAPHICAL_QUESTIONS.copy()
    return [q for q in BIOGRAPHICAL_QUESTIONS if q["priority"] == priority]



def personalise(text: str, subject_info: dict) -> str:
    """Personalise text by replacing placeholders with subject information."""
    return text.format(**subject_info)


def get_personalized_questions() -> List[dict]:
    """Get all biographical questions with {NAME} placeholders replaced with subject name."""
    personalized_questions = []
    for question in BIOGRAPHICAL_QUESTIONS:
        personalized_question = {
            **question,
            "question": personalise(question["question"], DEFAULT_SUBJECT_INFO)
        }
        personalized_questions.append(personalized_question)
    return personalized_questions
