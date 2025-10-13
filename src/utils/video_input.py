"""
Video input normalization utilities

Handles both YouTube URLs/IDs and local video files.
"""

import re
import hashlib
import os
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def extract_youtube_id(url_or_id: str) -> Optional[str]:
    """
    Extract YouTube video ID from URL or return as-is if already an ID.
    
    Args:
        url_or_id: YouTube URL or video ID
        
    Returns:
        YouTube video ID or None if invalid
    """
    # Already an ID (11 characters, alphanumeric + - and _)
    if len(url_or_id) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    
    # Extract from URL
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    
    return None


def is_youtube_input(input_source: str) -> bool:
    """
    Check if input is a YouTube URL or ID.
    
    Args:
        input_source: Input string to check
        
    Returns:
        True if YouTube input, False otherwise
    """
    return extract_youtube_id(input_source) is not None


def generate_local_video_id(file_path: str) -> str:
    """
    Generate a unique ID for a local video file.
    
    Uses filename + file size + modification time to create a stable ID
    that changes if the file is modified.
    
    Args:
        file_path: Path to local video file
        
    Returns:
        Unique video ID
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")
    
    # Get file stats
    stat = os.stat(file_path)
    filename = path.stem  # Without extension
    
    # Create stable ID from filename + size + mtime
    # This ensures same file = same ID, but modified file = new ID
    id_string = f"{filename}_{stat.st_size}_{int(stat.st_mtime)}"
    
    # Hash to keep it reasonable length
    hash_suffix = hashlib.md5(id_string.encode()).hexdigest()[:8]
    
    # Return clean filename + hash
    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', filename)[:40]
    return f"{clean_name}_{hash_suffix}"


def normalize_video_input(input_source: str) -> Tuple[str, str, str]:
    """
    Normalize video input to (video_id, video_path, input_type).
    
    Args:
        input_source: YouTube URL/ID or local file path
        
    Returns:
        Tuple of (video_id, video_path, input_type)
        - video_id: Unique identifier for caching
        - video_path: Path to video file (may need download for YouTube)
        - input_type: 'youtube' or 'local'
        
    Raises:
        ValueError: If input is invalid
        FileNotFoundError: If local file doesn't exist
    """
    # Check if YouTube
    youtube_id = extract_youtube_id(input_source)
    if youtube_id:
        logger.info(f"Detected YouTube video: {youtube_id}")
        return youtube_id, None, 'youtube'  # Path will be set after download
    
    # Check if local file
    path = Path(input_source)
    if path.exists() and path.is_file():
        video_id = generate_local_video_id(input_source)
        logger.info(f"Detected local video: {path.name} (ID: {video_id})")
        return video_id, str(path.absolute()), 'local'
    
    # Invalid input
    raise ValueError(
        f"Invalid video input: {input_source}\n"
        "Must be either:\n"
        "  - YouTube URL (e.g., https://youtube.com/watch?v=...)\n"
        "  - YouTube ID (e.g., dQw4w9WgXcQ)\n"
        "  - Local file path (e.g., ./video.mp4)"
    )


def get_or_download_youtube_video(
    video_id: str,
    cache_dir: str = ".cache"
) -> str:
    """
    Get path to YouTube video, downloading if necessary.
    
    Args:
        video_id: YouTube video ID
        cache_dir: Cache directory
        
    Returns:
        Path to downloaded video file
    """
    # Import directly to avoid loading agent
    import importlib
    video_tools = importlib.import_module('src.agents.video.tools')
    from src.utils.cache import get_cache
    
    cache = get_cache(cache_dir)
    
    # Check if already downloaded
    audio_path = cache.get_audio_path(video_id)
    if audio_path:
        logger.info(f"Using cached video: {video_id}")
        return str(audio_path)
    
    # Download video
    logger.info(f"Downloading YouTube video: {video_id}")
    result = video_tools.download_youtube_content(video_id)
    
    if not result.get('success'):
        raise RuntimeError(f"Failed to download video: {result.get('error')}")
    
    # Cache the downloaded file
    video_path = result['audio_path']
    cached_path = cache.save_audio_path(video_id, video_path)
    
    return str(cached_path)
