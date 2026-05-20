"""원고 → 재가공 + 콘텐츠 아이템 + 아이템별 본문 확장."""

from __future__ import annotations

import os
from pathlib import Path

from anthropic import Anthropic

from src.models import ContentIdea, PipelineResult
from src.parse_response import parse_llm_output

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_PATH = PROMPT_DIR / "manuscript_pipeline.md"
SUB_PROMPT_PATH = PROMPT_DIR / "sub_topic_writer.md"


def _client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경 변수를 설정하세요.")
    return Anthropic(api_key=api_key)


def process_manuscript(
    title: str,
    body: str,
    *,
    model: str,
    max_chars: int,
    source_path: str = "",
) -> PipelineResult:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    body_trimmed = body[:max_chars]
    if len(body) > max_chars:
        body_trimmed += "\n\n...(원문 일부만 전달됨)"

    user_content = template.replace("{{title}}", title).replace("{{body}}", body_trimmed)

    message = _client().messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": user_content}],
    )
    block = message.content[0]
    if block.type != "text":
        raise RuntimeError("예상치 못한 응답 형식")

    return parse_llm_output(block.text.strip(), source_path=source_path)


def process_sub_topic(
    idea: ContentIdea,
    *,
    parent_title: str,
    model: str,
    source_path: str = "",
) -> PipelineResult:
    """콘텐츠 아이템 1개를 본문급 단독 원고로 확장."""
    template = SUB_PROMPT_PATH.read_text(encoding="utf-8")
    user_content = (
        template.replace("{{parent_title}}", parent_title)
        .replace("{{topic}}", idea.topic)
        .replace("{{hook}}", idea.hook)
        .replace("{{expert_angle}}", idea.expert_angle)
        .replace("{{why_missed}}", idea.why_missed)
    )

    message = _client().messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": user_content}],
    )
    block = message.content[0]
    if block.type != "text":
        raise RuntimeError("예상치 못한 응답 형식 (sub topic)")

    return parse_llm_output(block.text.strip(), source_path=source_path)
