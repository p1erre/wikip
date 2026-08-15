---
name: clip
description: Create a hand-fed content bundle for wikip ingestion from pasted text and optional image URLs. Use when the user wants to add a LinkedIn post, tweet, newsletter excerpt, or any other manually copied content into the wiki — i.e., any source that can't be fetched automatically.
---

# clip

Create a wikip-compatible bundle from text pasted by the user. No fetching — the user provides the content directly. Useful for platforms that block automated access (LinkedIn, paywalled articles, etc.) or for any content the user has copied by hand.

## Inputs

- **text** (required) — the content to ingest. The user pastes it in the conversation.
- **title** (required) — a short descriptive title. Ask the user if not provided.
- **author** (optional) — author name.
- **url** (optional) — original source URL (for attribution, even if the page is unfetchable).
- **date** (optional) — published date (YYYY-MM-DD).
- **platform** (optional) — platform name, e.g. "LinkedIn", "Twitter/X", "Newsletter", "Substack".
- **image-urls** (optional, repeatable) — image URLs to download into the bundle.
- **out-dir** (required) — where to write the bundle, in the host project's bundle area (this repo's convention: `work/<corpus>/documents/clip-<slug>/`; other projects define theirs in CLAUDE.md).

## What to do

1. **Gather missing metadata.** If the user hasn't provided a title, ask. Author, URL, date, and platform are optional but improve the wiki page.

2. **Write the text to a temp file** to avoid shell quoting issues:
   ```bash
   # Use the Write tool to create /tmp/clip_content.txt with the user's text,
   # then reference it via --text-file below.
   ```

3. **Run the script:**
   ```bash
   uv run python3 "${CLAUDE_PLUGIN_ROOT}"/skills/clip/scripts/clip.py \
     --out-dir "<out_dir>" \
     --title "<title>" \
     --text-file /tmp/clip_content.txt \
     [--author "<author>"] \
     [--url "<url>"] \
     [--date "YYYY-MM-DD"] \
     [--platform "<platform>"] \
     [--image-url "<url1>"] \
     [--image-url "<url2>"]
   ```

4. **Report**: confirm the bundle was written, note any images that failed to download.

5. **Offer to run wikip** — ask the user which wiki/corpus to ingest into, then run the `wikip` skill on the new bundle.

## Output bundle

```
<out-dir>/
  content.md         YAML frontmatter + body text (verbatim from user)
  metadata.json      {title, author, url, published, site_name, fetched_at}
  clip_profile.json  {source:"clip", platform, original_url, images:{requested, downloaded}}
  figures/           downloaded images (only if --image-url used)
```

wikip detects this bundle via the presence of `clip_profile.json`.

## Out-dir naming

Default to `work/<corpus>/documents/clip-<slug>/` where `<slug>` is a kebab-case version of the title (max ~60 chars). Ask the user for the corpus name if not obvious from context.

## Notes

- Text is taken verbatim — no cleaning, no reformatting. What the user pastes is what goes in.
- Images are downloaded at bundle-creation time. If a URL expires later, the local copy is all that remains.
- This skill is intentionally minimal: its job is to get hand-fed content into the same bundle shape as the other fetch skills so wikip treats all sources uniformly.
