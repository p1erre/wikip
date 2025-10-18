# Commit Message for Refactoring

```
refactor: Simplify codebase to focus on pipeline functionality

Major simplification of the project structure:

REMOVED (77 files):
- src/agents/ - LangGraph agent wrappers (unnecessary abstraction)
- src/cli/ - CLI runner (not needed for pipeline-only usage)
- examples/ - 16 example scripts
- tests/ - Test suite
- scripts/ - Helper scripts  
- docs/ - 26 documentation files
- tmp/ - Temporary files
- demo_vision_output/ - Demo files
- src/processing/video/workflow.py - Unused workflow functions
- src/processing/content/semantic_chapters.py - Duplicate implementation
- Various standalone scripts and config files

KEPT (17 core Python files):
- src/pipeline.py - Main API
- src/processing/content/ - Content generation (2 files)
- src/processing/slides/ - Slide extraction (2 files)
- src/processing/video/ - YouTube operations (1 file)
- src/processing/vision/ - Vision analysis (1 file)
- src/utils/ - Cache, decorators, input handling (3 files)
- Module __init__.py files (7 files)

ADDED:
- REFACTORING_SUMMARY.md - Detailed refactoring documentation
- example_usage.py - Comprehensive usage examples
- test_pipeline.py - Import verification script

UPDATED:
- README.md - Simplified to reflect new structure
- src/processing/video/__init__.py - Removed workflow imports

BENEFITS:
✅ 82% reduction in file count (94 → 17 core files)
✅ Clearer dependency tree
✅ Easier to understand and maintain
✅ All pipeline.py functionality preserved
✅ No breaking changes to core API

The refactored codebase focuses exclusively on the video-to-book
pipeline functionality with intelligent caching, chapter generation,
and vision analysis capabilities.
```
