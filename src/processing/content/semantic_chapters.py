"""
Semantic chapter detection

Advanced chapter creation that detects natural topic boundaries
instead of using fixed time intervals.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def create_semantic_chapters(
    transcript: dict,
    model: str = "gpt-4o-mini",
    provider: str = "openai",
    min_chapter_minutes: int = 3,
    max_chapter_minutes: int = 10,
) -> List[Dict[str, Any]]:
    """
    Create chapters based on semantic topic boundaries.
    
    This uses an LLM to analyze the transcript and identify natural
    topic transitions, resulting in more meaningful chapter breaks.
    
    Args:
        transcript: Transcript dict with segments
        model: LLM model to use (gpt-4o-mini is fast and cheap)
        provider: LLM provider
        min_chapter_minutes: Minimum chapter length
        max_chapter_minutes: Maximum chapter length
        
    Returns:
        List of chapter dicts with meaningful titles and natural boundaries
    """
    from src.processing.content.generation import format_transcript_for_llm
    
    logger.info("Analyzing transcript for semantic chapter boundaries...")
    
    # Format full transcript
    formatted_transcript = format_transcript_for_llm(transcript)
    
    # Build prompt for semantic analysis
    prompt = _build_semantic_analysis_prompt(
        formatted_transcript,
        min_chapter_minutes,
        max_chapter_minutes
    )
    
    try:
        # Call LLM
        if provider == "openai":
            from src.processing.content.generation import _call_openai
            response = _call_openai(prompt, model, temperature=0.3)
        elif provider == "anthropic":
            from src.processing.content.generation import _call_anthropic
            response = _call_anthropic(prompt, model, temperature=0.3)
        elif provider == "openrouter":
            from src.processing.content.generation import _call_openrouter
            response = _call_openrouter(prompt, model, temperature=0.3)
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        # Parse response
        chapters = _parse_semantic_chapters(response)
        
        if chapters:
            logger.info(f"Created {len(chapters)} semantic chapters:")
            for i, ch in enumerate(chapters, 1):
                logger.info(f"   {i}. {ch['title']} ({ch['start_time']//60:.0f}-{ch['end_time']//60:.0f} min)")
            return chapters
        else:
            logger.warning("Failed to parse semantic chapters, falling back to time-based")
            from src.processing.content.chapters import auto_create_chapters
            return auto_create_chapters(transcript)
    
    except Exception as e:
        logger.error(f"Semantic chapter detection failed: {e}, falling back to time-based")
        from src.processing.content.chapters import auto_create_chapters
        return auto_create_chapters(transcript)


def _build_semantic_analysis_prompt(
    transcript_text: str,
    min_minutes: int,
    max_minutes: int
) -> str:
    """Build prompt for semantic chapter detection"""
    
    return f"""You are analyzing a video transcript to identify natural topic boundaries and create meaningful chapters.

TRANSCRIPT (with timestamps):
{transcript_text}

YOUR TASK:
Analyze the transcript and identify where major topics begin and end. Create chapters that:
1. Represent distinct topics or themes
2. Have natural transitions between them
3. Are between {min_minutes}-{max_minutes} minutes long
4. Have descriptive, specific titles (3-7 words)

GUIDELINES:
- Look for topic shifts, new concepts being introduced, or transitions in the speaker's narrative
- Avoid breaking mid-topic or mid-explanation
- Create 5-12 chapters total (depending on content)
- Titles should be informative and specific to the content

OUTPUT FORMAT:
Return a JSON array of chapters with this structure:
[
  {{
    "title": "Introduction to Forward Deployed Engineers",
    "start_time": 0,
    "end_time": 420,
    "summary": "Brief 1-sentence summary of what this chapter covers"
  }},
  ...
]

IMPORTANT: 
- Use actual timestamps from the transcript
- Ensure chapters don't overlap
- Cover the entire video duration
- Return ONLY the JSON array, no other text

JSON array:
"""


def _parse_semantic_chapters(response: str) -> List[Dict[str, Any]]:
    """Parse LLM response into chapter list"""
    import json
    import re
    
    try:
        # Extract JSON array from response
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            chapters = json.loads(json_match.group())
            
            # Validate structure
            for chapter in chapters:
                if not all(k in chapter for k in ['title', 'start_time', 'end_time']):
                    logger.warning("Invalid chapter structure, missing required fields")
                    return []
            
            return chapters
        else:
            logger.warning("Could not find JSON array in response")
            return []
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error parsing chapters: {e}")
        return []


def create_hybrid_chapters(
    transcript: dict,
    model: str = "gpt-4o-mini",
    provider: str = "openai",
) -> List[Dict[str, Any]]:
    """
    Hybrid approach: Try semantic detection, fall back to time-based with smart titles.
    
    This is the RECOMMENDED approach - best of both worlds.
    """
    logger.info("Using hybrid chapter creation...")
    
    # Try semantic detection first
    try:
        chapters = create_semantic_chapters(transcript, model, provider)
        if chapters and len(chapters) >= 3:  # Minimum viable chapters
            logger.info("✅ Using semantic chapters")
            return chapters
    except Exception as e:
        logger.warning(f"Semantic detection failed: {e}")
    
    # Fall back to time-based with smart titles
    logger.info("Falling back to time-based chapters with generated titles")
    from src.processing.content.chapters import auto_create_chapters
    return auto_create_chapters(
        transcript,
        minutes_per_chapter=5,
        generate_titles=True,
        model=model,
        provider=provider
    )
