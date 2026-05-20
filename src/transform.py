"""LLM 재작성."""

from __future__ import annotations

import os
from pathlib import Path

from anthropic import Anthropic

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
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경 변수를 설정하세요.")

    body_trimmed = body[:max_chars]
    if len(body) > max_chars:
        body_trimmed += "\n\n...(원문 일부만 전달됨)"

    user_content = (
        load_prompt_template()
        .replace("{{title}}", title)
        .replace("{{body}}", body_trimmed)
    )

    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": user_content}],
    )
    block = message.content[0]
    if block.type != "text":
        raise RuntimeError("예상치 못한 응답 형식")
    return block.text.strip()
