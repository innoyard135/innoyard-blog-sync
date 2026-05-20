"""텔레그램·카카오 알림."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from src.models import PipelineResult


def format_caption(result: PipelineResult, *, docx_name: str) -> str:
    lines = [
        f"📄 {result.title}",
        f"파일: {docx_name}",
        "",
        "💡 추가 콘텐츠 아이템 (요약)",
    ]
    for i, idea in enumerate(result.ideas[:8], start=1):
        hook = idea.hook or idea.topic
        lines.append(f"{i}. {hook}")
    if len(result.ideas) > 8:
        lines.append(f"... 외 {len(result.ideas) - 8}건 (Word 본문 참고)")
    if result.tags:
        lines.append("")
        lines.append("🏷 " + ", ".join(result.tags[:6]))
    return "\n".join(lines)[:1024]  # Telegram caption limit


def send_telegram(
    file_path: Path,
    caption: str,
    *,
    bot_token: str,
    chat_id: str,
) -> None:
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        raise RuntimeError("TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 가 필요합니다.")

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with file_path.open("rb") as f:
        resp = httpx.post(
            url,
            data={"chat_id": chat, "caption": caption},
            files={"document": (file_path.name, f)},
            timeout=120.0,
        )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram 오류: {data}")


def send_kakao_memo(
    text: str,
    *,
    access_token: str,
    link_url: str = "https://innoband.co.kr",
    button_title: str = "노션에서 열기",
) -> None:
    """카카오톡 '나에게 보내기' — 텍스트 + 링크 카드 (파일 첨부 API 없음)."""
    token = access_token or os.environ.get("KAKAO_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("KAKAO_ACCESS_TOKEN 이 필요합니다.")

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    template = {
        "object_type": "text",
        "text": text[:2000],
        "link": {
            "web_url": link_url,
            "mobile_web_url": link_url,
        },
        "button_title": button_title,
    }
    import json

    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=30.0,
    )
    resp.raise_for_status()


def notify(
    result: PipelineResult,
    docx_path: Path,
    *,
    provider: str,
    telegram_bot_token: str = "",
    telegram_chat_id: str = "",
    kakao_access_token: str = "",
    notion_page_url: str = "",
) -> list[str]:
    """provider: telegram | kakao | both | none"""
    sent: list[str] = []
    caption = format_caption(result, docx_name=docx_path.name)

    if provider in ("telegram", "both"):
        send_telegram(
            docx_path,
            caption,
            bot_token=telegram_bot_token,
            chat_id=telegram_chat_id,
        )
        sent.append("telegram")

    if provider in ("kakao", "both"):
        if notion_page_url:
            kakao_text = (
                f"[두상교정 원고 재가공 완료]\n{result.title}\n\n"
                f"{caption}\n\n"
                f"📝 노션에서 결과 열기:\n{notion_page_url}"
            )
            send_kakao_memo(
                kakao_text,
                access_token=kakao_access_token,
                link_url=notion_page_url,
                button_title="노션에서 열기",
            )
        else:
            kakao_text = (
                f"[두상교정 원고 재가공]\n{result.title}\n\n"
                f"{caption}\n\n"
                f"※ 카카오 API는 .docx 파일 첨부를 지원하지 않습니다.\n"
                f"Word 파일 경로:\n{docx_path.resolve()}"
            )
            send_kakao_memo(kakao_text, access_token=kakao_access_token)
        sent.append("kakao")

    return sent
