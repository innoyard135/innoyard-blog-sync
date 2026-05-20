from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContentIdea:
    topic: str
    hook: str
    expert_angle: str
    why_missed: str


@dataclass
class PipelineResult:
    title: str
    body: str
    tags: list[str]
    ideas: list[ContentIdea] = field(default_factory=list)
    source_path: str = ""
