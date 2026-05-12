#!/usr/bin/env python3
"""Initialize a deep-research bundle directory.

Creates the working/ and sources/ subdirectories and writes a stub
deep_research_profile.json. Exits early (with code 0) if content.md
already exists so the skill is idempotent.
"""
import argparse
import json
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", help="Output bundle directory")
    args = parser.parse_args()

    out = Path(args.out_dir)

    if (out / "content.md").exists():
        print(f"[deep-research] skipping init — content.md already exists in {out}")
        sys.exit(0)

    (out / "working").mkdir(parents=True, exist_ok=True)
    (out / "sources").mkdir(parents=True, exist_ok=True)

    fetched = out / "working" / "fetched_urls.txt"
    if not fetched.exists():
        fetched.write_text("")

    profile = out / "deep_research_profile.json"
    if not profile.exists():
        profile.write_text(json.dumps({
            "iterations": 0,
            "queries_run": 0,
            "sources_fetched": 0,
            "sources_failed": 0,
            "warnings": []
        }, indent=2))

    print(f"[deep-research] initialized bundle at {out}")
    print(f"  working/          ← iteration syntheses go here")
    print(f"  sources/          ← per-source summaries go here")
    print(f"  working/fetched_urls.txt  ← dedup registry (empty)")


if __name__ == "__main__":
    main()
