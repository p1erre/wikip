"""
Simple Video Analysis Workflow

This module provides a deterministic workflow for analyzing YouTube videos.
No LLM-based agent - just a clear sequence of steps.

Workflow:
1. Extract video ID from URL
2. Get video metadata
3. Try to get YouTube transcript
4. If no transcript, download audio and generate transcript
5. Return all collected data

For junior developers:
- This is a simple function-based workflow, not an LLM agent
- Each step calls a tool directly
- Clear, predictable behavior
- Easy to understand and debug
"""

import logging
from typing import Any
from pathlib import Path

from src.agents.video.tools import (
    extract_video_id_from_url,
    get_video_metadata,
    get_youtube_transcript,
    download_youtube_content,
    generate_transcript_from_audio,
)

logger = logging.getLogger(__name__)


def analyze_video_workflow(
    youtube_url: str,
    force_download: bool = False,
    output_dir: str = "./downloads"
) -> dict[str, Any]:
    """
    Analyze a YouTube video using a simple workflow.
    
    This is a deterministic workflow (not an LLM agent):
    1. Extract video ID
    2. Get metadata
    3. Try YouTube transcript
    4. If no transcript and force_download, download and transcribe
    
    Args:
        youtube_url: YouTube URL to analyze
        force_download: If True, download and transcribe even if YouTube captions exist
        output_dir: Directory for downloads
        
    Returns:
        Dictionary with all collected information
        
    Example:
        >>> result = analyze_video_workflow("https://youtube.com/watch?v=abc123")
        >>> print(result['metadata']['title'])
        >>> print(result['transcript']['num_segments'])
    """
    logger.info(f"Starting workflow for: {youtube_url}")
    
    result = {
        "youtube_url": youtube_url,
        "video_id": None,
        "metadata": None,
        "transcript": None,
        "audio_path": None,
        "steps_completed": [],
        "errors": [],
    }
    
    # Step 1: Extract video ID
    logger.info("Step 1: Extracting video ID...")
    id_result = extract_video_id_from_url.invoke({"youtube_url": youtube_url})
    
    if not id_result.get("success"):
        result["errors"].append(f"Failed to extract video ID: {id_result.get('error')}")
        return result
    
    video_id = id_result["video_id"]
    result["video_id"] = video_id
    result["steps_completed"].append("extract_id")
    logger.info(f"✓ Video ID: {video_id}")
    
    # Step 2: Get metadata
    logger.info("Step 2: Fetching metadata...")
    metadata_result = get_video_metadata.invoke({"video_id": video_id})
    
    if metadata_result.get("success"):
        result["metadata"] = metadata_result
        result["steps_completed"].append("get_metadata")
        logger.info(f"✓ Metadata: {metadata_result.get('title')}")
    else:
        result["errors"].append(f"Failed to get metadata: {metadata_result.get('error')}")
        logger.warning(f"✗ Metadata failed, continuing...")
    
    # Step 3: Try YouTube transcript
    logger.info("Step 3: Trying YouTube transcript...")
    transcript_result = get_youtube_transcript.invoke({"video_id": video_id})
    
    if transcript_result.get("success") and not force_download:
        result["transcript"] = transcript_result
        result["steps_completed"].append("get_youtube_transcript")
        logger.info(f"✓ YouTube transcript: {transcript_result.get('num_segments')} segments")
        return result  # Success! We have everything
    else:
        logger.info("✗ No YouTube transcript available")
        result["errors"].append("No YouTube transcript available")
    
    # Step 4: Download audio and generate transcript
    if force_download or not transcript_result.get("success"):
        logger.info("Step 4: Downloading audio...")
        download_result = download_youtube_content.invoke({
            "video_id": video_id,
            "download_video": False,
            "output_dir": output_dir
        })
        
        if not download_result.get("success"):
            result["errors"].append(f"Failed to download: {download_result.get('error')}")
            return result
        
        audio_path = download_result["file_path"]
        result["audio_path"] = audio_path
        result["steps_completed"].append("download_audio")
        logger.info(f"✓ Downloaded audio: {audio_path}")
        
        # Step 5: Generate transcript from audio
        logger.info("Step 5: Generating transcript with Whisper...")
        whisper_result = generate_transcript_from_audio.invoke({
            "video_id": video_id,
            "audio_path": audio_path
        })
        
        if whisper_result.get("success"):
            result["transcript"] = whisper_result
            result["steps_completed"].append("generate_transcript")
            logger.info(f"✓ Generated transcript: {whisper_result.get('num_segments')} segments")
        else:
            result["errors"].append(f"Failed to generate transcript: {whisper_result.get('error')}")
    
    logger.info(f"Workflow complete. Steps: {result['steps_completed']}")
    return result


def get_transcript(
    youtube_url: str,
    prefer_youtube: bool = True,
    output_dir: str = "./downloads"
) -> dict[str, Any]:
    """
    Get transcript for a YouTube video (simplified interface).
    
    Args:
        youtube_url: YouTube URL
        prefer_youtube: If True, use YouTube captions if available
        output_dir: Directory for downloads if needed
        
    Returns:
        Transcript data or error
        
    Example:
        >>> transcript = get_transcript("https://youtube.com/watch?v=abc")
        >>> for segment in transcript['segments']:
        ...     print(f"[{segment['start']}] {segment['text']}")
    """
    result = analyze_video_workflow(
        youtube_url,
        force_download=not prefer_youtube,
        output_dir=output_dir
    )
    
    if result.get("transcript"):
        return result["transcript"]
    else:
        return {
            "success": False,
            "error": "Could not get transcript",
            "details": result.get("errors", [])
        }


# Backward compatibility with old agent interface
def analyze_video(youtube_url: str, **kwargs) -> dict[str, Any]:
    """
    Analyze video (backward compatible with old agent interface).
    
    This wraps the workflow for compatibility with existing code.
    """
    return analyze_video_workflow(youtube_url, **kwargs)
