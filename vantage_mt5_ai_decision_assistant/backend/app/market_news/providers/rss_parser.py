"""RSS / Atom feed parsing — stdlib only (no feedparser dependency)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree as ET

_STRIP_TAGS = re.compile(r"<[^>]+>")


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def _strip_html(text: str) -> str:
    return _STRIP_TAGS.sub(" ", text).strip()


def _parse_published(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def _parse_rss_channel(channel: ET.Element, *, feed_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in channel.findall("item"):
        title = _text(item.find("title"))
        if not title:
            continue
        link = _text(item.find("link"))
        guid = _text(item.find("guid")) or link or title
        published = _parse_published(_text(item.find("pubDate")) or _text(item.find("date")))
        summary = _strip_html(_text(item.find("description")) or _text(item.find("summary")))
        rows.append(
            {
                "headline": title,
                "summary": summary,
                "published_at": published,
                "raw_url": link,
                "external_id": guid,
                "feed_url": feed_url,
            }
        )
    return rows


def _parse_atom_feed(root: ET.Element, *, feed_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        title = _text(entry.find("{http://www.w3.org/2005/Atom}title"))
        if not title:
            continue
        link_el = entry.find("{http://www.w3.org/2005/Atom}link")
        link = link_el.get("href") if link_el is not None else ""
        entry_id = _text(entry.find("{http://www.w3.org/2005/Atom}id")) or link or title
        published = _parse_published(
            _text(entry.find("{http://www.w3.org/2005/Atom}published"))
            or _text(entry.find("{http://www.w3.org/2005/Atom}updated"))
        )
        summary = _strip_html(
            _text(entry.find("{http://www.w3.org/2005/Atom}summary"))
            or _text(entry.find("{http://www.w3.org/2005/Atom}content"))
        )
        rows.append(
            {
                "headline": title,
                "summary": summary,
                "published_at": published,
                "raw_url": link,
                "external_id": entry_id,
                "feed_url": feed_url,
            }
        )
    return rows


def parse_feed_xml(content: bytes, *, feed_url: str) -> list[dict[str, Any]]:
    """Parse RSS 2.0 or Atom XML into normalized headline dicts."""
    root = ET.fromstring(content)
    tag = _local(root.tag).lower()
    if tag == "rss":
        channel = root.find("channel")
        if channel is None:
            return []
        return _parse_rss_channel(channel, feed_url=feed_url)
    if tag == "feed":
        return _parse_atom_feed(root, feed_url=feed_url)
    if _local(root.tag).lower() == "channel":
        return _parse_rss_channel(root, feed_url=feed_url)
    return []
