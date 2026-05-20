"""Nano Banana (Gemini 2.5 Flash Image) — 원본 이미지 → 새 이미지 변환.

원본을 reference 로 사용해 한국인 아기·자연스러운 인물 톤의 사진형 이미지를 생성합니다.
실패 또는 안전성 거부 시 그 항목만 스킵하고 다음으로 진행합니다.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-flash-image-preview"

DEFAULT_STYLE_PROMPT = (
    "Recreate this scene as a fresh editorial-style photograph of a Korean baby. "
    "The baby should look real and natural — soft daylight, natural skin tone, "
    "gentle expression, clean background, warm and friendly atmosphere. "
    "Keep the same general composition and concept of the reference image, "
    "but render a different baby (do not copy any identifiable face). "
    "No text, no watermark, no logos, no medical product branding."
)


@dataclass
class GeneratedImage:
    index: int
    source_url: str
    out_path: Path
    mime_type: str


def _download(url: str, client: httpx.Client) -> bytes:
    r = client.get(url, timeout=60.0, follow_redirects=True)
    r.raise_for_status()
    return r.content


def _guess_mime(data: bytes, fallback: str = "image/png") -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return fallback


def _ext_from_mime(mime: str) -> str:
    if "png" in mime:
        return ".png"
    if "jpeg" in mime or "jpg" in mime:
        return ".jpg"
    if "webp" in mime:
        return ".webp"
    return ".png"


def generate_images_from_sources(
    source_urls: list[str],
    out_dir: Path,
    *,
    style_prompt: str = DEFAULT_STYLE_PROMPT,
    model: str = DEFAULT_MODEL,
    max_count: int = 20,
    api_key: str | None = None,
) -> list[GeneratedImage]:
    """원본 URL 목록을 받아 같은 수만큼 새 이미지를 생성, 로컬에 저장한 뒤 경로 반환."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("  ⚠ GEMINI_API_KEY 미설정 — 이미지 생성을 건너뜁니다.")
        return []
    if not source_urls:
        return []

    urls = source_urls[:max_count]
    if len(source_urls) > max_count:
        print(
            f"  ⚠ 이미지 {len(source_urls)}장 중 {max_count}장만 처리 (config image_gen.max_count)"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    out: list[GeneratedImage] = []

    with httpx.Client() as client:
        for i, url in enumerate(urls, start=1):
            try:
                src_bytes = _download(url, client)
            except Exception as e:
                print(f"  ⚠ 이미지 {i} 다운로드 실패: {e}")
                continue
            src_mime = _guess_mime(src_bytes)
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": style_prompt},
                            {
                                "inline_data": {
                                    "mime_type": src_mime,
                                    "data": base64.b64encode(src_bytes).decode(),
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
            }
            try:
                r = client.post(
                    f"{GEMINI_API_BASE}/{model}:generateContent",
                    params={"key": api_key},
                    json=payload,
                    timeout=180.0,
                )
            except Exception as e:
                print(f"  ⚠ 이미지 {i} Gemini 호출 오류: {e}")
                continue
            if r.status_code >= 400:
                print(f"  ⚠ 이미지 {i} Gemini 실패 ({r.status_code}): {r.text[:200]}")
                continue

            data = r.json()
            new_bytes: bytes | None = None
            new_mime = "image/png"
            for part in (
                data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            ):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    new_bytes = base64.b64decode(inline["data"])
                    new_mime = inline.get("mimeType") or inline.get("mime_type", new_mime)
                    break
            if not new_bytes:
                print(f"  ⚠ 이미지 {i} Gemini 응답에 이미지 없음 (safety 차단 가능)")
                continue

            out_path = out_dir / f"gen_{i:02d}{_ext_from_mime(new_mime)}"
            out_path.write_bytes(new_bytes)
            out.append(
                GeneratedImage(index=i, source_url=url, out_path=out_path, mime_type=new_mime)
            )
            print(f"  → 이미지 {i} 생성: {out_path.name}")

    return out
