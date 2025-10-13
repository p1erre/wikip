"""
Vision-based slide analysis using Gemini or GPT-4V
"""
import os
import json
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()


class SlideVisionAnalyzer:
    """Analyze slides using vision LLMs (Gemini or GPT-4V)"""
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize the vision analyzer
        
        Args:
            provider: 'google', 'openai', or 'openrouter' (default from env VISION_MODEL_PROVIDER)
            model: Model name (default from env VISION_MODEL)
        """
        self.provider = provider or os.getenv('VISION_MODEL_PROVIDER', 'openrouter')
        self.model = model or os.getenv('VISION_MODEL', 'google/gemini-flash-1.5')
        
        if self.provider == 'google':
            import google.generativeai as genai
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not found in environment")
            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(self.model)
        elif self.provider == 'openai':
            from openai import OpenAI
            self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        elif self.provider == 'openrouter':
            from openai import OpenAI
            api_key = os.getenv('OPENROUTER_API_KEY') or os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY or GOOGLE_API_KEY not found in environment")
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def _build_analysis_prompt(self, transcript: Optional[str], timestamp_info: Optional[Dict[str, float]]) -> str:
        """Build the analysis prompt focusing on value-added content"""
        prompt_parts = []
        
        if timestamp_info:
            prompt_parts.append(
                f"This slide appears at {timestamp_info['start']:.1f}s - {timestamp_info['end']:.1f}s "
                f"(duration: {timestamp_info['end'] - timestamp_info['start']:.1f}s)"
            )
        
        if transcript:
            prompt_parts.append(f"\nSpeaker transcript during this slide:\n{transcript}\n")
        
        prompt_parts.append("""
Your goal is to extract information that ADDS VALUE for creating educational content.
Focus ONLY on elements that are hard to get from the transcript alone.

Return as JSON:
{
  "slide_type": "title|content|diagram|code|data|transition",
  "main_topic": "what this slide is teaching (1 sentence)",
  
  "code_snippets": [
    {
      "language": "python|javascript|etc",
      "code": "actual code text",
      "explanation": "what this code demonstrates"
    }
  ],
  
  "diagrams_and_charts": [
    {
      "type": "flowchart|architecture|graph|chart|etc",
      "description": "detailed description of what it shows",
      "key_elements": ["element 1", "element 2"],
      "teaching_point": "what concept this visual explains"
    }
  ],
  
  "formulas_and_equations": [
    {
      "formula": "LaTeX or text representation",
      "variables": {"x": "description", "y": "description"},
      "explanation": "what this formula represents"
    }
  ],
  
  "data_and_numbers": [
    {
      "metric": "what is being measured",
      "value": "the number/data",
      "context": "why this matters"
    }
  ],
  
  "key_visual_concepts": [
    "Only include visual concepts that are NOT in the transcript",
    "e.g., 'Diagram shows 3-layer architecture', 'Chart indicates 40% improvement'"
  ],
  
  "actionable_content": {
    "has_code": true/false,
    "has_diagram": true/false,
    "has_formula": true/false,
    "has_data": true/false,
    "needs_visual_description": true/false
  }
}

IMPORTANT:
- Skip simple text bullets (they're redundant with transcript)
- Focus on CODE, DIAGRAMS, FORMULAS, DATA that need to be captured
- Only describe visuals if they teach something the transcript doesn't
- Be concise - this is for content generation, not slide reproduction
- If slide is just text/title, set all arrays to [] and needs_visual_description to false""")
        
        return "\n".join(prompt_parts)
    
    def analyze_slide(
        self,
        image_path: str,
        transcript: Optional[str] = None,
        timestamp_info: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a single slide image
        
        Args:
            image_path: Path to slide image
            transcript: Optional transcript text during this slide
            timestamp_info: Optional dict with 'start' and 'end' times
            
        Returns:
            Dict with extracted information
        """
        if self.provider == 'google':
            return self._analyze_with_gemini(image_path, transcript, timestamp_info)
        elif self.provider in ['openai', 'openrouter']:
            return self._analyze_with_openai(image_path, transcript, timestamp_info)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def _analyze_with_gemini(
        self,
        image_path: str,
        transcript: Optional[str] = None,
        timestamp_info: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Analyze slide using Gemini"""
        # Load image
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Build prompt
        prompt = self._build_analysis_prompt(transcript, timestamp_info)
        
        # Call Gemini
        response = self.client.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": image_data}
        ])
        
        # Parse JSON response
        try:
            result = json.loads(response.text)
        except json.JSONDecodeError:
            # If not valid JSON, return raw text
            result = {"raw_analysis": response.text}
        
        return result
    
    def _analyze_with_openai(
        self,
        image_path: str,
        transcript: Optional[str] = None,
        timestamp_info: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Analyze slide using GPT-4V"""
        # Load and encode image
        with open(image_path, 'rb') as f:
            image_b64 = base64.b64encode(f.read()).decode()
        
        # Build prompt
        prompt = self._build_analysis_prompt(transcript, timestamp_info)
        
        # Call OpenAI
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        }
                    }
                ]
            }],
            max_tokens=1500,
            response_format={"type": "json_object"}
        )
        
        # Parse JSON response
        result = json.loads(response.choices[0].message.content)
        return result
    
    def analyze_slides_batch(
        self,
        slides: List[Dict[str, Any]],
        transcript_segments: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple slides
        
        Args:
            slides: List of slide dicts with 'image_path', 'timestamp', 'duration'
            transcript_segments: Optional list of transcript segments with 'start', 'end', 'text'
            
        Returns:
            List of enriched slide dicts with vision analysis
        """
        enriched_slides = []
        
        for slide in slides:
            # Get timestamp info
            start_time = slide['timestamp']
            end_time = start_time + slide['duration']
            timestamp_info = {'start': start_time, 'end': end_time}
            
            # Get corresponding transcript
            transcript = None
            if transcript_segments:
                transcript = self._get_transcript_for_timerange(
                    transcript_segments, start_time, end_time
                )
            
            # Analyze slide
            analysis = self.analyze_slide(
                slide['image_path'],
                transcript=transcript,
                timestamp_info=timestamp_info
            )
            
            # Enrich slide data
            enriched_slide = {
                **slide,
                'start_time': start_time,
                'end_time': end_time,
                'transcript': transcript,
                'vision_analysis': analysis
            }
            enriched_slides.append(enriched_slide)
            
            print(f"✓ Analyzed slide {slide['slide_number']}/{len(slides)}")
        
        return enriched_slides
    
    def _get_transcript_for_timerange(
        self,
        segments: List[Dict[str, Any]],
        start: float,
        end: float
    ) -> str:
        """Extract transcript text for a time range"""
        text_parts = []
        
        for seg in segments:
            seg_start = seg.get('start', 0)
            seg_end = seg.get('end', seg_start)
            
            # Check if segment overlaps with time range
            if seg_start < end and seg_end > start:
                text_parts.append(seg.get('text', ''))
        
        return ' '.join(text_parts).strip()


def analyze_slides_with_vision(
    slides_result: Dict[str, Any],
    transcript: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    output_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to analyze slides with vision LLM
    
    Args:
        slides_result: Result from extract_slides_robust()
        transcript: Optional transcript dict with 'segments'
        provider: 'google' or 'openai' (default from env)
        model: Model name (default from env)
        output_path: Optional path to save enriched slides JSON
        
    Returns:
        List of enriched slides with vision analysis
    """
    analyzer = SlideVisionAnalyzer(provider=provider, model=model)
    
    # Get transcript segments if provided
    transcript_segments = None
    if transcript:
        transcript_segments = transcript.get('segments', [])
    
    # Analyze all slides
    enriched_slides = analyzer.analyze_slides_batch(
        slides_result['slides'],
        transcript_segments=transcript_segments
    )
    
    # Save if output path provided
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump({
                'video_path': slides_result.get('video_path'),
                'num_slides': len(enriched_slides),
                'provider': analyzer.provider,
                'model': analyzer.model,
                'slides': enriched_slides
            }, f, indent=2)
        
        print(f"\n💾 Saved enriched slides to: {output_file}")
    
    return enriched_slides
