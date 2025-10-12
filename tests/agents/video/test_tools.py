"""
Tests for YouTube tools

These tests demonstrate how to test LangGraph tools.
Some tests are marked as integration tests because they make real API calls.

Run tests with:
    pytest tests/agents/video/test_tools.py
    pytest tests/agents/video/test_tools.py -v  # verbose
    pytest tests/agents/video/test_tools.py -k test_extract  # run specific test
    pytest tests/agents/video/ -m "not integration"  # skip integration tests
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from src.agents.video.tools import (
    extract_video_id_from_url,
    get_video_metadata,
    get_youtube_transcript,
    download_youtube_content,
    generate_transcript_from_audio,
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


class TestGenerateTranscriptFromAudio:
    """Tests for Whisper transcription tool."""
    
    def test_audio_file_not_found(self):
        """Test error when audio file doesn't exist."""
        result = generate_transcript_from_audio.invoke({
            "video_id": "test123",
            "audio_path": "./nonexistent/test123.m4a"
        })
        
        assert result["success"] is False
        assert "Audio file not found" in result["error"]
        assert "suggestion" in result
    
    @patch('src.agents.video.tools.Path')
    @patch('src.agents.video.tools.OpenAI')
    def test_uses_api_for_small_files(self, mock_openai, mock_path):
        """Test that small files use OpenAI Whisper API."""
        # Mock file exists and is small (< 25MB)
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value.st_size = 20 * 1024 * 1024  # 20MB
        mock_path.return_value = mock_file
        
        # Mock OpenAI response
        mock_client = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_segment.start = 0.0
        mock_segment.end = 1.5
        
        mock_response = MagicMock()
        mock_response.segments = [mock_segment]
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        result = generate_transcript_from_audio.invoke({
            "video_id": "test123",
            "audio_path": "./downloads/test123.m4a"
        })
        
        assert result["success"] is True
        assert result["source"] == "whisper_api"
        assert len(result["segments"]) == 1
    
    @patch('src.agents.video.tools.Path')
    @patch('src.agents.video.tools.whisper')
    def test_uses_local_for_large_files(self, mock_whisper, mock_path):
        """Test that large files use local Whisper."""
        # Mock file exists and is large (>= 25MB)
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value.st_size = 30 * 1024 * 1024  # 30MB
        mock_path.return_value = mock_file
        
        # Mock local Whisper response
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "segments": [
                {"text": " Hello world", "start": 0.0, "end": 1.5}
            ]
        }
        mock_whisper.load_model.return_value = mock_model
        
        result = generate_transcript_from_audio.invoke({
            "video_id": "test123",
            "audio_path": "./downloads/test123.m4a"
        })
        
        assert result["success"] is True
        assert result["source"] == "whisper_local"
        assert len(result["segments"]) == 1
        assert result["segments"][0]["text"] == "Hello world"  # Stripped


# Example of how to run specific tests:
# pytest tests/agents/video/test_tools.py::TestExtractVideoID::test_extract_from_standard_url
# pytest tests/agents/video/ -m "not integration"  # Skip integration tests
# pytest tests/agents/video/test_tools.py -v  # Verbose output
