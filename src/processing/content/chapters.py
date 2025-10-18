"""
Chapter-based content generation

Generate comprehensive booklets by processing each chapter/section independently.
This produces higher quality, more detailed output than single-pass generation.
"""

import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    
    Rough approximation: 1 token ≈ 4 characters for English text.
    This is conservative (actual is often better).
    """
    return len(text) // 4


def log_prompt_stats(prompt: str, context: str = ""):
    """
    Log prompt size statistics before sending to LLM.
    
    Args:
        prompt: The prompt text
        context: Description of what this prompt is for
    """
    char_count = len(prompt)
    token_estimate = estimate_tokens(prompt)
    
    logger.info(f"   📊 Prompt stats{' (' + context + ')' if context else ''}:")
    logger.info(f"      Characters: {char_count:,}")
    logger.info(f"      Estimated tokens: ~{token_estimate:,}")
    
    # Warn if approaching limits
    if token_estimate > 100000:
        logger.warning(f"      ⚠️  Very large prompt! May hit token limits.")
    elif token_estimate > 50000:
        logger.info(f"      ℹ️  Large prompt (but within GPT-4o limits)")
    
    return {'chars': char_count, 'tokens': token_estimate}


def validate_section_content(content: str, min_chars: int = 500) -> bool:
    """
    Validate that LLM generated acceptable content.
    
    Args:
        content: Generated content
        min_chars: Minimum acceptable character count
        
    Returns:
        True if valid, False otherwise
    """
    if not content or not content.strip():
        logger.warning("Content is empty")
        return False
    
    if len(content) < min_chars:
        logger.warning(f"Content too short: {len(content)} chars (min: {min_chars})")
        return False
    
    # Check if it starts with markdown heading
    if not content.strip().startswith('##'):
        logger.warning("Content doesn't start with ## heading")
        # Don't fail, just warn
    
    return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True
)
def call_llm_with_retry(provider: str, model: str, prompt: str, temperature: float):
    """
    Call LLM with automatic retry on transient failures.
    
    Retries up to 3 times with exponential backoff for:
    - Connection errors
    - Timeout errors
    - Rate limit errors (via exponential backoff)
    """
    if provider == "openai":
        from src.processing.content.generation import _call_openai
        return _call_openai(prompt, model, temperature)
    elif provider == "anthropic":
        from src.processing.content.generation import _call_anthropic
        return _call_anthropic(prompt, model, temperature)
    elif provider == "openrouter":
        from src.processing.content.generation import _call_openrouter
        return _call_openrouter(prompt, model, temperature)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def create_chapters(
    transcript: dict,
    strategy: str = "auto",
    model: str = "gpt-4o-mini",
    provider: str = "openai",
    minutes_per_chapter: int = 5,
    min_chapter_minutes: int = 3,
    max_chapter_minutes: int = 10,
) -> List[Dict[str, Any]]:
    """
    Create chapters intelligently with automatic strategy selection.
    
    This is the MAIN API for chapter creation. It automatically chooses
    the best approach and falls back gracefully if needed.
    
    Args:
        transcript: Transcript dict with segments
        strategy: "auto" (recommended), "semantic", or "time-based"
            - auto: Tries semantic, falls back to time-based with titles
            - semantic: Only semantic detection (may fail)
            - time-based: Fixed intervals with generated titles
        model: LLM model to use (gpt-4o-mini is fast and cheap)
        provider: LLM provider
        minutes_per_chapter: For time-based strategy
        min_chapter_minutes: For semantic strategy
        max_chapter_minutes: For semantic strategy
        
    Returns:
        List of chapter dicts with title, start_time, end_time
        
    Example:
        >>> # Recommended: auto strategy
        >>> chapters = create_chapters(transcript)
        >>> 
        >>> # Force semantic only
        >>> chapters = create_chapters(transcript, strategy="semantic")
    """
    logger.info(f"Creating chapters (strategy: {strategy})...")
    
    if strategy == "time-based":
        return _create_time_based_chapters(
            transcript, minutes_per_chapter, model, provider
        )
    
    if strategy == "semantic":
        return _create_semantic_chapters(
            transcript, model, provider, min_chapter_minutes, max_chapter_minutes
        )
    
    # Default: auto (semantic with fallback)
    logger.info("Trying semantic chapter detection...")
    try:
        chapters = _create_semantic_chapters(
            transcript, model, provider, min_chapter_minutes, max_chapter_minutes
        )
        if chapters and len(chapters) >= 3:
            logger.info(f"✅ Using {len(chapters)} semantic chapters")
            return chapters
        else:
            logger.info("Semantic detection returned too few chapters, falling back...")
    except Exception as e:
        logger.warning(f"Semantic detection failed: {e}, falling back to time-based...")
    
    # Fallback to time-based with titles
    logger.info("Using time-based chapters with generated titles")
    return _create_time_based_chapters(
        transcript, minutes_per_chapter, model, provider
    )


# Backward compatibility
def auto_create_chapters(
    transcript: dict, 
    minutes_per_chapter: int = 5,
    generate_titles: bool = True,
    model: str = "gpt-4o-mini",
    provider: str = "openai"
) -> List[Dict[str, Any]]:
    """
    DEPRECATED: Use create_chapters() instead.
    
    Kept for backward compatibility.
    """
    if generate_titles:
        return create_chapters(
            transcript, 
            strategy="time-based",
            model=model,
            provider=provider,
            minutes_per_chapter=minutes_per_chapter
        )
    else:
        # No titles - just time-based
        return _create_time_based_chapters_no_titles(transcript, minutes_per_chapter)


def _create_time_based_chapters(
    transcript: dict,
    minutes_per_chapter: int,
    model: str,
    provider: str
) -> List[Dict[str, Any]]:
    """Create chapters at fixed time intervals with generated titles."""
    segments = transcript.get('segments', [])
    if not segments:
        return []
    
    chapters = []
    chapter_duration = minutes_per_chapter * 60
    
    last_segment = segments[-1]
    total_duration = last_segment.get('end', last_segment.get('start', 0))
    
    current_time = 0
    chapter_num = 1
    
    while current_time < total_duration:
        end_time = min(current_time + chapter_duration, total_duration)
        chapters.append({
            'title': f'Section {chapter_num}',
            'start_time': current_time,
            'end_time': end_time,
        })
        current_time = end_time
        chapter_num += 1
    
    logger.info(f"Created {len(chapters)} time-based chapters ({minutes_per_chapter} min each)")
    
    # Generate titles
    chapters = _generate_chapter_titles(chapters, transcript, model, provider)
    return chapters


def _create_time_based_chapters_no_titles(
    transcript: dict,
    minutes_per_chapter: int
) -> List[Dict[str, Any]]:
    """Create chapters at fixed time intervals without title generation."""
    segments = transcript.get('segments', [])
    if not segments:
        return []
    
    chapters = []
    chapter_duration = minutes_per_chapter * 60
    
    last_segment = segments[-1]
    total_duration = last_segment.get('end', last_segment.get('start', 0))
    
    current_time = 0
    chapter_num = 1
    
    while current_time < total_duration:
        end_time = min(current_time + chapter_duration, total_duration)
        chapters.append({
            'title': f'Section {chapter_num}',
            'start_time': current_time,
            'end_time': end_time,
        })
        current_time = end_time
        chapter_num += 1
    
    return chapters


def _create_semantic_chapters(
    transcript: dict,
    model: str,
    provider: str,
    min_minutes: int,
    max_minutes: int
) -> List[Dict[str, Any]]:
    """Create chapters based on semantic topic boundaries."""
    from src.processing.content.generation import format_transcript_for_llm
    
    formatted_transcript = format_transcript_for_llm(transcript)
    
    # Build prompt
    prompt = f"""You are analyzing a video transcript to identify natural topic boundaries and create meaningful chapters.

TRANSCRIPT (with timestamps):
{formatted_transcript}

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
    
    # Log prompt stats
    log_prompt_stats(prompt, "semantic chapter detection")
    
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
        import json
        import re
        
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            chapters = json.loads(json_match.group())
            
            # Validate
            for chapter in chapters:
                if not all(k in chapter for k in ['title', 'start_time', 'end_time']):
                    raise ValueError("Invalid chapter structure")
            
            logger.info(f"Detected {len(chapters)} semantic chapters")
            for i, ch in enumerate(chapters, 1):
                logger.info(f"   {i}. {ch['title']} ({ch['start_time']//60:.0f}-{ch['end_time']//60:.0f} min)")
            
            return chapters
        else:
            raise ValueError("Could not parse JSON from response")
    
    except Exception as e:
        logger.error(f"Semantic detection failed: {e}")
        raise


def _generate_chapter_titles(
    chapters: List[Dict[str, Any]],
    transcript: dict,
    model: str,
    provider: str
) -> List[Dict[str, Any]]:
    """Generate meaningful titles for chapters using LLM."""
    from src.processing.content.generation import format_transcript_for_llm
    
    chapter_summaries = []
    for i, chapter in enumerate(chapters, 1):
        chapter_transcript = extract_chapter_transcript(transcript, chapter)
        formatted = format_transcript_for_llm(chapter_transcript)
        preview = formatted[:500] if len(formatted) > 500 else formatted
        chapter_summaries.append(f"Chapter {i} ({chapter['start_time']//60:.0f}-{chapter['end_time']//60:.0f} min):\n{preview}")
    
    prompt = f"""You are analyzing a video transcript that has been divided into {len(chapters)} chapters.
For each chapter, generate a concise, descriptive title (3-7 words) that captures the main topic.

CHAPTER PREVIEWS:
{chr(10).join(chapter_summaries)}

YOUR TASK:
Generate a descriptive title for each chapter. Titles should:
- Be 3-7 words
- Describe the main topic/theme
- Be specific and informative
- Use title case

Return ONLY a JSON array of titles in order:
["Title for Chapter 1", "Title for Chapter 2", ...]

JSON array:
"""
    
    # Log prompt stats
    log_prompt_stats(prompt, "title generation")
    
    try:
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
        
        import json
        import re
        
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            titles = json.loads(json_match.group())
            for i, title in enumerate(titles):
                if i < len(chapters):
                    chapters[i]['title'] = title
                    logger.info(f"   Chapter {i+1}: {title}")
        else:
            logger.warning("Could not parse titles, keeping generic titles")
    
    except Exception as e:
        logger.warning(f"Failed to generate titles: {e}, keeping generic titles")
    
    return chapters


def extract_chapter_transcript(
    transcript: dict,
    chapter: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract transcript segments for a specific chapter.
    
    Args:
        transcript: Full transcript dict
        chapter: Chapter dict with start_time and end_time
        
    Returns:
        Transcript dict with only segments from this chapter
    """
    segments = transcript.get('segments', [])
    start_time = chapter.get('start_time', 0)
    end_time = chapter.get('end_time', float('inf'))
    
    # Filter segments within chapter time range
    chapter_segments = [
        seg for seg in segments
        if start_time <= seg.get('start', 0) < end_time
    ]
    
    return {
        'segments': chapter_segments,
        'source': transcript.get('source', 'youtube'),
    }


def generate_section(
    chapter_title: str,
    chapter_transcript: dict,
    target_words: int = 2000,
    model: str = "gpt-4o",
    provider: str = "openai",
    temperature: float = 0.5,
    previous_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a detailed section for one chapter.
    
    Args:
        chapter_title: Title of this chapter/section
        chapter_transcript: Transcript segments for this chapter
        target_words: Target word count for this section
        model: LLM model to use
        provider: LLM provider
        temperature: LLM temperature
        previous_context: Optional summary of previous chapters for continuity
        
    Returns:
        Dict with section content and metadata
    """
    from src.processing.content.generation import format_transcript_for_llm
    
    logger.info(f"  📝 Generating section: '{chapter_title}'")
    
    # Format transcript for this chapter
    formatted_transcript = format_transcript_for_llm(chapter_transcript)
    
    if not formatted_transcript.strip():
        logger.warning(f"  ⚠️  Empty transcript for chapter: {chapter_title}")
        return {
            'success': False,
            'title': chapter_title,
            'content': '',
        }
    
    logger.info(f"     Transcript: {len(formatted_transcript):,} chars, Target: {target_words} words")
    
    # Build section prompt
    prompt = _build_section_prompt(
        chapter_title=chapter_title,
        transcript_text=formatted_transcript,
        target_words=target_words,
        previous_context=previous_context,
    )
    
    # Log prompt stats
    stats = log_prompt_stats(prompt, f"section '{chapter_title}'")
    
    logger.info(f"     Calling {provider}/{model}...")
    
    # Generate section with retry
    try:
        content = call_llm_with_retry(provider, model, prompt, temperature)
        
        # Validate output
        if not validate_section_content(content):
            logger.warning(f"     ⚠️  Generated content failed validation, but continuing...")
        
        word_count = len(content.split())
        logger.info(f"     ✅ Generated: {len(content):,} chars (~{word_count:,} words)")
        
        return {
            'success': True,
            'title': chapter_title,
            'content': content,
            'length': len(content),
            'word_count': word_count,
        }
        
    except Exception as e:
        logger.error(f"     ❌ Failed to generate section '{chapter_title}': {e}")
        return {
            'success': False,
            'title': chapter_title,
            'error': str(e),
        }


def _build_section_prompt(
    chapter_title: str,
    transcript_text: str,
    target_words: int,
    previous_context: Optional[str] = None,
) -> str:
    """Build prompt for generating a single section with optional context from previous chapters.
    
    Args:
        chapter_title: Title of the current chapter
        transcript_text: Transcript text for this chapter
        target_words: Target word count
        previous_context: Optional summary of previous chapters with key concepts
    """
    
    # Build context section if we have previous chapters
    context_section = ""
    if previous_context:
        context_section = f"""PREVIOUS CHAPTERS CONTEXT:
The booklet has already covered the following topics. Use this context to:
- Reference concepts already defined (don't re-explain them)
- Maintain consistent terminology
- Build upon previous ideas
- Create natural transitions from earlier content

{previous_context}

---

"""
    
    return f"""You are writing a detailed section for an educational booklet.

SECTION TITLE: {chapter_title}

{context_section}TRANSCRIPT FOR THIS SECTION:
{transcript_text}

YOUR TASK:
Write a comprehensive, detailed section about this topic. This is ONE section of a larger booklet.

REQUIREMENTS:

1. LENGTH:
   - Target: {target_words} words ({target_words * 5} characters)
   - Be thorough and detailed - this is educational content
   - Don't summarize - expand and explain

2. CONTENT:
   - Cover ALL points mentioned in the transcript
   - Explain concepts clearly and thoroughly
   - Include specific examples and details mentioned
   - Expand on ideas to make them clearer in written form
   - Use the speaker's insights and explanations

3. CONTINUITY (IMPORTANT):
   - If concepts were introduced in previous chapters, reference them naturally
   - Use the SAME terminology as previous chapters for consistency
   - Don't re-explain concepts already covered - just reference and build upon them
   - Create smooth transitions that acknowledge the booklet's flow
   - If this introduces new concepts, define them clearly for use in later chapters

4. STRUCTURE:
   - Start with a brief introduction to this topic
   - Use subheadings (###) to organize sub-topics
   - Use bullet points for lists of concepts
   - Use numbered lists for sequential steps
   - End each major point before moving to the next

5. WRITING STYLE:
   - Clear, professional, educational
   - Convert spoken language to polished prose
   - Remove filler words but keep all substance
   - Make complex ideas accessible
   - Maintain engaging tone

6. FORMATTING:
   - Use markdown: ### for subheadings, **bold**, *italic*
   - Create visual hierarchy
   - Use lists effectively
   - Add emphasis to key terms

IMPORTANT: 
- This section should be DETAILED and COMPREHENSIVE
- Aim for {target_words} words - don't be brief
- Cover the topic thoroughly as if teaching it
- Maintain consistency with previous chapters

OUTPUT FORMAT:
Return ONLY the section content in markdown. Start with the section heading (##).

Begin the section now:
"""


def extract_chapter_summary(
    chapter_title: str,
    chapter_content: str,
    model: str = "gpt-4o-mini",
    provider: str = "openai"
) -> str:
    """
    Extract a concise summary with key concepts from a generated chapter.
    
    This summary will be used as context for subsequent chapters to maintain
    concept continuity and consistent terminology.
    
    Args:
        chapter_title: Title of the chapter
        chapter_content: Full generated content for the chapter
        model: LLM model to use (use cheaper model for summaries)
        provider: LLM provider
        
    Returns:
        Concise summary with key concepts and terminology
    """
    logger.info(f"     Extracting key concepts from '{chapter_title}'...")
    
    # Truncate content if too long (keep first 3000 chars for summary)
    content_preview = chapter_content[:3000] if len(chapter_content) > 3000 else chapter_content
    
    prompt = f"""You are analyzing a chapter from an educational booklet to extract key information for context.

CHAPTER TITLE: {chapter_title}

CHAPTER CONTENT:
{content_preview}

YOUR TASK:
Create a concise summary (150-250 words) that captures:
1. Main topic/theme of this chapter
2. Key concepts introduced with their definitions
3. Important terminology used (with brief explanations)
4. Core ideas or frameworks discussed
5. Any specific examples or case studies mentioned

FORMAT:
Write in a structured format that's easy to reference:
- Start with: "Chapter: [title]"
- Use bullet points for key concepts
- Bold important terms
- Keep it factual and precise

This summary will help maintain consistency in later chapters.

Summary:
"""
    
    try:
        if provider == "openai":
            from src.processing.content.generation import _call_openai
            summary = _call_openai(prompt, model, temperature=0.3)
        elif provider == "anthropic":
            from src.processing.content.generation import _call_anthropic
            summary = _call_anthropic(prompt, model, temperature=0.3)
        elif provider == "openrouter":
            from src.processing.content.generation import _call_openrouter
            summary = _call_openrouter(prompt, model, temperature=0.3)
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        logger.info(f"     ✅ Extracted summary ({len(summary)} chars)")
        return summary.strip()
        
    except Exception as e:
        logger.warning(f"     ⚠️  Failed to extract summary: {e}")
        # Fallback: create basic summary from title
        return f"Chapter: {chapter_title}\n- Covers topics related to {chapter_title.lower()}"


def combine_sections(
    sections: List[Dict[str, Any]],
    video_title: str,
    video_url: Optional[str] = None,
) -> str:
    """
    Combine individual sections into a complete booklet.
    
    Args:
        sections: List of section dicts with 'title' and 'content'
        video_title: Title of the video
        video_url: Optional URL to include
        
    Returns:
        Complete booklet markdown
    """
    parts = []
    
    # Title
    parts.append(f"# {video_title}\n")
    
    # Metadata
    if video_url:
        parts.append(f"**Source:** {video_url}\n")
    parts.append("")
    
    # Introduction
    parts.append("## Introduction\n")
    parts.append(
        "This booklet is a comprehensive guide based on the video transcript. "
        "Each section covers a major topic discussed in the video, with detailed "
        "explanations and insights.\n"
    )
    
    # Table of contents
    parts.append("## Table of Contents\n")
    for i, section in enumerate(sections, 1):
        if section.get('success') and section.get('content'):
            parts.append(f"{i}. {section['title']}")
    parts.append("")
    
    parts.append("---\n")
    
    # Sections
    for section in sections:
        if section.get('success') and section.get('content'):
            parts.append(section['content'])
            parts.append("")  # Spacing between sections
    
    # Conclusion
    parts.append("## Conclusion\n")
    parts.append(
        "This booklet has covered the key topics and insights from the video. "
        "Each section provides detailed information to help you understand and "
        "apply the concepts discussed.\n"
    )
    
    return "\n".join(parts)


def _generate_sections_sequential(
    chapters: List[Dict[str, Any]],
    transcript: dict,
    words_per_section: int,
    model: str,
    provider: str,
    temperature: float
) -> List[Dict[str, Any]]:
    """Generate sections sequentially (one at a time) with context from previous chapters."""
    sections = []
    context_summaries = []  # Accumulate summaries of previous chapters
    
    for i, chapter in enumerate(chapters, 1):
        logger.info(f"[{i}/{len(chapters)}] Processing: {chapter.get('title', 'Untitled')}")
        
        # Build context from previous chapters
        previous_context = None
        if context_summaries:
            previous_context = "\n\n".join(context_summaries)
            logger.info(f"     Using context from {len(context_summaries)} previous chapter(s)")
        
        chapter_transcript = extract_chapter_transcript(transcript, chapter)
        section = generate_section(
            chapter_title=chapter.get('title', f'Section {i}'),
            chapter_transcript=chapter_transcript,
            target_words=words_per_section,
            model=model,
            provider=provider,
            temperature=temperature,
            previous_context=previous_context,
        )
        sections.append(section)
        
        # Extract summary for context if generation succeeded
        if section.get('success') and section.get('content'):
            summary = extract_chapter_summary(
                chapter_title=section['title'],
                chapter_content=section['content'],
                model="gpt-4o-mini",  # Use cheaper model for summaries
                provider=provider
            )
            context_summaries.append(summary)
        
        logger.info("")
    
    return sections


def _generate_sections_parallel(
    chapters: List[Dict[str, Any]],
    transcript: dict,
    words_per_section: int,
    model: str,
    provider: str,
    temperature: float,
    max_workers: int
) -> List[Dict[str, Any]]:
    """Generate sections in parallel (much faster but no context between chapters).
    
    WARNING: Parallel mode does not maintain context between chapters.
    This can lead to:
    - Inconsistent terminology
    - Repeated explanations of concepts
    - Poor narrative flow
    
    Use sequential mode (parallel=False) for better coherence.
    """
    logger.info(f"⚡ Using parallel processing with {max_workers} workers")
    logger.warning("⚠️  Parallel mode: chapters generated independently (no context sharing)")
    
    def generate_one_section(chapter_data):
        i, chapter = chapter_data
        logger.info(f"[{i}/{len(chapters)}] Starting: {chapter.get('title', 'Untitled')}")
        
        chapter_transcript = extract_chapter_transcript(transcript, chapter)
        section = generate_section(
            chapter_title=chapter.get('title', f'Section {i}'),
            chapter_transcript=chapter_transcript,
            target_words=words_per_section,
            model=model,
            provider=provider,
            temperature=temperature,
        )
        logger.info(f"[{i}/{len(chapters)}] Completed: {chapter.get('title', 'Untitled')}\n")
        return (i, section)
    
    # Create tasks with indices
    tasks = [(i, ch) for i, ch in enumerate(chapters, 1)]
    
    # Execute in parallel
    sections_dict = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(generate_one_section, task): task for task in tasks}
        
        for future in as_completed(futures):
            try:
                i, section = future.result()
                sections_dict[i] = section
            except Exception as e:
                task = futures[future]
                logger.error(f"Section {task[0]} failed: {e}")
                sections_dict[task[0]] = {
                    'success': False,
                    'title': task[1].get('title', f'Section {task[0]}'),
                    'error': str(e)
                }
    
    # Return sections in order
    return [sections_dict[i] for i in sorted(sections_dict.keys())]


def generate_booklet_by_chapters(
    transcript: dict,
    video_title: str,
    video_url: Optional[str] = None,
    chapters: Optional[List[Dict[str, Any]]] = None,
    model: str = "gpt-4o",
    provider: str = "openai",
    temperature: float = 0.5,
    words_per_section: int = 2000,
    auto_chapter_minutes: int = 5,
    parallel: bool = True,
    max_workers: int = 5,
) -> Dict[str, Any]:
    """
    Generate a comprehensive booklet by processing each chapter independently.
    
    This is the recommended approach for generating detailed content from long videos.
    
    Args:
        transcript: Full transcript dict
        video_title: Title of the video
        video_url: Optional video URL
        chapters: Optional list of chapters (if None, auto-creates them)
        model: LLM model to use
        provider: LLM provider
        temperature: LLM temperature
        words_per_section: Target words per section
        auto_chapter_minutes: Minutes per auto-created chapter
        parallel: If True, generate sections in parallel (faster but no context)
                  If False, generate sequentially with context from previous chapters (recommended)
        max_workers: Maximum parallel workers (default: 5)
        
    Returns:
        Dict with success, booklet content, and metadata
    """
    logger.info("=" * 80)
    logger.info("🚀 Starting chapter-based booklet generation")
    logger.info("=" * 80)
    
    # Get or create chapters
    if not chapters:
        logger.info("📋 No chapters provided, auto-creating from transcript...")
        chapters = auto_create_chapters(transcript, auto_chapter_minutes)
        logger.info(f"   Created {len(chapters)} chapters ({auto_chapter_minutes} min each)")
    else:
        logger.info(f"📋 Using {len(chapters)} chapters from video metadata")
    
    if not chapters:
        return {
            'success': False,
            'error': 'No chapters available and could not auto-create them',
        }
    
    logger.info(f"\n🔄 Generating {len(chapters)} sections (target: {words_per_section} words each)...")
    logger.info(f"   Model: {provider}/{model}")
    logger.info(f"   Mode: {'Parallel' if parallel else 'Sequential'}")
    if parallel:
        logger.info(f"   Workers: {max_workers}")
    logger.info(f"   This will take several minutes...\n")
    
    # Generate sections (parallel or sequential)
    if parallel and len(chapters) > 1:
        sections = _generate_sections_parallel(
            chapters, transcript, words_per_section, model, provider, temperature, max_workers
        )
    else:
        sections = _generate_sections_sequential(
            chapters, transcript, words_per_section, model, provider, temperature
        )
    
    # Check if any sections succeeded
    successful_sections = [s for s in sections if s.get('success')]
    if not successful_sections:
        logger.error("❌ Failed to generate any sections")
        return {
            'success': False,
            'error': 'Failed to generate any sections',
        }
    
    logger.info("=" * 80)
    logger.info("📚 Combining sections into final booklet...")
    
    # Combine sections into booklet
    booklet = combine_sections(sections, video_title, video_url)
    
    total_words = len(booklet.split())
    logger.info(f"✅ Booklet complete!")
    logger.info(f"   Sections: {len(successful_sections)}/{len(sections)} successful")
    logger.info(f"   Length: {len(booklet):,} chars (~{total_words:,} words)")
    logger.info("=" * 80)
    
    return {
        'success': True,
        'content': booklet,
        'model': f"{provider}/{model}",
        'num_sections': len(successful_sections),
        'total_sections': len(sections),
        'length': len(booklet),
    }
