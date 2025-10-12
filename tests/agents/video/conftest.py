"""
Shared fixtures for video agent tests.

These fixtures are automatically available to all tests in this directory.
"""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_video_id():
    """Standard test video ID."""
    return "test123"


@pytest.fixture
def mock_youtube_url():
    """Standard test YouTube URL."""
    return "https://youtube.com/watch?v=test123"


@pytest.fixture
def mock_video_metadata():
    """Mock video metadata response."""
    return {
        "success": True,
        "video_id": "test123",
        "title": "Test Video Title",
        "duration": 120,
        "description": "Test video description",
        "channel": "Test Channel",
        "upload_date": "20240101",
        "view_count": 1000,
        "thumbnail_url": "https://example.com/thumb.jpg",
        "has_subtitles": True,
        "has_automatic_captions": True,
    }


@pytest.fixture
def mock_transcript_segments():
    """Mock transcript segments."""
    return [
        {
            "text": "Hello world",
            "start": 0.0,
            "end": 1.5,
            "duration": 1.5
        },
        {
            "text": "This is a test",
            "start": 1.5,
            "end": 3.0,
            "duration": 1.5
        },
        {
            "text": "Thank you",
            "start": 3.0,
            "end": 4.0,
            "duration": 1.0
        }
    ]


@pytest.fixture
def mock_youtube_transcript(mock_transcript_segments):
    """Mock successful YouTube transcript response."""
    return {
        "success": True,
        "video_id": "test123",
        "num_segments": len(mock_transcript_segments),
        "segments": mock_transcript_segments,
        "total_duration": 4.0
    }


@pytest.fixture
def mock_whisper_transcript(mock_transcript_segments):
    """Mock successful Whisper transcript response."""
    return {
        "success": True,
        "video_id": "test123",
        "num_segments": len(mock_transcript_segments),
        "segments": mock_transcript_segments,
        "total_duration": 4.0,
        "source": "whisper_api"
    }


@pytest.fixture
def mock_download_result():
    """Mock successful download response."""
    return {
        "success": True,
        "video_id": "test123",
        "file_path": "./downloads/test123.m4a",
        "title": "Test Video",
        "duration": 120,
        "file_size_mb": 25.5,
        "content_type": "audio"
    }


@pytest.fixture
def mock_extract_id_result():
    """Mock successful video ID extraction."""
    return {
        "success": True,
        "video_id": "test123"
    }


@pytest.fixture
def mock_failed_result():
    """Mock failed operation result."""
    return {
        "success": False,
        "error": "Operation failed",
        "suggestion": "Try again later"
    }
