"""원고 파일 읽기."""

from __future__ import annotations

from pathlib import Path

SUPPORTED = {".md", ".txt", ".markdown"}


def read_text_file(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    title = path.stem.replace("_", " ")
    # 첫 줄이 # 제목이면 분리
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0].lstrip("# ").strip()
        text = "\n".join(lines[1:]).strip()
    return title, text


def read_docx_file(path: Path) -> tuple[str, str]:
    from docx import Document

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        return path.stem, ""
    title = paragraphs[0]
    body = "\n\n".join(paragraphs[1:]) if len(paragraphs) > 1 else paragraphs[0]
    return title, body


def load_manuscript(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx_file(path)
    if suffix in SUPPORTED:
        return read_text_file(path)
    raise ValueError(f"지원하지 않는 형식: {path.suffix} ({path})")


def list_manuscripts(directory: Path) -> list[Path]:
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        return []
    files: list[Path] = []
    for p in sorted(directory.iterdir()):
        if p.name.startswith(".") or p.name.startswith("_"):
            continue
        if p.is_file() and p.suffix.lower() in SUPPORTED | {".docx"}:
            files.append(p)
    return files
