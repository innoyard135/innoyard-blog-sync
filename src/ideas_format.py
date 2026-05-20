"""ContentIdea 리스트를 마크다운으로 직렬화."""

from src.models import ContentIdea


def ideas_to_markdown(ideas: list[ContentIdea]) -> str:
    lines: list[str] = []
    for i, idea in enumerate(ideas, start=1):
        lines.append(f"### {i}. {idea.topic}")
        if idea.hook:
            lines.append(f"- **훅**: {idea.hook}")
        if idea.expert_angle:
            lines.append(f"- **전문가 각도**: {idea.expert_angle}")
        if idea.why_missed:
            lines.append(f"- **왜 놓치기 쉬운가**: {idea.why_missed}")
        lines.append("")
    return "\n".join(lines).strip()
