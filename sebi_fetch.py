#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, re
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dparser

RSS_URL = "https://www.sebi.gov.in/sebirss.xml"
UA = "Mozilla/5.0 (compatible; SEBI-RSS-PDF-Fetcher/1.0)"
TIMEOUT = 30


def extract_pdf_links(page_url: str):
    headers = {"User-Agent": UA}
    r = requests.get(page_url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    out = set()

    for tag in soup.find_all(["a", "iframe", "embed", "object"]):
        for attr in ("href", "src", "data"):
            u = tag.get(attr)
            if u and ".pdf" in u.lower():
                out.add(urljoin(page_url, u))

    for m in re.findall(r'https?://[^\s\'"]+?\.pdf', html, re.IGNORECASE):
        out.add(m)

    for m in re.findall(r'["\'](/[^"\']+?\.pdf)["\']', html, re.IGNORECASE):
        out.add(urljoin(page_url, m))

    return sorted(out)


def to_utc(dt_str: str):
    if not dt_str:
        return None
    try:
        dt = dparser.parse(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def main():
    feed = feedparser.parse(RSS_URL)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=3, minutes=10)  # ~3-hour window

    fresh = []
    for e in feed.entries[:25]:
        title = (e.get("title") or "").strip()
        link = (e.get("link") or "").strip()
        published = (e.get("published") or e.get("updated") or "").strip()
        dt = to_utc(published)
        if dt and dt >= window_start:
            pdfs = []
            if link:
                try:
                    pdfs = extract_pdf_links(link)
                except Exception:
                    pdfs = []
            fresh.append({
                "title": title,
                "published": dt.isoformat(),
                "page_link": link,
                "pdf_links": pdfs
            })

    result = {"count": len(fresh), "items": fresh}
    with open("out.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Build nice HTML for email
    parts = ["<h2>SEBI: New items in the last 3 hours</h2>", "<ol>"]
    for it in fresh:
        parts.append("<li>")
        parts.append(f"<div><strong>{it['title']}</strong></div>")
        parts.append(f"<div><b>Date (UTC):</b> {it['published']}</div>")
        parts.append(f"<div><b>Page:</b> <a href='{it['page_link']}'>{it['page_link']}</a></div>")
        if it["pdf_links"]:
            parts.append("<div><b>PDFs:</b><ul>")
            for p in it["pdf_links"]:
                parts.append(f"<li><a href='{p}'>{p}</a></li>")
            parts.append("</ul></div>")
        else:
            parts.append("<div><i>No PDF links detected.</i></div>")
        parts.append("</li>")
    parts.append("</ol>")
    with open("out.html", "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


if __name__ == "__main__":
    main()
