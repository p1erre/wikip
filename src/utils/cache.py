"""
Cache utilities for video data

Provides caching for:
- Video metadata
- Transcripts
- Downloaded audio files
- Extracted slides
- Vision analysis results

This speeds up development and testing by avoiding repeated downloads and processing.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class VideoCache:
    """
    Cache manager for video data.
    
    Directory structure:
        .cache/
        └── videos/
            └── {video_id}/
                ├── metadata.json
                ├── transcript_{source}.json
                ├── audio.m4a
                ├── slides/
                │   ├── slides_metadata.json
                │   └── slide_*.jpg
                └── vision_analysis.json
    """
    
    def __init__(self, cache_dir: str = ".cache"):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Root directory for cache (default: .cache)
        """
        self.cache_dir = Path(cache_dir)
        self.videos_dir = self.cache_dir / "videos"
        
        # Create directories if they don't exist
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Create cache directories if they don't exist."""
        self.videos_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_video_dir(self, video_id: str) -> Path:
        """Get the directory for a specific video."""
        return self.videos_dir / video_id
    
    # ========================================================================
    # METADATA CACHE
    # ========================================================================
    
    def get_metadata(self, video_id: str) -> Optional[dict[str, Any]]:
        """
        Get cached metadata for a video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Metadata dict if cached, None otherwise
        """
        cache_file = self._get_video_dir(video_id) / "metadata.json"
        
        if cache_file.exists():
            logger.info(f"Loading metadata from cache: {video_id}")
            with open(cache_file, 'r') as f:
                return json.load(f)
        
        return None
    
    def save_metadata(self, video_id: str, metadata: dict[str, Any]) -> None:
        """
        Save metadata to cache.
        
        Args:
            video_id: YouTube video ID
            metadata: Metadata dict to cache
        """
        video_dir = self._get_video_dir(video_id)
        video_dir.mkdir(parents=True, exist_ok=True)
        cache_file = video_dir / "metadata.json"
        
        logger.info(f"Saving metadata to cache: {video_id}")
        with open(cache_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    # ========================================================================
    # TRANSCRIPT CACHE
    # ========================================================================
    
    def get_transcript(
        self, 
        video_id: str, 
        source: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """
        Get cached transcript for a video.
        
        Args:
            video_id: YouTube video ID
            source: Transcript source ('youtube', 'whisper_api', 'whisper_local')
                   If None, returns any available transcript (prefers YouTube)
            
        Returns:
            Transcript dict if cached, None otherwise
        """
        video_dir = self._get_video_dir(video_id)
        
        if source:
            # Look for specific source
            cache_file = video_dir / f"transcript_{source}.json"
            if cache_file.exists():
                logger.info(f"Loading {source} transcript from cache: {video_id}")
                with open(cache_file, 'r') as f:
                    return json.load(f)
        else:
            # Look for any transcript (prefer YouTube > Whisper API > Whisper local)
            for src in ['youtube', 'whisper_api', 'whisper_local']:
                cache_file = video_dir / f"transcript_{src}.json"
                if cache_file.exists():
                    logger.info(f"Loading {src} transcript from cache: {video_id}")
                    with open(cache_file, 'r') as f:
                        return json.load(f)
        
        return None
    
    def save_transcript(
        self, 
        video_id: str, 
        transcript: dict[str, Any],
        source: Optional[str] = None
    ) -> None:
        """
        Save transcript to cache.
        
        Args:
            video_id: YouTube video ID
            transcript: Transcript dict to cache
            source: Transcript source (extracted from transcript['source'] if not provided)
        """
        # Get source from transcript data if not provided
        if source is None:
            source = transcript.get('source', 'youtube')
        
        video_dir = self._get_video_dir(video_id)
        video_dir.mkdir(parents=True, exist_ok=True)
        cache_file = video_dir / f"transcript_{source}.json"
        
        logger.info(f"Saving {source} transcript to cache: {video_id}")
        with open(cache_file, 'w') as f:
            json.dump(transcript, f, indent=2)
    
    def get_available_transcripts(self, video_id: str) -> list[str]:
        """
        Get list of available transcript sources for a video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            List of available sources (e.g., ['youtube', 'whisper_api'])
        """
        video_dir = self._get_video_dir(video_id)
        sources = []
        for src in ['youtube', 'whisper_api', 'whisper_local']:
            cache_file = video_dir / f"transcript_{src}.json"
            if cache_file.exists():
                sources.append(src)
        return sources
    
    # ========================================================================
    # AUDIO CACHE
    # ========================================================================
    
    def get_audio_path(self, video_id: str) -> Optional[Path]:
        """
        Get path to cached audio file.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Path to audio file if cached, None otherwise
        """
        video_dir = self._get_video_dir(video_id)
        # Check for common audio formats
        for ext in ['.m4a', '.mp3', '.webm', '.opus']:
            cache_file = video_dir / f"audio{ext}"
            if cache_file.exists():
                logger.info(f"Found cached audio: {cache_file}")
                return cache_file
        
        return None
    
    def save_audio_path(self, video_id: str, source_path: str) -> Path:
        """
        Copy audio file to cache.
        
        Args:
            video_id: YouTube video ID
            source_path: Path to source audio file
            
        Returns:
            Path to cached audio file
        """
        import shutil
        
        video_dir = self._get_video_dir(video_id)
        video_dir.mkdir(parents=True, exist_ok=True)
        
        source = Path(source_path)
        dest = video_dir / f"audio{source.suffix}"
        
        if not dest.exists():
            logger.info(f"Copying audio to cache: {video_id}")
            shutil.copy2(source, dest)
        
        return dest
    
    # ========================================================================
    # SLIDES CACHE
    # ========================================================================
    
    def get_slides(self, video_id: str) -> Optional[dict[str, Any]]:
        """
        Get cached slides data for a video.
        
        Args:
            video_id: Video identifier (YouTube ID or local filename)
            
        Returns:
            Slides dict if cached, None otherwise
        """
        cache_file = self._get_video_dir(video_id) / "slides" / "slides_metadata.json"
        
        if cache_file.exists():
            logger.info(f"Loading slides from cache: {video_id}")
            with open(cache_file, 'r') as f:
                return json.load(f)
        
        return None
    
    def save_slides(self, video_id: str, slides_data: dict[str, Any]) -> Path:
        """
        Save slides data to cache.
        
        Args:
            video_id: Video identifier
            slides_data: Slides dict from extract_slides_robust()
            
        Returns:
            Path to cached slides directory
        """
        slides_dir = self._get_video_dir(video_id) / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)
        
        cache_file = slides_dir / "slides_metadata.json"
        
        logger.info(f"Saving slides to cache: {video_id}")
        with open(cache_file, 'w') as f:
            json.dump(slides_data, f, indent=2)
        
        return slides_dir
    
    def get_slides_dir(self, video_id: str) -> Path:
        """
        Get path to slides directory for a video.
        
        Args:
            video_id: Video identifier
            
        Returns:
            Path to slides directory
        """
        return self._get_video_dir(video_id) / "slides"
    
    # ========================================================================
    # VISION ANALYSIS CACHE
    # ========================================================================
    
    def get_vision_analysis(self, video_id: str) -> Optional[list[dict[str, Any]]]:
        """
        Get cached vision analysis for a video.
        
        Args:
            video_id: Video identifier
            
        Returns:
            Vision analysis list if cached, None otherwise
        """
        cache_file = self._get_video_dir(video_id) / "vision_analysis.json"
        
        if cache_file.exists():
            logger.info(f"Loading vision analysis from cache: {video_id}")
            with open(cache_file, 'r') as f:
                data = json.load(f)
                # Return just the slides array if wrapped in metadata
                if isinstance(data, dict) and 'slides' in data:
                    return data['slides']
                return data
        
        return None
    
    def save_vision_analysis(
        self, 
        video_id: str, 
        analysis: list[dict[str, Any]],
        metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Save vision analysis to cache.
        
        Args:
            video_id: Video identifier
            analysis: Vision analysis list from analyze_slides_with_vision()
            metadata: Optional metadata (provider, model, etc.)
        """
        video_dir = self._get_video_dir(video_id)
        video_dir.mkdir(parents=True, exist_ok=True)
        cache_file = video_dir / "vision_analysis.json"
        
        # Wrap in metadata if provided
        if metadata:
            data = {
                **metadata,
                'slides': analysis
            }
        else:
            data = analysis
        
        logger.info(f"Saving vision analysis to cache: {video_id}")
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    # ========================================================================
    # CACHE MANAGEMENT
    # ========================================================================
    
    def clear_video(self, video_id: str) -> None:
        """
        Clear all cached data for a specific video.
        
        Args:
            video_id: YouTube video ID or video identifier
        """
        import shutil
        
        logger.info(f"Clearing cache for video: {video_id}")
        
        # Remove entire video directory
        video_dir = self._get_video_dir(video_id)
        if video_dir.exists():
            shutil.rmtree(video_dir)
            logger.info(f"Removed cache directory: {video_dir}")
    
    def clear_all(self) -> None:
        """Clear entire cache."""
        import shutil
        
        logger.warning("Clearing entire cache")
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
        
        self._ensure_dirs()
    
    def get_cache_size(self) -> dict[str, int]:
        """
        Get cache size statistics.
        
        Returns:
            Dict with size in bytes for each cache type
        """
        def dir_size(path: Path) -> int:
            return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        
        return {
            "total": dir_size(self.cache_dir)
        }
    
    def get_cache_info(self) -> dict[str, Any]:
        """
        Get cache information.
        
        Returns:
            Dict with cache statistics
        """
        sizes = self.get_cache_size()
        
        # Count videos
        num_videos = len(list(self.videos_dir.glob("*"))) if self.videos_dir.exists() else 0
        
        return {
            "cache_dir": str(self.cache_dir.absolute()),
            "size_bytes": sizes['total'],
            "size_mb": sizes['total'] / (1024 * 1024),
            "num_videos": num_videos
        }


# Global cache instance
_cache = None


def get_cache(cache_dir: str = ".cache") -> VideoCache:
    """
    Get global cache instance.
    
    Args:
        cache_dir: Root directory for cache
        
    Returns:
        VideoCache instance
    """
    global _cache
    if _cache is None:
        _cache = VideoCache(cache_dir)
    return _cache
