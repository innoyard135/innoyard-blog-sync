#!/usr/bin/env python3
"""텔레그램 그룹 chat_id 조회 (.env 의 TELEGRAM_BOT_TOKEN 사용)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def api(token: str, method: str, **params) -> dict:
    r = httpx.get(f"https://api.telegram.org/bot{token}/{method}", params=params, timeout=30.0)
    r.raise_for_status()
    return r.json()


def main() -> None:
    load_dotenv(ROOT / ".env")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or ":" not in token:
        print("TELEGRAM_BOT_TOKEN 이 .env 에 없거나 형식이 잘못되었습니다.", file=sys.stderr)
        sys.exit(1)

    me = api(token, "getMe")
    if not me.get("ok"):
        print(f"토큰 오류: {me}", file=sys.stderr)
        sys.exit(1)
    username = me["result"]["username"]
    print(f"\n연결된 봇: @{username}\n")

    wh = api(token, "getWebhookInfo").get("result", {})
    if wh.get("url"):
        print(f"⚠ 웹훅이 설정되어 있어 getUpdates 가 비어 있을 수 있습니다: {wh['url']}")
        print("  웹훅 삭제 중...")
        api(token, "deleteWebhook")
        print("  → deleteWebhook 완료\n")

    data = api(token, "getUpdates", timeout=10)
    if not data.get("ok"):
        print(f"Telegram API 오류: {data}", file=sys.stderr)
        sys.exit(1)

    results = data.get("result", [])
    if not results:
        print("업데이트가 없습니다. 아래를 순서대로 해보세요:\n")
        print(f"  1) 그룹 멤버에 **@{username}** 이 있는지 확인 (다른 봇이면 안 됨)")
        print("  2) BotFather → /setprivacy → 이 봇 선택 → **Disable**")
        print(f"  3) 그룹 채팅에 입력: @{username} 테스트")
        print("     (Privacy ON 이면 @멘션 없는 일반 메시지는 봇이 못 봅니다)")
        print("  4) 또는 그룹에서 봇을 제거했다가 다시 초대")
        print("  5) 이 스크립트 다시 실행: python scripts/get_chat_id.py\n")
        sys.exit(1)

    seen: dict[int, dict] = {}
    for item in results:
        msg = item.get("message") or item.get("my_chat_member") or item.get("channel_post") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is None:
            continue
        seen[cid] = {
            "id": cid,
            "title": chat.get("title") or chat.get("first_name") or "(이름 없음)",
            "type": chat.get("type", "?"),
        }

    print("=== 발견된 채팅 ===\n")
    for chat in seen.values():
        kind = "그룹/슈퍼그룹" if str(chat["id"]).startswith("-") else "1:1"
        print(f"  제목: {chat['title']}")
        print(f"  유형: {chat['type']} ({kind})")
        print(f"  TELEGRAM_CHAT_ID={chat['id']}")
        print()

    groups = [c for c in seen.values() if str(c["id"]).startswith("-")]
    if groups:
        print("→ 운영 그룹이면 위 음수 ID 를 .env 의 TELEGRAM_CHAT_ID= 에 넣으세요.\n")
    else:
        print("→ 그룹 ID(음수)가 없습니다. 그룹에 @멘션 후 다시 실행하세요.\n")


if __name__ == "__main__":
    main()
