"""원고 → 재가공 + 콘텐츠 아이템."""

from __future__ import annotations

import os
from pathlib import Path

from anthropic import Anthropic

from src.models import PipelineResult
from src.parse_response import parse_llm_output

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "manuscript_pipeline.md"


def process_manuscript(
    title: str,
    body: str,
    *,
    model: str,
    max_chars: int,
    source_path: str = "",
) -> PipelineResult:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경 변수를 설정하세요.")

    template = PROMPT_PATH.read_text(encoding="utf-8")
    body_trimmed = body[:max_chars]
    if len(body) > max_chars:
        body_trimmed += "\n\n...(원문 일부만 전달됨)"

    user_content = template.replace("{{title}}", title).replace("{{body}}", body_trimmed)

    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": user_content}],
    )
    block = message.content[0]
    if block.type != "text":
        raise RuntimeError("예상치 못한 응답 형식")

    return parse_llm_output(block.text.strip(), source_path=source_path)
