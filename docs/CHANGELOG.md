# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Changed - 2025-10-21

#### Project Structure Reorganization
Cleaned up root folder by organizing files into appropriate directories:

- **Created `examples/` folder** - Moved all example and test scripts:
  - `example_usage.py` - Comprehensive Python API examples
  - `generate_booklet.py` - Simple booklet generation example
  - `ejemplo_pipeline.py` - Spanish pipeline explanation
  - `test_pipeline.py` - Import verification script

- **Documentation in `docs/`** - All markdown files organized:
  - `CLI_GUIDE.md` - Complete CLI documentation
  - `PIPELINE_EXPLICACION.md` - Pipeline explanation (Spanish)
  - `CHANGELOG.md` - This file
  - `REFACTORING_SUMMARY.md` - Major refactoring notes

- **Root folder now contains only**:
  - `README.md` - Main documentation
  - `pyproject.toml` / `uv.lock` - Dependencies
  - `vtb` - CLI wrapper script
  - Core directories: `src/`, `docs/`, `examples/`, `output/`, `downloads/`

#### Function Name Refactoring
Renamed pipeline functions to better reflect their purpose:

- **`process_video` → `process_video_with_slides`**
  - Makes it clear this pipeline is specialized for videos with slides/presentations
  - Extracts slides, analyzes with vision, gets transcript
  - Updated in: `src/pipeline.py`, `src/cli.py`, `example_usage.py`, `test_pipeline.py`

- **`generate_booklet` → `transcript_to_booklet`**
  - Makes it clear this pipeline only uses transcripts (no slides/vision)
  - Generates text-based booklets from YouTube transcripts
  - Updated in: `src/pipeline.py`, `src/cli.py`, `generate_booklet.py`, `example_usage.py`, `test_pipeline.py`

**Migration:**
```python
# Before
from src.pipeline import process_video, generate_booklet

# After
from src.pipeline import process_video_with_slides, transcript_to_booklet
```

#### Documentation Organization
- Moved markdown documentation files to `docs/` folder
- Moved generated booklets to `output/` folder
- Kept `README.md` in root (standard practice)

### Added - 2025-10-21

- **CLI Interface** (`src/cli.py`)
  - `generate` command - Generate booklet from YouTube video
  - `process` command - Process video with slides and vision analysis
  - `cache-info` command - Show cache information
  - `cache-clear` command - Clear cache for a video

- **Example Files**
  - `generate_booklet.py` - Simple booklet generation example
  - `example_usage.py` - Comprehensive usage examples
  - `ejemplo_pipeline.py` - Spanish pipeline explanation with examples

### Previous Changes

See `docs/REFACTORING_SUMMARY.md` for details on the major refactoring that simplified the codebase from 90+ files to 17 core files.

---

## How to Use This Changelog

- **Added** - New features
- **Changed** - Changes in existing functionality
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Security fixes
