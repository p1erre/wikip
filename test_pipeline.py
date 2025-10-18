#!/usr/bin/env python3
"""
Quick test to verify pipeline imports work correctly after refactoring.
"""

def test_imports():
    """Test that all pipeline dependencies can be imported."""
    print("Testing imports...")
    
    # Core pipeline
    from src.pipeline import process_video, generate_booklet, clear_video_cache, get_cache_info
    print("✅ Pipeline imports OK")
    
    # Utils
    from src.utils.cache import get_cache
    from src.utils.video_input import normalize_video_input, get_or_download_youtube_video
    from src.utils.decorators import with_cache_control
    print("✅ Utils imports OK")
    
    # Processing - Video
    from src.processing.video import get_youtube_transcript, get_video_metadata
    print("✅ Video processing imports OK")
    
    # Processing - Slides
    from src.processing.slides import extract_slides_robust
    print("✅ Slides processing imports OK")
    
    # Processing - Vision
    from src.processing.vision import analyze_slides_with_vision
    print("✅ Vision processing imports OK")
    
    # Processing - Content
    from src.processing.content import (
        generate_booklet_from_transcript,
        generate_booklet_by_chapters,
        create_chapters
    )
    print("✅ Content processing imports OK")
    
    print("\n✅ All imports successful!")
    return True


if __name__ == "__main__":
    try:
        test_imports()
        print("\n🎉 Pipeline refactoring successful - all dependencies intact!")
    except Exception as e:
        print(f"\n❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
