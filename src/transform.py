"""LLM 재작성."""

from __future__ import annotations

import os
from pathlib import Path

from google import genai
from google.genai import types

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "doctor_rewrite.md"


def load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def rewrite(
    title: str,
    body: str,
    *,
    model: str,
    max_chars: int,
) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경 변수를 설정하세요.")

    body_trimmed = body[:max_chars]
    if len(body) > max_chars:
        body_trimmed += "\n\n...(원문 일부만 전달됨)"

    user_content = (
        load_prompt_template()
        .replace("{{title}}", title)
        .replace("{{body}}", body_trimmed)
    )

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=user_content,
        config=types.GenerateContentConfig(
            max_output_tokens=4096,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("빈 응답 (Gemini)")
    return text
