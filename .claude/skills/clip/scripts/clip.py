#!/usr/bin/env python3
"""clip.py — create a wikip-compatible bundle from hand-fed text."""

import argparse
import json
import sys
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")


def download_image(url: str, figures_dir: Path) -> str | None:
    try:
        import httpx
        r = httpx.get(url, timeout=30, follow_redirects=True)
        r.raise_for_status()

        content_type = r.headers.get("content-type", "")
        ext_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
        }
        ext = ext_map.get(content_type.split(";")[0].strip(), "")
        if not ext:
            url_path = url.split("?")[0]
            for e in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]:
                if url_path.lower().endswith(e):
                    ext = e
                    break
            if not ext:
                ext = ".bin"

        sha = hashlib.sha256(r.content).hexdigest()[:12]
        filename = f"image_{sha}{ext}"
        (figures_dir / filename).write_bytes(r.content)
        return f"figures/{filename}"
    except Exception as e:
        print(f"Warning: failed to download {url}: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Create a wikip bundle from hand-fed text")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    parser.add_argument("--title", required=True, help="Title of the content")
    parser.add_argument("--text", help="Content text (use - for stdin)")
    parser.add_argument("--text-file", help="Read content from this file")
    parser.add_argument("--author", default="", help="Author name")
    parser.add_argument("--url", default="", help="Source URL")
    parser.add_argument("--date", default="", help="Published date YYYY-MM-DD")
    parser.add_argument("--platform", default="", help="Platform name (e.g. LinkedIn, Twitter)")
    parser.add_argument(
        "--image-url",
        action="append",
        default=[],
        dest="image_urls",
        help="Image URL to download (can repeat)",
    )
    args = parser.parse_args()

    if args.text_file:
        text = Path(args.text_file).read_text()
    elif args.text is None or args.text == "-":
        text = sys.stdin.read()
    else:
        text = args.text

    text = text.strip()
    if not text:
        print("Error: no content provided", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = out_dir / "figures"

    downloaded_images: list[tuple[str, str]] = []
    if args.image_urls:
        figures_dir.mkdir(exist_ok=True)
        for url in args.image_urls:
            path = download_image(url, figures_dir)
            if path:
                downloaded_images.append((url, path))

    fetched_at = datetime.now(timezone.utc).isoformat()

    fm: list[str] = ["---", f"title: {json.dumps(args.title)}"]
    if args.url:
        fm.append(f"url: {args.url}")
    if args.author:
        fm.append(f"author: {json.dumps(args.author)}")
    if args.date:
        fm.append(f"published: {args.date}")
    if args.platform:
        fm.append(f"site_name: {json.dumps(args.platform)}")
    fm.append(f"fetched_at: {fetched_at}")
    fm.append("---")

    body: list[str] = [f"# {args.title}", "", text]

    if downloaded_images:
        body.append("")
        for _orig, local_path in downloaded_images:
            stem = Path(local_path).stem
            body.append(f"![{stem}]({local_path})")

    content = "\n".join(fm) + "\n\n" + "\n".join(body) + "\n"
    (out_dir / "content.md").write_text(content)

    metadata = {
        "title": args.title,
        "author": args.author or None,
        "url": args.url or None,
        "published": args.date or None,
        "site_name": args.platform or None,
        "fetched_at": fetched_at,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    clip_profile = {
        "source": "clip",
        "platform": args.platform or None,
        "original_url": args.url or None,
        "images": {
            "requested": len(args.image_urls),
            "downloaded": len(downloaded_images),
        },
    }
    (out_dir / "clip_profile.json").write_text(json.dumps(clip_profile, indent=2))

    print(f"Bundle written to {out_dir}")
    print(f"  content.md: {len(text)} chars")
    print(f"  images: {len(downloaded_images)}/{len(args.image_urls)} downloaded")


if __name__ == "__main__":
    main()
