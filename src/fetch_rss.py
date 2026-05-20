"""네이버 블로그 RSS 수집."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime

import feedparser
import httpx
from bs4 import BeautifulSoup


@dataclass
class BlogPost:
    post_id: str
    title: str
    link: str
    published: datetime | None
    body_text: str
    body_html: str


def rss_url_for(blog_id: str, override: str = "") -> str:
    if override.strip():
        return override.strip()
    return f"https://rss.blog.naver.com/{blog_id}.xml"


def _strip_html(raw: str) -> str:
    soup = BeautifulSoup(raw or "", "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _entry_id(entry: feedparser.FeedParserDict) -> str:
    link = entry.get("link", "")
    # https://blog.naver.com/PostView.naver?blogId=x&logNo=123
    m = re.search(r"logNo=(\d+)", link)
    if m:
        return m.group(1)
    return entry.get("id", link) or link


def fetch_posts(blog_id: str, rss_override: str = "", limit: int = 20) -> list[BlogPost]:
    url = rss_url_for(blog_id, rss_override)
    resp = httpx.get(url, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)

    posts: list[BlogPost] = []
    for entry in feed.entries[:limit]:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6])

        raw_html = ""
        if entry.get("content"):
            raw_html = entry.content[0].get("value", "")
        elif entry.get("summary"):
            raw_html = entry.summary

        title = html.unescape(entry.get("title", "제목 없음"))
        posts.append(
            BlogPost(
                post_id=_entry_id(entry),
                title=title,
                link=entry.get("link", ""),
                published=published,
                body_text=_strip_html(raw_html),
                body_html=raw_html,
            )
        )
    return posts


def matches_keywords(post: BlogPost, keywords: list[str]) -> bool:
    if not keywords:
        return True
    hay = f"{post.title}\n{post.body_text}".lower()
    return any(k.lower() in hay for k in keywords)
