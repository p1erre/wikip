"""
Cache utilities for video data

Provides caching for:
- Video metadata
- Transcripts
- Downloaded audio files

This speeds up development and testing by avoiding repeated downloads.
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
        ├── metadata/
        │   └── {video_id}.json
        ├── transcripts/
        │   └── {video_id}.json
        └── audio/
            └── {video_id}.m4a
    """
    
    def __init__(self, cache_dir: str = ".cache"):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Root directory for cache (default: .cache)
        """
        self.cache_dir = Path(cache_dir)
        self.metadata_dir = self.cache_dir / "metadata"
        self.transcripts_dir = self.cache_dir / "transcripts"
        self.audio_dir = self.cache_dir / "audio"
        
        # Create directories if they don't exist
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Create cache directories if they don't exist."""
        for dir_path in [self.metadata_dir, self.transcripts_dir, self.audio_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
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
        cache_file = self.metadata_dir / f"{video_id}.json"
        
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
        cache_file = self.metadata_dir / f"{video_id}.json"
        
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
        if source:
            # Look for specific source
            cache_file = self.transcripts_dir / f"{video_id}_{source}.json"
            if cache_file.exists():
                logger.info(f"Loading {source} transcript from cache: {video_id}")
                with open(cache_file, 'r') as f:
                    return json.load(f)
        else:
            # Look for any transcript (prefer YouTube > Whisper API > Whisper local)
            for src in ['youtube', 'whisper_api', 'whisper_local']:
                cache_file = self.transcripts_dir / f"{video_id}_{src}.json"
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
        
        cache_file = self.transcripts_dir / f"{video_id}_{source}.json"
        
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
        sources = []
        for src in ['youtube', 'whisper_api', 'whisper_local']:
            cache_file = self.transcripts_dir / f"{video_id}_{src}.json"
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
        # Check for common audio formats
        for ext in ['.m4a', '.mp3', '.webm', '.opus']:
            cache_file = self.audio_dir / f"{video_id}{ext}"
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
        
        source = Path(source_path)
        dest = self.audio_dir / f"{video_id}{source.suffix}"
        
        if not dest.exists():
            logger.info(f"Copying audio to cache: {video_id}")
            shutil.copy2(source, dest)
        
        return dest
    
    # ========================================================================
    # CACHE MANAGEMENT
    # ========================================================================
    
    def clear_video(self, video_id: str) -> None:
        """
        Clear all cached data for a specific video.
        
        Args:
            video_id: YouTube video ID
        """
        logger.info(f"Clearing cache for video: {video_id}")
        
        # Remove metadata
        metadata_file = self.metadata_dir / f"{video_id}.json"
        if metadata_file.exists():
            metadata_file.unlink()
        
        # Remove transcript
        transcript_file = self.transcripts_dir / f"{video_id}.json"
        if transcript_file.exists():
            transcript_file.unlink()
        
        # Remove audio (all formats)
        for ext in ['.m4a', '.mp3', '.webm', '.opus']:
            audio_file = self.audio_dir / f"{video_id}{ext}"
            if audio_file.exists():
                audio_file.unlink()
    
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
            "metadata": dir_size(self.metadata_dir),
            "transcripts": dir_size(self.transcripts_dir),
            "audio": dir_size(self.audio_dir),
            "total": dir_size(self.cache_dir)
        }
    
    def get_cache_info(self) -> dict[str, Any]:
        """
        Get cache information.
        
        Returns:
            Dict with cache statistics
        """
        sizes = self.get_cache_size()
        
        return {
            "cache_dir": str(self.cache_dir.absolute()),
            "size_bytes": sizes,
            "size_mb": {k: v / (1024 * 1024) for k, v in sizes.items()},
            "cached_videos": {
                "metadata": len(list(self.metadata_dir.glob("*.json"))),
                "transcripts": len(list(self.transcripts_dir.glob("*.json"))),
                "audio": len(list(self.audio_dir.glob("*")))
            }
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
