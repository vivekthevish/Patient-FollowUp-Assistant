"""Shared Gemini helpers."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from src.config import GEMINI_API_KEY, GEMINI_MODEL


TModel = TypeVar("TModel", bound=BaseModel)


def gemini_enabled() -> bool:
    return bool(GEMINI_API_KEY)


def generate_structured_response(prompt: str, schema_model: type[TModel], system_instruction: str) -> TModel:
    from google import genai
    from google.genai import types

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
