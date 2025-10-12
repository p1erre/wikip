"""
Content Generation Tools

Simple tool for preparing video data for content generation.
"""

import logging
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ContentDataInput(BaseModel):
    """Input schema for preparing content data"""
    
    video_id: str = Field(description="YouTube video ID")
    metadata: dict = Field(description="Video metadata dictionary")
    transcript: dict = Field(description="Transcript dictionary with segments")


@tool(args_schema=ContentDataInput)
def prepare_content_data(video_id: str, metadata: dict, transcript: dict) -> dict[str, Any]:
    """
    Prepare and structure video data for content generation.
    
    This tool extracts chapters from metadata and organizes transcript
    segments by chapter, making it easy to generate structured content.
    
    Args:
        video_id: YouTube video ID
        metadata: Video metadata from get_video_metadata
        transcript: Transcript data from get_youtube_transcript
        
    Returns:
        Dictionary with organized content data including chapters and their transcripts
        
    Example:
        >>> data = prepare_content_data("abc123", metadata, transcript)
        >>> data['chapters'][0]
        {
            'title': 'Introduction',
            'start_time': 0,
            'end_time': 120,
            'transcript': 'Welcome to this video...'
        }
    """
    logger.info(f"Preparing content data for video: {video_id}")
    
    try:
        # Extract basic info
        video_title = metadata.get('title', 'Untitled Video')
        video_description = metadata.get('description', '')
        duration = metadata.get('duration', 0)
        channel = metadata.get('channel', 'Unknown')
        
        # Extract chapters from metadata
        chapters = []
        has_chapters = False
        
        if 'chapters' in metadata and metadata['chapters']:
            has_chapters = True
            raw_chapters = metadata['chapters']
            
            for i, chapter in enumerate(raw_chapters):
                chapters.append({
                    'index': i,
                    'title': chapter.get('title', f'Chapter {i+1}'),
                    'start_time': chapter.get('start_time', 0),
                    'end_time': chapter.get('end_time', duration),
                })
        else:
            # No chapters - treat entire video as one chapter
            chapters.append({
                'index': 0,
                'title': video_title,
                'start_time': 0,
                'end_time': duration,
            })
        
        # Get transcript segments
        transcript_segments = transcript.get('segments', [])
        
        # Match transcript segments to chapters
        for chapter in chapters:
            chapter_start = chapter['start_time']
            chapter_end = chapter['end_time']
            
            # Find all transcript segments within this chapter's time range
            chapter_segments = [
                seg for seg in transcript_segments
                if seg['start'] >= chapter_start and seg['start'] < chapter_end
            ]
            
            # Combine segment texts into chapter transcript
            chapter_transcript = ' '.join(seg['text'] for seg in chapter_segments)
            chapter['transcript'] = chapter_transcript
            chapter['num_segments'] = len(chapter_segments)
        
        result = {
            'success': True,
            'video_id': video_id,
            'video_title': video_title,
            'video_description': video_description,
            'channel': channel,
            'duration': duration,
            'has_chapters': has_chapters,
            'num_chapters': len(chapters),
            'chapters': chapters,
            'total_transcript_length': len(' '.join(seg['text'] for seg in transcript_segments)),
        }
        
        logger.info(f"Successfully prepared content data with {len(chapters)} chapters")
        return result
        
    except Exception as e:
        error_msg = f"Failed to prepare content data: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }


@tool(args_schema=ContentDataInput)
def create_chapter_markdown(video_id: str, metadata: dict, transcript: dict) -> dict[str, Any]:
    """
    Create a markdown document organized by chapters with full transcript content.
    
    This tool takes video metadata (with chapters) and transcript (with timestamped segments),
    then creates a single markdown document where each chapter contains all the transcript
    text that falls within that chapter's time range.
    
    Args:
        video_id: YouTube video ID
        metadata: Video metadata dictionary containing chapter information
        transcript: Transcript dictionary with timestamped segments
        
    Returns:
        Dictionary with success status and markdown content
        
    Example:
        >>> markdown_result = create_chapter_markdown("abc123", metadata, transcript)
        >>> print(markdown_result['markdown'])
        # Video Title
        
        ## Chapter 1: Introduction (0s - 120s)
        [Full transcript text for this chapter...]
    """
    logger.info(f"Creating chapter markdown for video: {video_id}")
    
    try:
        # Extract basic info
        video_title = metadata.get('title', 'Untitled Video')
        channel = metadata.get('channel', 'Unknown')
        duration = metadata.get('duration', 0)
        
        # Extract chapters from metadata
        chapters = []
        has_chapters = False
        
        if 'chapters' in metadata and metadata['chapters']:
            has_chapters = True
            raw_chapters = metadata['chapters']
            
            for i, chapter in enumerate(raw_chapters):
                chapters.append({
                    'index': i,
                    'title': chapter.get('title', f'Chapter {i+1}'),
                    'start_time': chapter.get('start_time', 0),
                    'end_time': chapter.get('end_time', duration),
                })
        else:
            # No chapters - treat entire video as one chapter
            chapters.append({
                'index': 0,
                'title': video_title,
                'start_time': 0,
                'end_time': duration,
            })
        
        # Get transcript segments
        transcript_segments = transcript.get('segments', [])
        
        # Build markdown document
        markdown_lines = []
        
        # Add title and metadata
        markdown_lines.append(f"# {video_title}\n")
        markdown_lines.append(f"**Channel:** {channel}\n")
        markdown_lines.append(f"**Duration:** {duration} seconds\n")
        markdown_lines.append("---\n")
        
        # Process each chapter
        for chapter in chapters:
            chapter_start = chapter['start_time']
            chapter_end = chapter['end_time']
            
            # Add chapter header
            markdown_lines.append(f"\n## {chapter['title']} ({chapter_start}s - {chapter_end}s)\n")
            
            # Find all transcript segments within this chapter's time range
            chapter_segments = [
                seg for seg in transcript_segments
                if seg['start'] >= chapter_start and seg['start'] < chapter_end
            ]
            
            # Concatenate all segment texts
            if chapter_segments:
                chapter_text = ' '.join(seg['text'] for seg in chapter_segments)
                markdown_lines.append(f"{chapter_text}\n")
            else:
                markdown_lines.append("*No transcript available for this chapter.*\n")
        
        # Join all lines into final markdown
        markdown_content = '\n'.join(markdown_lines)
        
        result = {
            'success': True,
            'video_id': video_id,
            'video_title': video_title,
            'has_chapters': has_chapters,
            'num_chapters': len(chapters),
            'markdown': markdown_content,
            'total_length': len(markdown_content),
        }
        
        logger.info(f"Successfully created chapter markdown with {len(chapters)} chapters")
        return result
        
    except Exception as e:
        error_msg = f"Failed to create chapter markdown: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }


def get_content_tools() -> list:
    """
    Get all content generation tools.
    
    Returns:
        List of tool functions for content generation
    """
    return [prepare_content_data, create_chapter_markdown]
