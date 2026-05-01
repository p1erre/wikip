---
name: pdf-extract
description: Extract a PDF into structured markdown with LaTeX math, figures, and metadata. Detects native vs scanned PDFs and runs an escalation ladder (pymupdf → marker → nougat / ocrmypdf+tesseract) until quality clears the threshold. Outputs GFM math syntax ($...$, $$...$$). Use when converting a PDF to markdown for the wikip pipeline, when ingesting math-heavy academic papers, or when the user has a scanned PDF that needs OCR.
---

# pdf-extract

Convert a single PDF into clean markdown + extracted figures + metadata, ready for downstream wiki/booklet generation.

## Inputs

- **pdf path** (required) — absolute or workspace-relative path to a `.pdf`
- **out-dir** (required) — where to write outputs (e.g., `work/<corpus>/documents/<doc-slug>/`)
- **force-strategy** (optional, default `auto`) — `auto | pymupdf | marker | nougat | ocr`
- **quality-threshold** (optional, default `0.7`) — score below which the script escalates to the next strategy

## What to do

1. Verify the PDF file exists and is readable.
2. Run:
   ```bash
   uv run python3 .claude/skills/pdf-extract/scripts/extract.py "<pdf>" --out-dir "<out_dir>"
   ```
3. Read `<out_dir>/pdf_profile.json`. Report:
   - Detected type (`native | scanned | hybrid`) and `has_math`
   - Strategy used + final quality score
   - Any pages flagged in `needs_vision` (these need a manual vision-LLM pass)
   - Any LaTeX blocks flagged in `latex_warnings`
4. If `needs_vision` is non-empty: tell the user which pages failed and offer to do a vision pass on the rendered PNGs in `figures/_low_quality_pages/`.

## Output structure

```
<out_dir>/
  content.md                       markdown body, $...$ / $$...$$ for math
  figures/
    fig_001.png ...                figures and embedded images
    _low_quality_pages/page_NN.png (only if needs_vision is non-empty)
  metadata.json                    {source_pdf, page_count, strategies_used}
  pdf_profile.json                 detection result + per-page strategy + quality
```

## Strategy ladder

Detection picks the starting strategy; if the quality score is under threshold, escalate.

| Profile | Default | Escalation |
|---|---|---|
| native, no math | `pymupdf` | `marker` |
| native, with math | `marker` | `nougat` |
| scanned, no math | `ocr` (ocrmypdf+tesseract) | `nougat` |
| scanned, with math | `nougat` | (manual vision) |
| hybrid | `marker` | `nougat` |

`force-strategy` skips detection entirely.

## Math handling

Output uses GFM math syntax — renders correctly in GitHub, MkDocs+arithmatex, Quarto, Obsidian, Jupyter. Each `$...$` and `$$...$$` block is validated with `pylatexenc`; unparseable blocks are kept verbatim and listed in `pdf_profile.json` under `latex_warnings`.

`pymupdf` and plain `tesseract` destroy math. The strategy ladder defaults to `marker` (native math-capable) or `nougat` (academic papers, also handles scanned math) whenever `has_math` is true.

## Idempotency

Skips if `<out_dir>/content.md` and `<out_dir>/pdf_profile.json` both exist. To force re-extraction, delete `<out_dir>/` first or pass `--force-strategy <name>` to override the cached output.

## Failure modes

- **Encrypted PDF**: hard error, no auto-decrypt.
- **All strategies below threshold**: writes whatever was extracted, marks `pdf_profile.json` `unreliable: true`, and exits non-zero. Caller decides whether to proceed.
- **mathpix opt-in**: not bundled in MVP. Future env-var gate `MATHPIX_API_KEY`.

## Notes

- This skill does NOT verify extraction fidelity beyond cheap heuristics. Deeper QA is `/pdf-verify-extraction` (separate skill).
- This skill does NOT chunk or outline the result. That's `/outline-wiki`.
- Heavy dependencies: `pymupdf`, `marker-pdf`, `nougat-ocr`, `ocrmypdf`, `pylatexenc`. All in `pyproject.toml`. `tesseract` is a system binary — install via `brew install tesseract` on macOS.
