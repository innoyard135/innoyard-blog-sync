"""원고 → 재가공 → Word(메인 + 아이템) → zip → 메신저."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.compliance import scan
from src.export_docx import export_docx, safe_filename
from src.ideas_format import ideas_to_markdown
from src.manuscript import list_manuscripts, load_manuscript
from src.notify import notify
from src.state import StateStore
from src.transform_pipeline import process_manuscript, process_sub_topic

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_VERSION = "2026-05-20-bundle-v2"


def load_config() -> dict:
    path = ROOT / "config.yaml"
    if not path.exists():
        print("config.yaml 이 없습니다. config.example.yaml 을 복사하세요.", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def file_fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.name.encode())
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


class ManuscriptState(StateStore):
    """state.json 에 manuscript 해시 저장."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._fingerprints: set[str] = set()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self._fingerprints = set(data.get("processed_manuscripts", []))

    def is_done_file(self, fp: str) -> bool:
        return fp in self._fingerprints

    def mark_file(self, fp: str) -> None:
        self._fingerprints.add(fp)
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "processed_post_ids": sorted(self._ids),
            "processed_manuscripts": sorted(self._fingerprints),
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _process_and_dispatch(
    *,
    title: str,
    body: str,
    cfg: dict,
    source_label: str,
    source_url: str = "",
    skip_notify: bool = False,
    image_urls: list[str] | None = None,
) -> tuple[Path, str | None]:
    transform = cfg.get("transform", {})
    output = cfg.get("output", {})
    target = cfg.get("target", {})
    notify_cfg = cfg.get("notify", {})
    notion_cfg = cfg.get("notion", {})
    image_cfg = cfg.get("image_gen", {})

    print(f"  [pipeline {PIPELINE_VERSION}]")

    result = process_manuscript(
        title,
        body,
        model=transform.get("model", "claude-sonnet-4-20250514"),
        max_chars=int(transform.get("max_source_chars", 12000)),
        source_path=source_label,
    )
    print(f"  → 메인 완료, 아이템 후보 {len(result.ideas)}개 (최대 2개만 확장)")

    warnings = scan(result.body + " " + result.title)
    if warnings:
        print(f"  ⚠ 검수 힌트: {', '.join(warnings)}")

    image_paths: list[Path] = []
    if image_cfg.get("enabled") and image_urls:
        from src.image_gen import (
            DEFAULT_MODEL,
            DEFAULT_STYLE_PROMPT,
            generate_images_from_sources,
        )

        gen_dir = ROOT / output.get("image_dir", "output/images") / safe_filename(result.title)
        generated = generate_images_from_sources(
            image_urls,
            gen_dir,
            style_prompt=image_cfg.get("style_prompt") or DEFAULT_STYLE_PROMPT,
            model=image_cfg.get("model") or DEFAULT_MODEL,
            max_count=int(image_cfg.get("max_count", 20)),
        )
        image_paths = [g.out_path for g in generated]
        if image_paths:
            print(f"  → 생성 이미지 {len(image_paths)}장")

    docx_dir = ROOT / output.get("docx_dir", "output/docx")
    stamp = datetime.now().strftime("%Y%m%d")
    base_name = f"{stamp}_{safe_filename(result.title)}"
    bundle_dir = docx_dir / base_name
    bundle_dir.mkdir(parents=True, exist_ok=True)

    author_label = target.get("author_label", "성형외과·소아과 전문의")
    docx_path = export_docx(
        result,
        bundle_dir / f"00_메인_{safe_filename(result.title)}.docx",
        author_label=author_label,
        image_paths=image_paths,
    )
    print(f"  → Word(메인): {docx_path.name}")

    sub_cfg = cfg.get("sub_topics", {}) or {}
    sub_enabled = bool(sub_cfg.get("enabled", True))
    sub_count = int(sub_cfg.get("count", 2))
    sub_model = sub_cfg.get("model") or transform.get("model", "claude-sonnet-4-20250514")
    print(f"  → sub_topics: enabled={sub_enabled}, count={sub_count}")
    sub_paths: list[Path] = []
    if sub_enabled and sub_count > 0 and result.ideas:
        for i, idea in enumerate(result.ideas[:sub_count], start=1):
            try:
                sub_result = process_sub_topic(
                    idea,
                    parent_title=result.title,
                    model=sub_model,
                    source_path=source_label,
                )
            except Exception as e:
                print(f"  ⚠ 아이템 {i} 원고 생성 실패: {e}")
                continue
            sub_path = export_docx(
                sub_result,
                bundle_dir / f"{i:02d}_아이템_{safe_filename(sub_result.title)}.docx",
                author_label=author_label,
            )
            sub_paths.append(sub_path)
            print(f"  → Word(아이템 {i}): {sub_path.name}")

    if sub_enabled and sub_count > 0 and result.ideas and not sub_paths:
        print("  ⚠ 아이템 단독 원고 0건 — 메인+README 만 zip 전송 (API 오류 확인)")

    # README.txt for bundle
    readme = bundle_dir / "README.txt"
    readme.write_text(
        f"제목: {result.title}\n"
        f"생성일: {stamp}\n"
        f"작성 관점: {author_label}\n\n"
        f"구성:\n"
        f"- 00_메인_*.docx — 재가공 본문 + 추가 콘텐츠 아이템 목록\n"
        + "".join(f"- {i+1:02d}_아이템_*.docx — 아이템 {i+1} 단독 원고\n" for i in range(len(sub_paths)))
        + "\n검수 후 게시하세요. 본 자료는 일반 정보이며 진단·치료는 직접 진료를 통해 결정됩니다.\n",
        encoding="utf-8",
    )

    # zip 묶기
    zip_path = docx_dir / f"{base_name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in [docx_path, *sub_paths, readme]:
            z.write(p, arcname=f"{base_name}/{p.name}")
    print(f"  → zip: {zip_path}")

    notion_url: str | None = None
    parent_id = notion_cfg.get("result_parent_page_id", "")
    if notion_cfg.get("create_result_page") and parent_id:
        from src.notion_client import create_result_page

        ideas_md = ideas_to_markdown(result.ideas)
        notion_url = create_result_page(
            parent_page_id=parent_id,
            title=result.title,
            body_md=result.body,
            ideas_md=ideas_md,
            source_url=source_url,
            tags=result.tags,
        )
        print(f"  → Notion: {notion_url}")

    provider = notify_cfg.get("provider", "none")
    if not skip_notify and provider != "none":
        sent = notify(
            result,
            zip_path,
            provider=provider,
            telegram_bot_token=notify_cfg.get("telegram_bot_token", ""),
            telegram_chat_id=notify_cfg.get("telegram_chat_id", ""),
            kakao_access_token=notify_cfg.get("kakao_access_token", ""),
            notion_page_url=notion_url or "",
            sub_count=len(sub_paths),
            pipeline_version=PIPELINE_VERSION,
        )
        print(f"  → 전송: {', '.join(sent)} ({zip_path.name})")

    return docx_path, notion_url


def run_file(
    path: Path,
    cfg: dict,
    *,
    force: bool = False,
    skip_notify: bool = False,
) -> Path | None:
    ms_cfg = cfg.get("manuscripts", {})

    state = ManuscriptState(ROOT / "state.json")
    fp = file_fingerprint(path)
    if state.is_done_file(fp) and not force:
        print(f"[건너뜀] 이미 처리됨: {path.name}")
        return None

    title, body = load_manuscript(path)
    print(f"[처리] {path.name} → «{title}»")

    docx_path, _ = _process_and_dispatch(
        title=title,
        body=body,
        cfg=cfg,
        source_label=str(path.name),
        skip_notify=skip_notify,
    )

    if ms_cfg.get("move_after_process", True):
        done_dir = ROOT / ms_cfg.get("processed_dir", "manuscripts/_done")
        done_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d")
        dest = done_dir / f"{stamp}_{path.name}"
        shutil.move(str(path), str(dest))
        print(f"  → 원고 이동: {dest}")

    state.mark_file(fp)
    return docx_path


def run_notion(url: str, cfg: dict, *, skip_notify: bool = False) -> Path:
    from src.notion_client import fetch_page

    page = fetch_page(url)
    print(f"[Notion] {page.title} ({page.page_id})")
    if not page.text.strip():
        raise RuntimeError("Notion 페이지 본문이 비어 있습니다. Integration이 페이지에 연결됐는지 확인하세요.")

    docx_path, _ = _process_and_dispatch(
        title=page.title,
        body=page.text,
        cfg=cfg,
        source_label=f"notion:{page.page_id}",
        source_url=url,
        skip_notify=skip_notify,
    )
    return docx_path


def run_batch(cfg: dict, *, force: bool = False, skip_notify: bool = False) -> int:
    ms_dir = ROOT / cfg.get("manuscripts", {}).get("dir", "manuscripts")
    count = 0
    for path in list_manuscripts(ms_dir):
        if run_file(path, cfg, force=force, skip_notify=skip_notify):
            count += 1
    return count


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="원고 재가공 → Word → 텔레그램/카카오 + Notion")
    parser.add_argument("--file", type=str, help="특정 원고 파일 경로")
    parser.add_argument("--notion-url", type=str, help="Notion 원고 페이지 URL")
    parser.add_argument("--force", action="store_true", help="이미 처리한 원고도 다시 실행")
    parser.add_argument("--no-notify", action="store_true", help="메신저 전송 생략")
    parser.add_argument("--no-move", action="store_true", help="원고를 _done 으로 이동하지 않음")
    args = parser.parse_args()

    cfg = load_config()
    if args.no_move:
        cfg.setdefault("manuscripts", {})["move_after_process"] = False

    if args.notion_url:
        run_notion(args.notion_url, cfg, skip_notify=args.no_notify)
        return

    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = ROOT / path
        run_file(path, cfg, force=args.force, skip_notify=args.no_notify)
    else:
        n = run_batch(cfg, force=args.force, skip_notify=args.no_notify)
        if n == 0:
            print(f"처리할 원고가 없습니다. `{cfg.get('manuscripts', {}).get('dir', 'manuscripts')}/` 에 .md/.txt/.docx 를 넣으세요.")


if __name__ == "__main__":
    main()
