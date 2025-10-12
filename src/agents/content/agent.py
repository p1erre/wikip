"""
Content Generation Agent

Simple agent that generates high-quality content from video metadata and transcripts.
Uses a single prompt to generate structured content organized by YouTube chapters.
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.agents.content.tools import get_content_tools

logger = logging.getLogger(__name__)


CONTENT_AGENT_SYSTEM_PROMPT = """You are an expert content writer specializing in creating high-quality posts and booklets from video content.

Your capabilities:
1. Analyze video metadata and transcripts
2. Extract and organize content by chapters
3. Generate well-structured, engaging content
4. Maintain the key insights and information from the original video

Your workflow:
1. Use the prepare_content_data tool to organize the video data by chapters
2. Analyze the structured data to understand the video's flow and key points
3. Generate content that:
   - Has a clear introduction
   - Follows the chapter structure from the video
   - Summarizes key points in each section
   - Includes relevant quotes or insights
   - Has a conclusion that ties everything together
   - Is well-formatted with headers and sections

Writing guidelines:
- Be clear and concise
- Maintain the original message and insights
- Use proper markdown formatting
- Include chapter titles as section headers
- Make the content engaging and readable
- Preserve important details and examples from the transcript

Remember: Your goal is to transform video content into a readable, well-structured document that captures the essence of the video.
"""


def create_content_agent(
    model: str = "gpt-4-turbo-preview",
    temperature: float = 0.7,
) -> Any:
    """
    Create a content generation agent using LangGraph's ReAct pattern.
    
    This agent can take video metadata and transcripts and generate
    structured content organized by chapters.
    
    Args:
        model: OpenAI model to use (default: gpt-4-turbo-preview)
        temperature: LLM temperature (0.7 for creative writing)
        
    Returns:
        Compiled LangGraph agent ready to use
        
    Example:
        >>> agent = create_content_agent()
        >>> result = agent.invoke({
        ...     "messages": [HumanMessage(content="Generate a booklet...")]
        ... })
    """
    logger.info(f"Creating content agent with model: {model}")
    
    # Initialize the LLM with higher temperature for creative writing
    llm = ChatOpenAI(model=model, temperature=temperature)
    
    # Get content generation tools
    tools = get_content_tools()
    
    # Create the ReAct agent
    agent = create_react_agent(
        llm,
        tools,
        prompt=CONTENT_AGENT_SYSTEM_PROMPT
    )
    
    logger.info("Content agent created successfully")
    return agent


def generate_content_from_chapters(
    chapter_markdown: str,
    video_title: str,
    content_type: str = "booklet",
    model: str = "gpt-4-turbo-preview"
) -> dict[str, Any]:
    """
    Generate content from chapter-organized markdown.
    
    Takes a markdown document organized by chapters (from create_chapter_markdown)
    and transforms it into different content types using a single LLM call.
    
    Args:
        chapter_markdown: Markdown document with chapters and full transcript
        video_title: Title of the video
        content_type: Type of content to generate:
            - 'booklet': Comprehensive guide/booklet
            - 'blog': Blog post
            - 'linkedin': LinkedIn post
            - 'twitter': Twitter thread
            - 'summary': Short summary
        model: OpenAI model to use
        
    Returns:
        Dictionary with generated content
        
    Example:
        >>> from src.agents.content import create_chapter_markdown
        >>> markdown_result = create_chapter_markdown.func(video_id, metadata, transcript)
        >>> content = generate_content_from_chapters(
        ...     markdown_result['markdown'],
        ...     metadata['title'],
        ...     content_type='booklet'
        ... )
    """
    logger.info(f"Generating {content_type} from chapter markdown")
    
    # Content type specific prompts
    prompts = {
        'booklet': """Create a comprehensive booklet that:
- Has an engaging introduction
- Organizes content by the video's chapters
- Summarizes key insights and important points from each section
- Includes relevant quotes and examples
- Has a meaningful conclusion
- Uses proper markdown formatting (# headers, ** bold, etc.)
- Is informative and well-structured""",
        
        'blog': """Create an engaging blog post that:
- Has a catchy introduction that hooks the reader
- Flows naturally through the main topics (use chapters as guide)
- Highlights the most interesting insights and takeaways
- Uses conversational tone
- Includes subheadings for readability
- Ends with a strong conclusion or call-to-action
- Length: 800-1200 words""",
        
        'linkedin': """Create a LinkedIn post that:
- Starts with a hook that grabs attention
- Summarizes the key insights in 3-5 main points
- Uses short paragraphs for readability
- Includes relevant emojis sparingly
- Ends with a question or call-to-action to drive engagement
- Length: 150-300 words
- Professional but conversational tone""",
        
        'twitter': """Create a Twitter thread that:
- Tweet 1: Hook that makes people want to read more
- Tweets 2-8: One key insight per tweet, each standalone but connected
- Final tweet: Summary and call-to-action
- Each tweet under 280 characters
- Use thread numbering (1/9, 2/9, etc.)
- Conversational and engaging tone
- Use line breaks for readability""",
        
        'summary': """Create a concise summary that:
- Captures the main topic and purpose
- Lists 3-5 key takeaways
- Mentions the most important insights
- Length: 200-400 words
- Clear and direct writing"""
    }
    
    content_prompt = prompts.get(content_type, prompts['booklet'])
    
    # Create the prompt
    prompt = f"""You are an expert content writer. Transform the following video transcript (organized by chapters) into a high-quality {content_type}.

**Video Title:** {video_title}

**Your Task:**
{content_prompt}

**Source Material (Chapter-Organized Transcript):**
{chapter_markdown}

**Important:**
- Extract the most valuable insights and information
- Maintain accuracy to the source material
- Make it engaging and well-structured
- Use the chapter structure to guide your organization

Generate the {content_type} now:"""
    
    # Direct LLM call
    llm = ChatOpenAI(model=model, temperature=0.7)
    
    messages = [
        SystemMessage(content=f"You are an expert content writer who creates engaging {content_type}s from video transcripts."),
        HumanMessage(content=prompt)
    ]
    
    logger.info(f"Making LLM call to generate {content_type}...")
    response = llm.invoke(messages)
    generated_content = response.content
    
    logger.info(f"{content_type.capitalize()} generation complete")
    
    return {
        "success": True,
        "video_title": video_title,
        "content_type": content_type,
        "content": generated_content,
    }


def generate_content(
    video_id: str,
    metadata: dict,
    transcript: dict,
    content_type: str = "booklet",
    model: str = "gpt-4-turbo-preview"
) -> dict[str, Any]:
    """
    Generate high-quality content from video metadata and transcript.
    
    Simple single-call approach - no agents, no tools, just direct LLM call.
    
    Args:
        video_id: YouTube video ID
        metadata: Video metadata dictionary
        transcript: Transcript dictionary with segments
        content_type: Type of content to generate ('post', 'booklet', 'article')
        model: OpenAI model to use
        
    Returns:
        Dictionary with generated content and metadata
        
    Example:
        >>> from src.agents.video import analyze_video
        >>> result = analyze_video("https://youtube.com/watch?v=abc123")
        >>> content = generate_content(
        ...     result['video_id'],
        ...     result['metadata'],
        ...     result['transcript']
        ... )
        >>> print(content['content'])
    """
    logger.info(f"Starting content generation for video: {video_id}")
    
    # Prepare the data (organize by chapters)
    from src.agents.content.tools import prepare_content_data
    organized_data = prepare_content_data.func(video_id, metadata, transcript)
    
    if not organized_data.get('success'):
        return {
            "success": False,
            "error": "Failed to prepare content data"
        }
    
    # Build chapter summaries for the prompt
    chapters_text = ""
    for chapter in organized_data['chapters']:
        chapters_text += f"\n## {chapter['title']} ({chapter['start_time']}s - {chapter['end_time']}s)\n"
        chapters_text += f"{chapter['transcript'][:500]}...\n"  # First 500 chars of each chapter
    
    # Create a focused prompt for single LLM call
    prompt = f"""You are an expert content writer. Generate a well-structured {content_type} from this YouTube video.

**Video Information:**
- Title: {organized_data['video_title']}
- Channel: {organized_data['channel']}
- Duration: {organized_data['duration']} seconds
- Chapters: {organized_data['num_chapters']}

**Content Structure:**
{chapters_text}

**Your Task:**
Create a {content_type} that:
1. Starts with an engaging introduction about the video topic
2. Organizes content by the video's chapter structure
3. Summarizes key insights and important points from each section
4. Uses proper markdown formatting (# headers, ** bold, etc.)
5. Includes relevant quotes or examples from the transcript
6. Ends with a meaningful conclusion

**Output Format:**
- Use markdown formatting
- Start with a title (# Title)
- Use ## for chapter/section headers
- Make it informative and well-organized
- Keep the original message and insights from the video

Generate the {content_type} now:"""
    
    # Direct LLM call - no agent, no tools
    llm = ChatOpenAI(model=model, temperature=0.7)
    
    messages = [
        SystemMessage(content="You are an expert content writer who creates engaging, well-structured content from video transcripts."),
        HumanMessage(content=prompt)
    ]
    
    logger.info("Making single LLM call to generate content...")
    response = llm.invoke(messages)
    generated_content = response.content
    
    logger.info("Content generation complete")
    
    return {
        "success": True,
        "video_id": video_id,
        "video_title": metadata.get('title'),
        "content_type": content_type,
        "content": generated_content,
        "chapters_used": organized_data['num_chapters'],
    }


# Example usage
if __name__ == "__main__":
    """
    Example of how to use the content generation agent.
    
    Run this file directly to see the agent in action:
    $ python -m src.agents.content.agent
    """
    import os
    from dotenv import load_dotenv
    from src.agents.video import analyze_video
    
    # Load environment variables
    load_dotenv()
    
    # Check if API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set in environment")
        print("Please create a .env file with your API key")
        exit(1)
    
    # Example: Analyze a video first
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    print(f"\n{'='*60}")
    print("CONTENT GENERATION AGENT EXAMPLE")
    print(f"{'='*60}\n")
    print(f"Step 1: Analyzing video: {test_url}\n")
    
    # First, analyze the video to get metadata and transcript
    video_result = analyze_video(test_url)
    
    if not video_result['video_id']:
        print("Failed to analyze video")
        exit(1)
    
    print(f"Video analyzed: {video_result['metadata'].get('title')}\n")
    print(f"Step 2: Generating content...\n")
    
    # Generate content from the video
    content_result = generate_content(
        video_id=video_result['video_id'],
        metadata=video_result['metadata'],
        transcript=video_result['transcript'],
        content_type="booklet"
    )
    
    # Print results
    print(f"\n{'='*60}")
    print("GENERATED CONTENT")
    print(f"{'='*60}\n")
    print(content_result['content'])
    print(f"\n{'='*60}\n")
