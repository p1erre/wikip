"""
Show the output structure of analyze_slides_with_vision
"""
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.slides import extract_slides_robust, analyze_slides_with_vision

def main():
    print("\n" + "="*80)
    print("📊 ANALYZE_SLIDES_WITH_VISION OUTPUT STRUCTURE")
    print("="*80)
    
    # Use existing slides from test
    video_path = ".test_videos/r1qZpYAmqmg_12min.mp4"
    
    print(f"\n📹 Video: {video_path}")
    print("🔍 Analyzing first 2 slides only (to save cost)...\n")
    
    # Extract slides
    slides_result = extract_slides_robust.func(
        video_path=video_path,
        output_dir="./demo_vision_output/slides",
        fps_sample=2.0,
        build_policy="build_collapse",
        save_keyframes=True,
    )
    
    # Limit to first 2 slides for demo
    slides_result['slides'] = slides_result['slides'][:2]
    
    print(f"✅ Extracted {len(slides_result['slides'])} slides")
    print("\n🤖 Analyzing with vision LLM via OpenRouter...")
    
    # Analyze with vision
    enriched = analyze_slides_with_vision(
        slides_result=slides_result,
        provider='openrouter',
        model='openai/gpt-4o',
        output_path="./demo_vision_output/enriched_slides.json"
    )
    
    print("\n" + "="*80)
    print("📦 RETURN VALUE (enriched)")
    print("="*80)
    print(f"\nType: {type(enriched)}")
    print(f"Length: {len(enriched)} slides")
    print("\nThis is a LIST of enriched slide dictionaries\n")
    
    print("="*80)
    print("📋 FIRST SLIDE (enriched[0])")
    print("="*80)
    print("\nFull structure of first slide:")
    print(json.dumps(enriched[0], indent=2, default=str))
    
    print("\n" + "="*80)
    print("🎯 KEY FIELDS EXPLANATION")
    print("="*80)
    print("""
enriched = [  # List of enriched slide objects
    {
        # Original slide fields from extract_slides_robust:
        'slide_number': 1,
        'cluster_id': 0,
        'image_path': 'path/to/slide_001.jpg',
        'timestamp': 0.0,
        'duration': 61.44,
        'num_occurrences': 1,
        'occurrences': [...],
        'num_builds': 0,
        'builds': [],
        
        # NEW fields added by analyze_slides_with_vision:
        'start_time': 0.0,              # Start time (same as timestamp)
        'end_time': 61.44,              # End time (timestamp + duration)
        'transcript': "Speaker text...", # What speaker said during slide
        'vision_analysis': {            # AI-extracted slide content
            'title': 'Slide Title',
            'text_content': [           # All visible text
                'Bullet point 1',
                'Bullet point 2',
                ...
            ],
            'visual_elements': {        # Visual components
                'diagrams': ['description of diagram'],
                'charts': ['description of chart'],
                'code_snippets': ['code block'],
                'images': ['description of image'],
                'icons': ['icon description']
            },
            'key_concepts': [           # Main concepts
                'concept 1',
                'concept 2'
            ],
            'technical_details': 'formulas, equations, specs',
            'layout': 'description of slide layout',
            'speaker_alignment': 'how visuals relate to speech'
        }
    },
    # ... more enriched slides
]
""")
    
    print("="*80)
    print("📊 COMPARISON TABLE")
    print("="*80)
    print(f"\n{'Slide':<8} {'Time Range':<20} {'Title':<40} {'Concepts'}")
    print("-" * 100)
    
    for slide in enriched:
        time_range = f"{slide['start_time']:.1f}s - {slide['end_time']:.1f}s"
        title = slide['vision_analysis'].get('title', 'N/A')[:38]
        concepts = ', '.join(slide['vision_analysis'].get('key_concepts', [])[:3])[:30]
        
        print(f"{slide['slide_number']:<8} {time_range:<20} {title:<40} {concepts}")
    
    print("\n" + "="*80)
    print("💡 USAGE EXAMPLES")
    print("="*80)
    print("""
# Access slide data:
for slide in enriched:
    print(f"Slide {slide['slide_number']}")
    print(f"  Time: {slide['start_time']:.1f}s - {slide['end_time']:.1f}s")
    print(f"  Title: {slide['vision_analysis']['title']}")
    print(f"  Concepts: {slide['vision_analysis']['key_concepts']}")
    print(f"  Speaker: {slide['transcript']}")

# Get all titles:
titles = [s['vision_analysis']['title'] for s in enriched]

# Get all concepts:
all_concepts = []
for slide in enriched:
    all_concepts.extend(slide['vision_analysis']['key_concepts'])

# Find slides with code:
code_slides = [
    s for s in enriched 
    if s['vision_analysis']['visual_elements'].get('code_snippets')
]

# Generate content from slide:
def generate_section(slide):
    title = slide['vision_analysis']['title']
    content = slide['vision_analysis']['text_content']
    speaker = slide['transcript']
    
    return f"## {title}\\n\\n{speaker}\\n\\n" + "\\n".join(content)
""")
    
    print("="*80)
    print("✅ COMPLETE!")
    print("="*80)
    print(f"\nEnriched data saved to: ./demo_vision_output/enriched_slides.json")
    print(f"You can load it with: json.load(open('enriched_slides.json'))")
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
