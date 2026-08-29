"""
Fetches the latest issue of মাসিক ফুলকুঁড়ি from the official WordPress REST API,
extracts the PDF link from the embedded flipbook widget, and downloads it.

Designed to run inside GitHub Actions on a schedule, but works fine locally too:
    pip install requests
    python fetch_magazine.py
"""

import json
import html
import re
import pathlib
import sys

import requests

API_URL = (
    "https://monthlyphulkuri.com/wp-json/wp/v2/posts"
    "?categories=80&per_page=1&orderby=date&order=desc"
)

ISSUES_DIR = pathlib.Path("issues")
STATE_FILE = pathlib.Path("last_issue.json")


def fetch_latest_post():
    resp = requests.get(API_URL, timeout=20)
    resp.raise_for_status()
    posts = resp.json()
    if not posts:
        raise RuntimeError("No e-book posts returned by the API")
    return posts[0]


def extract_pdf_url(content_html: str) -> str | None:
    match = re.search(r'data-flipbook-options="([^"]+)"', content_html)
    if not match:
        return None
    decoded = html.unescape(match.group(1))
    options = json.loads(decoded)
    return options.get("pdfUrl")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def load_last_seen_id():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text()).get("post_id")
    return None


def save_state(post_id: int, title: str, pdf_url: str, date: str):
    STATE_FILE.write_text(
        json.dumps(
            {"post_id": post_id, "title": title, "pdf_url": pdf_url, "date": date},
            ensure_ascii=False,
            indent=2,
        )
    )


def main():
    post = fetch_latest_post()
    post_id = post["id"]
    title = strip_tags(post["title"]["rendered"])
    date = post["date"]
    content_html = post["content"]["rendered"]

    pdf_url = extract_pdf_url(content_html)
    if not pdf_url:
        print("Could not find a PDF URL in the latest post. Nothing downloaded.")
        sys.exit(1)

    print(f"Latest issue found: {title} ({date})")
    print(f"PDF URL: {pdf_url}")

    last_seen_id = load_last_seen_id()
    if post_id == last_seen_id:
        print("No new issue since last run. Skipping download.")
        return

    ISSUES_DIR.mkdir(exist_ok=True)
    pdf_data = requests.get(pdf_url, timeout=60).content

    # Use the post date to name the file, e.g. issues/2026-04.pdf
    file_stub = date[:7]  # "YYYY-MM"
    dest = ISSUES_DIR / f"{file_stub}.pdf"
    dest.write_bytes(pdf_data)
    print(f"Downloaded new issue to {dest} ({len(pdf_data) / 1024:.1f} KB)")

    save_state(post_id, title, pdf_url, date)
    print("State updated.")


if __name__ == "__main__":
    main()
