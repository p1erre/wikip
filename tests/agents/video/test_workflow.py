"""
Tests for video analysis workflow

These tests verify the deterministic workflow behavior.
All external dependencies are mocked for fast, reliable tests.

Run tests with:
    pytest tests/agents/video/test_workflow.py
    pytest tests/agents/video/test_workflow.py -v
    pytest tests/agents/video/test_workflow.py -k test_successful
"""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.video.workflow import (
    analyze_video_workflow,
    get_transcript,
)


class TestAnalyzeVideoWorkflow:
    """Tests for the main video analysis workflow."""
    
    @patch('src.agents.video.workflow.extract_video_id_from_url')
    @patch('src.agents.video.workflow.get_video_metadata')
    @patch('src.agents.video.workflow.get_youtube_transcript')
    def test_successful_workflow_with_youtube_transcript(
        self, mock_transcript, mock_metadata, mock_extract_id
    ):
        """Test workflow when YouTube transcript is available."""
        # Mock successful responses
        mock_extract_id.invoke.return_value = {
            "success": True,
            "video_id": "test123"
        }
        mock_metadata.invoke.return_value = {
            "success": True,
            "video_id": "test123",
            "title": "Test Video",
            "duration": 120,
            "channel": "Test Channel"
        }
        mock_transcript.invoke.return_value = {
            "success": True,
            "video_id": "test123",
            "num_segments": 10,
            "segments": [
                {"text": "Hello", "start": 0.0, "end": 1.0, "duration": 1.0},
                {"text": "World", "start": 1.0, "end": 2.0, "duration": 1.0}
            ],
            "total_duration": 2.0
        }
        
        # Run workflow
        result = analyze_video_workflow("https://youtube.com/watch?v=test123")
        
        # Verify results
        assert result["video_id"] == "test123"
        assert result["youtube_url"] == "https://youtube.com/watch?v=test123"
        assert "extract_id" in result["steps_completed"]
        assert "get_metadata" in result["steps_completed"]
        assert "get_youtube_transcript" in result["steps_completed"]
        assert result["transcript"] is not None
        assert result["transcript"]["num_segments"] == 10
        assert len(result["errors"]) == 0
        assert result["audio_path"] is None  # No download needed
    
    @patch('src.agents.video.workflow.extract_video_id_from_url')
    @patch('src.agents.video.workflow.get_video_metadata')
    @patch('src.agents.video.workflow.get_youtube_transcript')
    @patch('src.agents.video.workflow.download_youtube_content')
    @patch('src.agents.video.workflow.generate_transcript_from_audio')
    def test_workflow_falls_back_to_whisper(
        self, mock_whisper, mock_download, mock_transcript,
        mock_metadata, mock_extract_id
    ):
        """Test workflow downloads and transcribes when no YouTube transcript."""
        # Mock responses
        mock_extract_id.invoke.return_value = {
            "success": True,
            "video_id": "test123"
        }
        mock_metadata.invoke.return_value = {
            "success": True,
            "title": "Test Video"
        }
        mock_transcript.invoke.return_value = {
            "success": False,
            "error": "No transcript available"
        }
        mock_download.invoke.return_value = {
            "success": True,
            "file_path": "./downloads/test123.m4a",
            "video_id": "test123"
        }
        mock_whisper.invoke.return_value = {
            "success": True,
            "video_id": "test123",
            "num_segments": 5,
            "segments": [
                {"text": "Generated", "start": 0.0, "end": 1.0, "duration": 1.0}
            ],
            "total_duration": 1.0,
            "source": "whisper_api"
        }
        
        # Run workflow
        result = analyze_video_workflow("https://youtube.com/watch?v=test123")
        
        # Verify fallback behavior
        assert "download_audio" in result["steps_completed"]
        assert "generate_transcript" in result["steps_completed"]
        assert result["audio_path"] == "./downloads/test123.m4a"
        assert result["transcript"]["source"] == "whisper_api"
        assert "No YouTube transcript available" in result["errors"]
    
    @patch('src.agents.video.workflow.extract_video_id_from_url')
    def test_workflow_handles_invalid_url(self, mock_extract_id):
        """Test workflow handles invalid URL gracefully."""
        mock_extract_id.invoke.return_value = {
            "success": False,
            "error": "Could not extract video ID"
        }
        
        result = analyze_video_workflow("https://example.com/not-youtube")
        
        assert result["video_id"] is None
        assert len(result["errors"]) > 0
        assert "Failed to extract video ID" in result["errors"][0]
        assert len(result["steps_completed"]) == 0
    
    @patch('src.agents.video.workflow.extract_video_id_from_url')
    @patch('src.agents.video.workflow.get_video_metadata')
    def test_workflow_continues_on_metadata_failure(
        self, mock_metadata, mock_extract_id
    ):
        """Test workflow continues even if metadata fetch fails."""
        mock_extract_id.invoke.return_value = {
            "success": True,
            "video_id": "test123"
        }
        mock_metadata.invoke.return_value = {
            "success": False,
            "error": "Video not found"
        }
        
        # Mock transcript to succeed so workflow completes
        with patch('src.agents.video.workflow.get_youtube_transcript') as mock_transcript:
            mock_transcript.invoke.return_value = {
                "success": True,
                "num_segments": 1,
                "segments": [{"text": "Test", "start": 0, "end": 1}]
            }
            
            result = analyze_video_workflow("https://youtube.com/watch?v=test123")
            
            assert result["video_id"] == "test123"
            assert "extract_id" in result["steps_completed"]
            assert "get_metadata" not in result["steps_completed"]
            assert "Failed to get metadata" in result["errors"][0]
    
    @patch('src.agents.video.workflow.extract_video_id_from_url')
    @patch('src.agents.video.workflow.get_video_metadata')
    @patch('src.agents.video.workflow.get_youtube_transcript')
    @patch('src.agents.video.workflow.download_youtube_content')
    def test_workflow_handles_download_failure(
        self, mock_download, mock_transcript, mock_metadata, mock_extract_id
    ):
        """Test workflow handles download failure gracefully."""
        mock_extract_id.invoke.return_value = {"success": True, "video_id": "test123"}
        mock_metadata.invoke.return_value = {"success": True, "title": "Test"}
        mock_transcript.invoke.return_value = {"success": False}
        mock_download.invoke.return_value = {
            "success": False,
            "error": "Download failed"
        }
        
        result = analyze_video_workflow("https://youtube.com/watch?v=test123")
        
        assert "download_audio" not in result["steps_completed"]
        assert "Failed to download" in result["errors"][-1]
        assert result["transcript"] is None
    
    @patch('src.agents.video.workflow.extract_video_id_from_url')
    @patch('src.agents.video.workflow.get_video_metadata')
    @patch('src.agents.video.workflow.get_youtube_transcript')
    @patch('src.agents.video.workflow.download_youtube_content')
    @patch('src.agents.video.workflow.generate_transcript_from_audio')
    def test_force_download_mode(
        self, mock_whisper, mock_download, mock_transcript,
        mock_metadata, mock_extract_id
    ):
        """Test force_download skips YouTube transcript."""
        mock_extract_id.invoke.return_value = {"success": True, "video_id": "test123"}
        mock_metadata.invoke.return_value = {"success": True, "title": "Test"}
        mock_transcript.invoke.return_value = {
            "success": True,
            "num_segments": 10,
            "segments": [{"text": "YouTube", "start": 0, "end": 1}]
        }
        mock_download.invoke.return_value = {
            "success": True,
            "file_path": "./downloads/test123.m4a"
        }
        mock_whisper.invoke.return_value = {
            "success": True,
            "num_segments": 5,
            "segments": [{"text": "Whisper", "start": 0, "end": 1}],
            "source": "whisper_local"
        }
        
        # Run with force_download=True
        result = analyze_video_workflow(
            "https://youtube.com/watch?v=test123",
            force_download=True
        )
        
        # Should download and transcribe even though YouTube transcript exists
        assert "download_audio" in result["steps_completed"]
        assert "generate_transcript" in result["steps_completed"]
        assert result["transcript"]["source"] == "whisper_local"


class TestGetTranscript:
    """Tests for the simplified get_transcript interface."""
    
    @patch('src.agents.video.workflow.analyze_video_workflow')
    def test_get_transcript_success(self, mock_workflow):
        """Test get_transcript returns transcript when available."""
        mock_workflow.return_value = {
            "video_id": "test123",
            "transcript": {
                "success": True,
                "num_segments": 5,
                "segments": [{"text": "Hello", "start": 0, "end": 1}]
            },
            "errors": []
        }
        
        result = get_transcript("https://youtube.com/watch?v=test123")
        
        assert result["success"] is True
        assert result["num_segments"] == 5
    
    @patch('src.agents.video.workflow.analyze_video_workflow')
    def test_get_transcript_failure(self, mock_workflow):
        """Test get_transcript returns error when transcript unavailable."""
        mock_workflow.return_value = {
            "video_id": "test123",
            "transcript": None,
            "errors": ["No transcript available", "Download failed"]
        }
        
        result = get_transcript("https://youtube.com/watch?v=test123")
        
        assert result["success"] is False
        assert "error" in result
        assert "details" in result
        assert len(result["details"]) == 2
    
    @patch('src.agents.video.workflow.analyze_video_workflow')
    def test_get_transcript_prefer_youtube(self, mock_workflow):
        """Test prefer_youtube parameter is passed correctly."""
        mock_workflow.return_value = {
            "transcript": {"success": True, "segments": []},
            "errors": []
        }
        
        # Call with prefer_youtube=True (default)
        get_transcript("https://youtube.com/watch?v=test123", prefer_youtube=True)
        
        # Verify force_download=False was passed
        mock_workflow.assert_called_with(
            "https://youtube.com/watch?v=test123",
            force_download=False,
            output_dir="./downloads"
        )
    
    @patch('src.agents.video.workflow.analyze_video_workflow')
    def test_get_transcript_force_whisper(self, mock_workflow):
        """Test prefer_youtube=False forces Whisper transcription."""
        mock_workflow.return_value = {
            "transcript": {"success": True, "segments": []},
            "errors": []
        }
        
        # Call with prefer_youtube=False
        get_transcript("https://youtube.com/watch?v=test123", prefer_youtube=False)
        
        # Verify force_download=True was passed
        mock_workflow.assert_called_with(
            "https://youtube.com/watch?v=test123",
            force_download=True,
            output_dir="./downloads"
        )


# Example of how to run tests:
# pytest tests/agents/video/test_workflow.py -v
# pytest tests/agents/video/test_workflow.py::TestAnalyzeVideoWorkflow::test_successful_workflow_with_youtube_transcript
# pytest tests/agents/video/test_workflow.py -k "test_force"
