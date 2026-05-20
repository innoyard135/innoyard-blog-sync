"""Notion API: 원고 페이지 읽기 + 결과 페이지 생성."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import httpx

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"


def _headers() -> dict[str, str]:
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise RuntimeError("NOTION_TOKEN 환경 변수가 필요합니다.")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": VERSION,
        "Content-Type": "application/json",
    }


def page_id_from_url(url: str) -> str:
    # https://www.notion.so/{workspace?}/{slug-?}{32hex}?source=...
    m = re.search(r"([0-9a-f]{32})", url.replace("-", ""))
    if not m:
        raise ValueError(f"Notion 페이지 ID를 찾을 수 없습니다: {url}")
    raw = m.group(1)
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


@dataclass
class NotionPage:
    page_id: str
    title: str
    text: str


def _rich_text(blocks: list[dict]) -> str:
    return "".join(b.get("plain_text", "") for b in blocks or [])


def _block_to_text(block: dict) -> str:
    t = block["type"]
    inner = block.get(t, {})
    rt = inner.get("rich_text") or inner.get("title")
    text = _rich_text(rt) if rt else ""

    if t == "heading_1":
        return f"# {text}"
    if t == "heading_2":
        return f"## {text}"
    if t == "heading_3":
        return f"### {text}"
    if t == "bulleted_list_item":
        return f"- {text}"
    if t == "numbered_list_item":
        return f"1. {text}"
    if t == "to_do":
        checked = "x" if inner.get("checked") else " "
        return f"- [{checked}] {text}"
    if t == "quote":
        return f"> {text}"
    if t == "callout":
        return f"💡 {text}"
    if t == "code":
        lang = inner.get("language", "")
        return f"```{lang}\n{text}\n```"
    if t == "divider":
        return "---"
    if t == "paragraph":
        return text
    return text


def _fetch_children(page_id: str, client: httpx.Client) -> list[dict]:
    blocks: list[dict] = []
    cursor: str | None = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        r = client.get(f"{API}/blocks/{page_id}/children", params=params, headers=_headers(), timeout=30.0)
        r.raise_for_status()
        data = r.json()
        blocks.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return blocks


def fetch_page(url_or_id: str) -> NotionPage:
    page_id = url_or_id if "-" in url_or_id and len(url_or_id) == 36 else page_id_from_url(url_or_id)
    with httpx.Client() as client:
        meta = client.get(f"{API}/pages/{page_id}", headers=_headers(), timeout=30.0)
        meta.raise_for_status()
        props = meta.json().get("properties", {})
        title = "제목 없음"
        for v in props.values():
            if v.get("type") == "title":
                title = _rich_text(v.get("title", [])) or title
                break

        blocks = _fetch_children(page_id, client)
        lines: list[str] = []
        for b in blocks:
            line = _block_to_text(b)
            if line:
                lines.append(line)
        return NotionPage(page_id=page_id, title=title, text="\n\n".join(lines).strip())


def _md_to_blocks(markdown: str) -> list[dict]:
    """간단 markdown → Notion blocks."""
    out: list[dict] = []

    def para(text: str, block_type: str = "paragraph") -> dict:
        # Notion rich_text 최대 길이 2000자 — 청크 분할
        chunks = [text[i : i + 1800] for i in range(0, len(text), 1800)] or [""]
        rt = [{"type": "text", "text": {"content": c}} for c in chunks]
        return {"object": "block", "type": block_type, block_type: {"rich_text": rt}}

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("### "):
            out.append(para(line[4:], "heading_3"))
        elif line.startswith("## "):
            out.append(para(line[3:], "heading_2"))
        elif line.startswith("# "):
            out.append(para(line[2:], "heading_1"))
        elif line.startswith(("- ", "* ")):
            out.append(para(line[2:], "bulleted_list_item"))
        elif line == "---":
            out.append({"object": "block", "type": "divider", "divider": {}})
        else:
            out.append(para(line))
    return out


def create_result_page(
    *,
    parent_page_id: str,
    title: str,
    body_md: str,
    ideas_md: str = "",
    source_url: str = "",
    tags: list[str] | None = None,
) -> str:
    """결과 페이지를 parent 아래에 생성하고 URL 반환."""
    parent_id = parent_page_id if "-" in parent_page_id else page_id_from_url(parent_page_id)

    children = _md_to_blocks(body_md)

    if source_url:
        children.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "🔗"},
                    "rich_text": [
                        {"type": "text", "text": {"content": "원고 출처: "}},
                        {
                            "type": "text",
                            "text": {"content": source_url, "link": {"url": source_url}},
                        },
                    ],
                },
            }
        )
    if tags:
        children.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": "🏷 " + ", ".join(tags)}}]
                },
            }
        )
    if ideas_md:
        children.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "추가 콘텐츠 아이템"}}]},
            }
        )
        children.extend(_md_to_blocks(ideas_md))

    payload = {
        "parent": {"page_id": parent_id},
        "properties": {
            "title": {"title": [{"type": "text", "text": {"content": title}}]}
        },
        "children": children[:100],  # API 단일 호출 100 블록 제한
    }
    with httpx.Client() as client:
        r = client.post(f"{API}/pages", json=payload, headers=_headers(), timeout=60.0)
        if r.status_code >= 400:
            raise RuntimeError(f"Notion 페이지 생성 실패: {r.status_code} {r.text}")
        data = r.json()
        # 나머지 블록 append
        rest = children[100:]
        page_id = data["id"]
        for i in range(0, len(rest), 100):
            ar = client.patch(
                f"{API}/blocks/{page_id}/children",
                json={"children": rest[i : i + 100]},
                headers=_headers(),
                timeout=60.0,
            )
            ar.raise_for_status()
        return data.get("url", f"https://www.notion.so/{page_id.replace('-', '')}")
