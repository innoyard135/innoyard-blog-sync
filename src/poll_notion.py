"""노션 DB 폴링 → 재가공 → Word → Telegram."""

from __future__ import annotations

import argparse
import sys

import yaml
from dotenv import load_dotenv

from src.notion_db import query_ready_rows, mark_sent
from src.pipeline import ROOT, _process_and_dispatch, load_config


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="노션 DB 폴링 (게시 준비 + 대기)")
    parser.add_argument("--dry-run", action="store_true", help="조회만, 발송 안 함")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="발송 건수 제한 (기본 0=무제한, 1 이상이면 가장 오래된 N건만)",
    )
    args = parser.parse_args()

    cfg = load_config()
    notion_cfg = cfg.get("notion", {})
    db_id = notion_cfg.get("database_id", "").strip()
    if not db_id:
        print("config.yaml 의 notion.database_id 를 설정하세요.", file=sys.stderr)
        print("가이드: docs/step6-notion-db-setup.md", file=sys.stderr)
        sys.exit(1)

    rows = query_ready_rows(
        db_id,
        prop_ready=notion_cfg.get("prop_ready", "게시준비"),
        prop_status=notion_cfg.get("prop_status", "상태"),
        status_pending=notion_cfg.get("status_pending", "대기"),
    )
    if not rows:
        print("처리할 원고 없음 (게시 준비 ☑ + 상태=대기 인 행이 없음)")
        return

    total = len(rows)
    if args.limit > 0:
        rows = rows[: args.limit]
        print(f"대기 원고 {total}건 — 이번 회차 {len(rows)}건 발송 (가장 오래된 순)")
    else:
        print(f"대기 원고 {total}건")
    for row in rows:
        print(f"  - {row.title} ({row.page_id})")
        if not row.body.strip():
            print("    ⚠ 본문 비어 있음 — 페이지 본문을 채운 뒤 다시 실행")
            continue
        if args.dry_run:
            continue

        _process_and_dispatch(
            title=row.title,
            body=row.body,
            cfg=cfg,
            source_label=f"notion-db:{row.page_id}",
            source_url=f"https://www.notion.so/{row.page_id.replace('-', '')}",
            skip_notify=False,
            image_urls=row.image_urls,
        )
        mark_sent(
            row.page_id,
            prop_status=notion_cfg.get("prop_status", "상태"),
            status_done=notion_cfg.get("status_done", "발송완료"),
            prop_sent_date=notion_cfg.get("prop_sent_date", "telegram 발송일"),
        )
        print(f"    → 발송완료 처리")


if __name__ == "__main__":
    main()
