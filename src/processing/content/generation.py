"""
Simple content generation from transcripts

Direct LLM calls for generating booklets without using agents.
This is the simplest approach: transcript → LLM → formatted content
"""

import logging
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)


def format_transcript_for_llm(transcript: dict, max_chars: int = 300000) -> str:
    """
    Format transcript segments into readable text for LLM.
    
    Args:
        transcript: Transcript dict with 'segments' list
        max_chars: Maximum characters to include (default: 300k for GPT-4o/Claude)
        
    Returns:
        Formatted transcript text with timestamps
        
    Note:
        Modern LLMs (GPT-4o, Claude 3.5) can handle 128k+ tokens (~400k chars).
        Default limit of 300k chars is safe for most videos.
    """
    segments = transcript.get('segments', [])
    
    lines = []
    total_chars = 0
    
    for segment in segments:
        start = segment.get('start', 0)
        text = segment.get('text', '').strip()
        
        # Format: [MM:SS] Text
        minutes = int(start // 60)
        seconds = int(start % 60)
        line = f"[{minutes:02d}:{seconds:02d}] {text}"
        
        # Check if we're approaching limit
        if total_chars + len(line) > max_chars:
            lines.append("\n[... transcript truncated due to length ...]")
            break
        
        lines.append(line)
        total_chars += len(line)
    
    return "\n".join(lines)


def generate_booklet_from_transcript(
    transcript: dict,
    video_title: str,
    video_url: Optional[str] = None,
    model: str = "gpt-4o",
    provider: str = "openai",
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """
    Generate a booklet from a video transcript using a simple LLM call.
    
    This is the simplest workflow:
    1. Format transcript
    2. Send to LLM with prompt
    3. Return formatted booklet
    
    Args:
        transcript: Transcript dict with segments
        video_title: Title of the video
        video_url: Optional URL to include in booklet
        model: LLM model to use
        provider: LLM provider ('openai', 'anthropic', 'openrouter')
        temperature: LLM temperature (0.7 for creative writing)
        
    Returns:
        Dict with:
            - success: bool
            - content: str (markdown booklet)
            - model: str (model used)
            - error: str (if failed)
    """
    logger.info(f"Generating booklet from transcript using {provider}/{model}")
    
    try:
        # Format transcript
        formatted_transcript = format_transcript_for_llm(transcript)
        
        # Build prompt
        prompt = _build_booklet_prompt(
            transcript_text=formatted_transcript,
            video_title=video_title,
            video_url=video_url
        )
        
        # Log prompt details
        logger.info(f"Prompt length: {len(prompt):,} characters (~{len(prompt)//4:,} tokens)")
        logger.info(f"Transcript length: {len(formatted_transcript):,} characters")
        
        # Call LLM based on provider
        if provider == "openai":
            content = _call_openai(prompt, model, temperature)
        elif provider == "anthropic":
            content = _call_anthropic(prompt, model, temperature)
        elif provider == "openrouter":
            content = _call_openrouter(prompt, model, temperature)
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        logger.info(f"✅ Booklet generated successfully ({len(content)} chars)")
        
        return {
            "success": True,
            "content": content,
            "model": f"{provider}/{model}",
            "length": len(content),
        }
        
    except Exception as e:
        logger.error(f"Failed to generate booklet: {e}")
        return {
            "success": False,
            "error": str(e),
            "model": f"{provider}/{model}",
        }


def _build_booklet_prompt(
    transcript_text: str,
    video_title: str,
    video_url: Optional[str] = None
) -> str:
    """Build the prompt for booklet generation"""
    
    prompt = f"""You are an expert content writer. Your task is to transform a video transcript into a well-structured, engaging booklet.

VIDEO INFORMATION:
Title: {video_title}
"""
    
    if video_url:
        prompt += f"URL: {video_url}\n"
    
    prompt += f"""

TRANSCRIPT:
{transcript_text}

YOUR TASK:
Transform this ENTIRE transcript into a comprehensive, detailed booklet. This should be a COMPLETE educational resource, not a summary.

IMPORTANT: Cover ALL major topics and sections from the transcript. The booklet should be thorough and detailed.

1. STRUCTURE:
   - Start with an engaging introduction that outlines what the video covers
   - Create multiple sections (aim for 5-10+ sections depending on content)
   - Each section should thoroughly cover its topic
   - Use descriptive headers and subheaders to organize content
   - End with a comprehensive conclusion

2. CONTENT COVERAGE:
   - Cover ALL major topics discussed in the transcript
   - Preserve all important information, examples, and insights
   - Include specific details, examples, and explanations mentioned
   - Expand on ideas to make them clearer in written form
   - Don't skip or summarize - be thorough and complete

3. WRITING STYLE:
   - Convert spoken language into polished, professional prose
   - Remove filler words but keep the substance
   - Maintain the speaker's voice and perspective
   - Use clear, engaging language
   - Make complex ideas accessible

4. FORMATTING:
   - Use markdown: headers (##, ###), **bold**, *italic*, lists
   - Create clear visual hierarchy with headers
   - Use bullet points for lists of concepts
   - Use numbered lists for sequential steps or processes
   - Add emphasis to key terms and concepts

5. LENGTH:
   - This should be a COMPREHENSIVE booklet, not a brief summary
   - Aim for thorough coverage of all topics
   - Each major section should have substantial content
   - Don't be brief - be complete and educational

OUTPUT FORMAT:
Return ONLY the booklet content in markdown format. No meta-commentary.

Begin the comprehensive booklet now:
"""
    
    return prompt


def _call_openai(prompt: str, model: str, temperature: float) -> str:
    """Call OpenAI API"""
    from openai import OpenAI
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
    )
    
    return response.choices[0].message.content


def _call_anthropic(prompt: str, model: str, temperature: float) -> str:
    """Call Anthropic API"""
    import anthropic
    
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=temperature,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.content[0].text


def _call_openrouter(prompt: str, model: str, temperature: float) -> str:
    """Call OpenRouter API"""
    from openai import OpenAI
    
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
    )
    
    return response.choices[0].message.content
