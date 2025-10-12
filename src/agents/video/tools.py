"""
YouTube Tools for LangGraph Agents

This module provides tools that agents can use to interact with YouTube videos.
Each tool is a function decorated with @tool that the LLM can call.

For junior developers:
- @tool decorator makes a function callable by the LLM
- Pydantic models validate inputs automatically
- Docstrings become the tool description the LLM sees
"""

import logging
import re
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.utils.cache import get_cache
from src.utils.decorators import with_cache_control, cached_metadata, cached_transcript

# Set up logging
logger = logging.getLogger(__name__)


class YouTubeURLInput(BaseModel):
    """Input schema for extracting video ID from URL"""
    
    youtube_url: str = Field(
        description="Full YouTube URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID)"
    )


class VideoIDInput(BaseModel):
    """Input schema for tools that work with video ID"""
    
    video_id: str = Field(
        description="YouTube video ID (11 characters, e.g., 'dQw4w9WgXcQ')"
    )


class DownloadInput(BaseModel):
    """Input schema for video download tool"""
    
    video_id: str = Field(
        description="YouTube video ID to download"
    )
    download_video: bool = Field(
        default=False,
        description="If True, download video file. If False, download only audio."
    )
    output_dir: str = Field(
        default="./downloads",
        description="Directory to save downloaded files"
    )


@tool(args_schema=YouTubeURLInput)
def extract_video_id_from_url(youtube_url: str) -> dict[str, Any]:
    """
    Extract the video ID from a YouTube URL.
    
    This tool handles various YouTube URL formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    
    Args:
        youtube_url: The YouTube URL to parse
        
    Returns:
        Dictionary with 'success', 'video_id', and optional 'error'
        
    Example:
        >>> result = extract_video_id_from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        >>> result['video_id']
        'dQw4w9WgXcQ'
    """
    logger.info(f"Extracting video ID from URL: {youtube_url}")
    
    # Patterns for different YouTube URL formats
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([^&\n?#]+)',  # Standard watch URL
        r'(?:youtu\.be\/)([^&\n?#]+)',              # Shortened URL
        r'(?:youtube\.com\/embed\/)([^&\n?#]+)',    # Embed URL
        r'(?:youtube\.com\/v\/)([^&\n?#]+)',        # Old embed format
    ]
    
    for pattern in patterns:
        match = re.search(pattern, youtube_url)
        if match:
            video_id = match.group(1)
            logger.info(f"Successfully extracted video ID: {video_id}")
            return {
                "success": True,
                "video_id": video_id
            }
    
    error_msg = f"Could not extract video ID from URL: {youtube_url}"
    logger.error(error_msg)
    return {
        "success": False,
        "error": error_msg
    }


@with_cache_control
@cached_metadata
@tool(args_schema=VideoIDInput)
def get_video_metadata(video_id: str) -> dict[str, Any]:
    """
    Get metadata about a YouTube video without downloading it.
    
    This retrieves information like title, duration, description, etc.
    Uses yt-dlp to extract metadata. Results are automatically cached.
    
    Args:
        video_id: YouTube video ID
        
    Cache Control (optional kwargs):
        use_cache: Use cached data if available (default: True)
        force_refresh: Force refresh from API even if cached (default: False)
        
    Returns:
        Dictionary with video metadata or error information
        
    Example:
        >>> metadata = get_video_metadata("dQw4w9WgXcQ")
        >>> metadata['title']
        'Rick Astley - Never Gonna Give You Up'
        
        >>> # Force refresh
        >>> metadata = get_video_metadata("dQw4w9WgXcQ", force_refresh=True)
    """
    logger.info(f"Fetching metadata for video ID: {video_id}")
    
    try:
        import yt_dlp
        
        # Configure yt-dlp to only extract info, not download
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False  # Don't download, just get info
            )
            
            # Extract relevant metadata
            metadata = {
                "success": True,
                "video_id": video_id,
                "title": info.get("title"),
                "duration": info.get("duration"),  # in seconds
                "description": info.get("description"),
                "channel": info.get("uploader"),
                "upload_date": info.get("upload_date"),
                "view_count": info.get("view_count"),
                "thumbnail_url": info.get("thumbnail"),
                "has_subtitles": len(info.get("subtitles", {})) > 0,
                "has_automatic_captions": len(info.get("automatic_captions", {})) > 0,
                "chapters": info.get("chapters", []),  # Include chapters if available
            }
            
            logger.info(f"Successfully fetched metadata for: {metadata['title']}")
            return metadata
            
    except Exception as e:
        error_msg = f"Failed to get metadata: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


@tool(args_schema=VideoIDInput)
@with_cache_control
@cached_transcript
def get_youtube_transcript(video_id: str) -> dict[str, Any]:
    """
    Get the transcript/captions from a YouTube video.
    
    This tries to fetch existing captions (manual or auto-generated).
    Returns transcript segments with timestamps. Results are automatically cached.
    
    Args:
        video_id: YouTube video ID
        
    Cache Control (optional kwargs):
        use_cache: Use cached data if available (default: True)
        force_refresh: Force refresh from API even if cached (default: False)
        
    Returns:
        Dictionary with transcript segments or error information
        
    Example:
        >>> result = get_youtube_transcript("dQw4w9WgXcQ")
        >>> result['segments'][0]
        {'text': 'We're no strangers to love', 'start': 0.0, 'duration': 3.5}
    """
    logger.info(f"Fetching transcript for video ID: {video_id}")
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        # Try to get transcript (prefers manual captions over auto-generated)
        api = YouTubeTranscriptApi()
        transcript_data = api.fetch(video_id)
        
        # The API returns a FetchedTranscriptSnippet object with a 'snippets' attribute
        transcript_list = transcript_data.snippets if hasattr(transcript_data, 'snippets') else transcript_data
        
        # Format the transcript segments
        segments = [
            {
                "text": snippet.text if hasattr(snippet, 'text') else snippet["text"],
                "start": snippet.start if hasattr(snippet, 'start') else snippet["start"],
                "duration": snippet.duration if hasattr(snippet, 'duration') else snippet["duration"],
                "end": (snippet.start + snippet.duration) if hasattr(snippet, 'start') else (snippet["start"] + snippet["duration"])
            }
            for snippet in transcript_list
        ]
        
        logger.info(f"Successfully fetched {len(segments)} transcript segments")
        
        return {
            "success": True,
            "video_id": video_id,
            "num_segments": len(segments),
            "segments": segments,
            "total_duration": segments[-1]["end"] if segments else 0,
            "source": "youtube"  # Decorator uses this for multi-source caching
        }
        
    except Exception as e:
        error_msg = f"Failed to get transcript: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "suggestion": "Video may not have captions. Try downloading and transcribing."
        }


@tool(args_schema=DownloadInput)
def download_youtube_content(
    video_id: str,
    download_video: bool = False,
    output_dir: str = "./downloads"
) -> dict[str, Any]:
    """
    Download a YouTube video or just its audio.
    
    This tool uses yt-dlp to download content. You can choose to download:
    - Just audio (faster, smaller file) - default
    - Full video (slower, larger file)
    
    Args:
        video_id: YouTube video ID
        download_video: If True, download video. If False, download only audio.
        output_dir: Directory to save the downloaded file
        
    Returns:
        Dictionary with download information or error
        
    Example:
        >>> result = download_youtube_content("dQw4w9WgXcQ", download_video=False)
        >>> result['file_path']
        './downloads/dQw4w9WgXcQ.m4a'
    """
    logger.info(f"Downloading {'video' if download_video else 'audio'} for: {video_id}")
    
    try:
        import yt_dlp
        
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best' if download_video else 'bestaudio/best',
            'outtmpl': str(output_path / f'{video_id}.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
        }
        
        # If downloading audio only, convert to m4a
        if not download_video:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }]
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Download and get info
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=True
            )
            
            # Determine the output file path
            if download_video:
                ext = info.get('ext', 'mp4')
            else:
                ext = 'm4a'
            
            file_path = output_path / f"{video_id}.{ext}"
            
            result = {
                "success": True,
                "video_id": video_id,
                "file_path": str(file_path),
                "title": info.get("title"),
                "duration": info.get("duration"),
                "file_size_mb": file_path.stat().st_size / (1024 * 1024) if file_path.exists() else None,
                "content_type": "video" if download_video else "audio"
            }
            
            logger.info(f"Successfully downloaded to: {file_path}")
            return result
            
    except Exception as e:
        error_msg = f"Failed to download: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


@tool(args_schema=VideoIDInput)
def generate_transcript_from_audio(video_id: str, audio_path: str = None) -> dict[str, Any]:
    """
    Generate transcript from downloaded audio using Whisper.
    
    This tool uses OpenAI's Whisper API for files < 25MB,
    or falls back to local Whisper for larger files.
    Use this when YouTube captions are not available.
    
    Args:
        video_id: YouTube video ID
        audio_path: Path to audio file (optional, will use default if not provided)
        
    Returns:
        Dictionary with transcript segments or error
        
    Example:
        >>> result = generate_transcript_from_audio("abc123", "./downloads/abc123.m4a")
        >>> result['segments'][0]
        {'text': 'Hello world', 'start': 0.0, 'end': 1.5}
    """
    logger.info(f"Generating transcript for video ID: {video_id}")
    
    try:
        # Determine audio file path
        if audio_path is None:
            audio_path = f"./downloads/{video_id}.m4a"
        
        audio_file = Path(audio_path)
        
        if not audio_file.exists():
            return {
                "success": False,
                "error": f"Audio file not found: {audio_path}",
                "suggestion": "Download the audio first using download_youtube_content"
            }
        
        # Check file size (Whisper API limit is 25MB)
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        logger.info(f"Audio file size: {file_size_mb:.1f}MB")
        
        if file_size_mb < 25:
            # Use OpenAI Whisper API for smaller files
            logger.info("Using OpenAI Whisper API...")
            from openai import OpenAI
            
            client = OpenAI()
            
            with open(audio_file, "rb") as f:
                transcript_response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
            
            # Format segments
            segments = []
            if hasattr(transcript_response, 'segments'):
                segments = [
                    {
                        "text": segment.text,
                        "start": segment.start,
                        "end": segment.end,
                        "duration": segment.end - segment.start
                    }
                    for segment in transcript_response.segments
                ]
            
            source = "whisper_api"
        else:
            # Use local Whisper for larger files
            logger.info("File too large for API, using local Whisper...")
            import whisper
            
            # Load model (base is good balance of speed/accuracy)
            model = whisper.load_model("base")
            
            # Transcribe
            result = model.transcribe(str(audio_file), verbose=False)
            
            # Format segments
            segments = [
                {
                    "text": segment["text"].strip(),
                    "start": segment["start"],
                    "end": segment["end"],
                    "duration": segment["end"] - segment["start"]
                }
                for segment in result.get("segments", [])
            ]
            
            source = "whisper_local"
        
        logger.info(f"Successfully generated {len(segments)} transcript segments")
        
        return {
            "success": True,
            "video_id": video_id,
            "num_segments": len(segments),
            "segments": segments,
            "total_duration": segments[-1]["end"] if segments else 0,
            "source": source
        }
        
    except Exception as e:
        error_msg = f"Failed to generate transcript: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "suggestion": "Make sure openai-whisper is installed: pip install openai-whisper"
        }


# List of all tools for easy import
YOUTUBE_TOOLS = [
    extract_video_id_from_url,
    get_video_metadata,
    get_youtube_transcript,
    download_youtube_content,
    generate_transcript_from_audio,
]


def get_tools() -> list:
    """
    Get all YouTube tools for use with LangGraph agents.
    
    Returns:
        List of tool functions
        
    Example:
        >>> from src.tools.youtube_tools import get_tools
        >>> tools = get_tools()
        >>> # Pass to agent
        >>> agent = create_react_agent(llm, tools)
    """
    return YOUTUBE_TOOLS
