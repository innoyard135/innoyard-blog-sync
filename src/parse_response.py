"""LLM 구분자 응답 파싱."""

from __future__ import annotations

import re

from src.models import ContentIdea, PipelineResult


def _section(text: str, name: str) -> str:
    pattern = rf"===\s*{name}\s*===\s*\n(.*?)(?=\n===|\Z)"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _parse_tags(raw: str) -> list[str]:
    raw = raw.replace("태그:", "").strip()
    parts = re.split(r"[,，、\n]+", raw)
    return [p.strip() for p in parts if p.strip()][:12]


def _parse_ideas(raw: str) -> list[ContentIdea]:
    ideas: list[ContentIdea] = []
    blocks = re.split(r"\n---+\n", raw)
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        def field(key: str) -> str:
            m = re.search(rf"^{key}\s*:\s*(.+)$", block, re.MULTILINE)
            return m.group(1).strip() if m else ""

        topic = field("주제")
        if not topic:
            continue
        ideas.append(
            ContentIdea(
                topic=topic,
                hook=field("훅"),
                expert_angle=field("전문가 각도"),
                why_missed=field("왜 놓치기 쉬운가"),
            )
        )
    return ideas


def parse_llm_output(raw: str, *, source_path: str = "") -> PipelineResult:
    title = _section(raw, "TITLE") or "제목 없음"
    body = _section(raw, "BODY")
    tags = _parse_tags(_section(raw, "TAGS"))
    ideas = _parse_ideas(_section(raw, "CONTENT_IDEAS"))[:2]

    if not body:
        # 구분자 없이 온 경우 전체를 본문으로
        body = raw.strip()

    return PipelineResult(
        title=title,
        body=body,
        tags=tags,
        ideas=ideas,
        source_path=source_path,
    )
