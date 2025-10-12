"""
Tests for LLM-based video agent

These tests are minimal because LLM agents are non-deterministic.
We only test structure and basic functionality, not exact outputs.

Run tests with:
    pytest tests/agents/video/test_agent.py
    pytest tests/agents/video/test_agent.py -v
"""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.video.agent import (
    create_video_agent,
    analyze_video,
    VideoAgentState,
)


class TestVideoAgentCreation:
    """Tests for agent creation and structure."""
    
    @patch('src.agents.video.agent.ChatOpenAI')
    def test_create_video_agent(self, mock_openai):
        """Test that agent can be created."""
        mock_llm = MagicMock()
        mock_openai.return_value = mock_llm
        
        agent = create_video_agent()
        
        assert agent is not None
        mock_openai.assert_called_once()
    
    @patch('src.agents.video.agent.ChatOpenAI')
    def test_create_agent_with_custom_model(self, mock_openai):
        """Test agent creation with custom model."""
        mock_llm = MagicMock()
        mock_openai.return_value = mock_llm
        
        agent = create_video_agent(model="gpt-4", temperature=0.5)
        
        mock_openai.assert_called_with(model="gpt-4", temperature=0.5)
    
    @patch('src.agents.video.agent.get_tools')
    @patch('src.agents.video.agent.ChatOpenAI')
    def test_agent_has_tools(self, mock_openai, mock_get_tools):
        """Test that agent is created with tools."""
        mock_llm = MagicMock()
        mock_openai.return_value = mock_llm
        mock_tools = [MagicMock(), MagicMock()]
        mock_get_tools.return_value = mock_tools
        
        agent = create_video_agent()
        
        mock_get_tools.assert_called_once()


class TestVideoAgentState:
    """Tests for agent state structure."""
    
    def test_video_agent_state_structure(self):
        """Test VideoAgentState has expected fields."""
        # This is a TypedDict, so we just verify it's importable
        # and has the right structure
        assert hasattr(VideoAgentState, '__annotations__')
        annotations = VideoAgentState.__annotations__
        
        assert 'youtube_url' in annotations
        assert 'messages' in annotations
        assert 'video_id' in annotations
        assert 'metadata' in annotations
        assert 'transcript' in annotations
        assert 'error' in annotations


class TestAnalyzeVideo:
    """Tests for the analyze_video function."""
    
    @patch('src.agents.video.agent.create_video_agent')
    def test_analyze_video_creates_agent(self, mock_create_agent):
        """Test that analyze_video creates an agent."""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [
                MagicMock(content="Analysis complete")
            ]
        }
        mock_create_agent.return_value = mock_agent
        
        result = analyze_video("https://youtube.com/watch?v=test123")
        
        mock_create_agent.assert_called_once()
        mock_agent.invoke.assert_called_once()
    
    @patch('src.agents.video.agent.create_video_agent')
    def test_analyze_video_returns_dict(self, mock_create_agent):
        """Test that analyze_video returns expected structure."""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [
                MagicMock(content="Analysis complete")
            ]
        }
        mock_create_agent.return_value = mock_agent
        
        result = analyze_video("https://youtube.com/watch?v=test123")
        
        # Verify result structure
        assert isinstance(result, dict)
        assert "youtube_url" in result
        assert "video_id" in result
        assert "metadata" in result
        assert "transcript" in result
        assert "summary" in result
        assert "messages" in result
        assert result["youtube_url"] == "https://youtube.com/watch?v=test123"
    
    @patch('src.agents.video.agent.create_video_agent')
    def test_analyze_video_with_custom_model(self, mock_create_agent):
        """Test analyze_video with custom model parameter."""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [MagicMock(content="Done")]
        }
        mock_create_agent.return_value = mock_agent
        
        result = analyze_video(
            "https://youtube.com/watch?v=test123",
            model="gpt-4"
        )
        
        mock_create_agent.assert_called_with(model="gpt-4")


# Note: We don't test exact LLM outputs because they're non-deterministic
# For testing actual agent behavior, use integration tests with real API calls
# or mock the LLM responses at a lower level

# Example integration test (requires API key, marked to skip by default):
@pytest.mark.integration
@pytest.mark.skip(reason="Requires OpenAI API key and makes real API calls")
class TestVideoAgentIntegration:
    """Integration tests with real LLM (expensive, slow)."""
    
    def test_agent_analyzes_video(self):
        """Test agent can analyze a real video."""
        # This would make real API calls
        result = analyze_video("https://youtube.com/watch?v=dQw4w9WgXcQ")
        
        assert result["video_id"] is not None
        assert result["summary"] is not None


# Example of how to run tests:
# pytest tests/agents/video/test_agent.py -v
# pytest tests/agents/video/test_agent.py -k "test_create"
# pytest tests/agents/video/ -m "not integration"  # Skip expensive tests
