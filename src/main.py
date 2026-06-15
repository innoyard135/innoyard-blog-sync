"""네이버 블로그 RSS → 전문의 톤 재작성 → 초안 파일 저장."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.compliance import scan
from src.fetch_rss import fetch_posts, matches_keywords
from src.state import StateStore
from src.transform import rewrite

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path) -> dict:
    if not path.exists():
        print(f"config.yaml 이 없습니다. {path.parent / 'config.example.yaml'} 를 복사하세요.", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def slugify(title: str, post_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title[:40])
    return f"{post_id}_{safe}".strip("_")


def write_draft(
    out_dir: Path,
    *,
    slug: str,
    content: str,
    source_link: str,
    target_blog_url: str,
    author_label: str,
    warnings: list[str],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}.md"

    meta = [
        f"<!-- 원문: {source_link} -->",
        f"<!-- 대상 블로그: {target_blog_url} -->",
        f"<!-- 생성: {datetime.now().isoformat(timespec='seconds')} -->",
    ]
    if warnings:
        meta.append(f"<!-- ⚠ 검수 필요: {', '.join(warnings)} -->")

    footer = f"\n\n---\n\n*{author_label} · 본 글은 일반적인 건강 정보이며, 진단·치료는 직접 진료를 통해 결정하시기 바랍니다.*\n"

    path.write_text("\n".join(meta) + "\n\n" + content + footer, encoding="utf-8")
    return path


def run(*, dry_run: bool = False, force: bool = False, limit: int = 5) -> None:
    load_dotenv(ROOT / ".env")
    cfg = load_config(ROOT / "config.yaml")

    source = cfg["source"]
    target = cfg["target"]
    filt = cfg.get("filter", {})
    transform = cfg.get("transform", {})
    output = cfg.get("output", {})

    state = StateStore(ROOT / "state.json")
    out_dir = ROOT / output.get("dir", "output")

    posts = fetch_posts(
        source["blog_id"],
        source.get("rss_url", ""),
        limit=limit,
    )
    keywords = filt.get("keywords") or []

    processed = 0
    for post in posts:
        if not matches_keywords(post, keywords):
            continue
        if state.is_done(post.post_id) and not force:
            continue

        print(f"[대상] {post.title} ({post.link})")

        if dry_run:
            print("  → dry-run: 재작성 생략")
            continue

        draft = rewrite(
            post.title,
            post.body_text,
            model=transform.get("model", "gemini-2.5-flash"),
            max_chars=int(transform.get("max_source_chars", 12000)),
        )
        warnings = scan(draft)
        if warnings:
            print(f"  ⚠ 검수 힌트: {', '.join(warnings)}")

        path = write_draft(
            out_dir,
            slug=slugify(post.title, post.post_id),
            content=draft,
            source_link=post.link,
            target_blog_url=target.get("blog_url", ""),
            author_label=target.get("author_label", "전문의"),
            warnings=warnings,
        )
        print(f"  → 저장: {path}")

        state.mark_done(post.post_id)
        state.save()
        processed += 1

    if processed == 0:
        print("새로 처리할 글이 없습니다. (키워드 필터·이미 처리됨 확인)")
    else:
        print(f"\n완료: {processed}편 → {out_dir}/")
        print("네이버 스마트에디터 ONE에 붙여넣은 뒤 검수·발행하세요.")


def main() -> None:
    parser = argparse.ArgumentParser(description="네이버 블로그 RSS → 전문의 톤 초안 생성")
    parser.add_argument("--dry-run", action="store_true", help="수집만, LLM 호출 안 함")
    parser.add_argument("--force", action="store_true", help="이미 처리한 글도 다시 생성")
    parser.add_argument("--limit", type=int, default=5, help="RSS에서 가져올 최대 글 수")
    args = parser.parse_args()
    run(dry_run=args.dry_run, force=args.force, limit=args.limit)


if __name__ == "__main__":
    main()
