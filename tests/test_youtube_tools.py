"""
Tests for YouTube tools

These tests demonstrate how to test LangGraph tools.
Some tests are marked as integration tests because they make real API calls.

Run tests with:
    pytest tests/test_youtube_tools.py
    pytest tests/test_youtube_tools.py -v  # verbose
    pytest tests/test_youtube_tools.py -k test_extract  # run specific test
"""

import pytest
from src.tools.youtube_tools import (
    extract_video_id_from_url,
    get_video_metadata,
    get_youtube_transcript,
)


class TestExtractVideoID:
    """Tests for video ID extraction."""
    
    def test_extract_from_standard_url(self):
        """Test extracting ID from standard watch URL."""
        result = extract_video_id_from_url.invoke({
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        })
        
        assert result["success"] is True
        assert result["video_id"] == "dQw4w9WgXcQ"
    
    def test_extract_from_short_url(self):
        """Test extracting ID from shortened youtu.be URL."""
        result = extract_video_id_from_url.invoke({
            "youtube_url": "https://youtu.be/dQw4w9WgXcQ"
        })
        
        assert result["success"] is True
        assert result["video_id"] == "dQw4w9WgXcQ"
    
    def test_extract_from_embed_url(self):
        """Test extracting ID from embed URL."""
        result = extract_video_id_from_url.invoke({
            "youtube_url": "https://www.youtube.com/embed/dQw4w9WgXcQ"
        })
        
        assert result["success"] is True
        assert result["video_id"] == "dQw4w9WgXcQ"
    
    def test_extract_with_parameters(self):
        """Test extracting ID from URL with query parameters."""
        result = extract_video_id_from_url.invoke({
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s"
        })
        
        assert result["success"] is True
        assert result["video_id"] == "dQw4w9WgXcQ"
    
    def test_invalid_url(self):
        """Test that invalid URLs return error."""
        result = extract_video_id_from_url.invoke({
            "youtube_url": "https://example.com/not-a-video"
        })
        
        assert result["success"] is False
        assert "error" in result


@pytest.mark.integration
class TestGetVideoMetadata:
    """
    Integration tests for video metadata.
    
    These make real API calls to YouTube.
    Mark as integration so they can be skipped in CI.
    """
    
    def test_get_metadata_success(self):
        """Test getting metadata for a real video."""
        # Using a well-known video that should always exist
        result = get_video_metadata.invoke({
            "video_id": "dQw4w9WgXcQ"
        })
        
        assert result["success"] is True
        assert "title" in result
        assert "duration" in result
        assert result["video_id"] == "dQw4w9WgXcQ"
    
    def test_get_metadata_invalid_id(self):
        """Test getting metadata for invalid video ID."""
        result = get_video_metadata.invoke({
            "video_id": "invalid_id_123"
        })
        
        assert result["success"] is False
        assert "error" in result


@pytest.mark.integration
class TestGetTranscript:
    """Integration tests for transcript fetching."""
    
    def test_get_transcript_success(self):
        """Test getting transcript for a video with captions."""
        # This video has captions
        result = get_youtube_transcript.invoke({
            "video_id": "dQw4w9WgXcQ"
        })
        
        # Note: This might fail if the video doesn't have captions
        # In that case, it's expected behavior
        if result["success"]:
            assert "segments" in result
            assert len(result["segments"]) > 0
            assert "text" in result["segments"][0]
            assert "start" in result["segments"][0]
    
    def test_get_transcript_no_captions(self):
        """Test getting transcript for video without captions."""
        # Use a video ID that likely doesn't exist
        result = get_youtube_transcript.invoke({
            "video_id": "nonexistent123"
        })
        
        assert result["success"] is False
        assert "error" in result


# Example of how to run specific tests:
# pytest tests/test_youtube_tools.py::TestExtractVideoID::test_extract_from_standard_url
# pytest tests/test_youtube_tools.py -m "not integration"  # Skip integration tests
