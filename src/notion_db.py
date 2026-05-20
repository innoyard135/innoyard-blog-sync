"""Notion 데이터베이스 폴링 — 게시 준비 + 대기 행 처리."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from src.notion_client import _block_to_text, _fetch_children, _headers, _rich_text

API = "https://api.notion.com/v1"


@dataclass
class NotionManuscriptRow:
    page_id: str
    title: str
    body: str


def _normalize_db_id(db_id: str) -> str:
    raw = db_id.replace("-", "").strip()
    if len(raw) != 32:
        return db_id.strip()
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


def _prop_checkbox(prop: dict) -> bool:
    return prop.get("checkbox", False)


def _prop_select(prop: dict) -> str:
    sel = prop.get("select")
    return sel.get("name", "") if sel else ""


def _prop_title(prop: dict) -> str:
    return _rich_text(prop.get("title", []))


def _detect_status_type(db_id: str, prop_name: str, client: httpx.Client) -> str:
    """상태 컬럼이 'select' 인지 'status' 인지 자동 감지."""
    r = client.get(f"{API}/databases/{db_id}", headers=_headers(), timeout=30.0)
    r.raise_for_status()
    props = r.json().get("properties", {})
    prop = props.get(prop_name) or {}
    return prop.get("type", "select")


def query_ready_rows(
    database_id: str,
    *,
    prop_ready: str = "게시준비",
    prop_status: str = "상태",
    status_pending: str = "대기",
) -> list[NotionManuscriptRow]:
    """게시준비=True, 상태=대기 인 행 목록."""
    db_id = _normalize_db_id(database_id)
    rows: list[NotionManuscriptRow] = []
    with httpx.Client() as client:
        status_type = _detect_status_type(db_id, prop_status, client)
        if status_type not in ("select", "status"):
            status_type = "select"
        payload = {
            "filter": {
                "and": [
                    {"property": prop_ready, "checkbox": {"equals": True}},
                    {"property": prop_status, status_type: {"equals": status_pending}},
                ]
            }
        }
        r = client.post(
            f"{API}/databases/{db_id}/query",
            json=payload,
            headers=_headers(),
            timeout=60.0,
        )
        if r.status_code >= 400:
            raise RuntimeError(
                f"Notion query 실패 ({r.status_code}): {r.text}"
            )
        data = r.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            title = ""
            for v in props.values():
                if v.get("type") == "title":
                    title = _prop_title(v)
                    break
            page_id = page["id"]
            blocks = _fetch_children(page_id, client)
            lines = [_block_to_text(b) for b in blocks]
            body = "\n\n".join(l for l in lines if l).strip()
            rows.append(NotionManuscriptRow(page_id=page_id, title=title or "제목 없음", body=body))
    return rows


def mark_sent(
    page_id: str,
    *,
    prop_status: str = "상태",
    status_done: str = "발송완료",
    prop_sent_date: str = "telegram 발송일",
) -> None:
    """상태=발송완료 (+ telegram 발송일 컬럼 있으면 오늘 날짜)."""
    today = datetime.now(timezone.utc).date().isoformat()
    with httpx.Client() as client:
        for payload in (
            {
                "properties": {
                    prop_status: {"status": {"name": status_done}},
                    prop_sent_date: {"date": {"start": today}},
                }
            },
            {
                "properties": {
                    prop_status: {"select": {"name": status_done}},
                    prop_sent_date: {"date": {"start": today}},
                }
            },
            {"properties": {prop_status: {"status": {"name": status_done}}}},
            {"properties": {prop_status: {"select": {"name": status_done}}}},
        ):
            r = client.patch(
                f"{API}/pages/{page_id}",
                json=payload,
                headers=_headers(),
                timeout=30.0,
            )
            if r.status_code < 400:
                return
        r.raise_for_status()
