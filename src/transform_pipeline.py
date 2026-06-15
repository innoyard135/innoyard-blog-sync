"""원고 → 재가공 + 콘텐츠 아이템 + 아이템별 본문 확장."""

from __future__ import annotations

import os
from pathlib import Path

from google import genai
from google.genai import types

from src.models import ContentIdea, PipelineResult
from src.parse_response import parse_llm_output

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_PATH = PROMPT_DIR / "manuscript_pipeline.md"
SUB_PROMPT_PATH = PROMPT_DIR / "sub_topic_writer.md"


def _generate(user_content: str, *, model: str, max_tokens: int = 8192) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경 변수를 설정하세요.")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=user_content,
        config=types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            # 추론(thinking) 토큰이 출력 예산을 잠식해 본문이 잘리는 것을 방지
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("빈 응답 (Gemini)")
    return text


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

    text = _generate(user_content, model=model)
    return parse_llm_output(text, source_path=source_path)


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

    text = _generate(user_content, model=model)
    return parse_llm_output(text, source_path=source_path)
