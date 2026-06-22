"""Shared Gemini helpers."""

from __future__ import annotations

import logging
from typing import TypeVar

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import GEMINI_API_KEY, GEMINI_MODEL, MAX_RETRIES


logger = logging.getLogger(__name__)


TModel = TypeVar("TModel", bound=BaseModel)


def gemini_enabled() -> bool:
    return bool(GEMINI_API_KEY)


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        f"Gemini API call failed (attempt {retry_state.attempt_number}/{MAX_RETRIES}), retrying..."
    )
)
def generate_structured_response(prompt: str, schema_model: type[TModel], system_instruction: str) -> TModel:
    from google import genai
    from google.genai import types

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema_model,
                system_instruction=system_instruction,
            ),
        )
        response_text = getattr(response, "text", None) or "{}"
        return schema_model.model_validate_json(response_text)
    except Exception as exc:
        logger.error(f"Gemini API call failed: {exc}")
        raise
