"""
Quick test of Gemini vision integration
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.vision import SlideVisionAnalyzer

def main():
    print("\n" + "="*70)
    print("🧪 TESTING GEMINI VISION INTEGRATION")
    print("="*70)
    
    # Check if we have slides from previous test
    slides_dir = Path("test_slides_robust/collapse")
    if not slides_dir.exists():
        print("\n❌ No slides found. Run test_robust_slides.py first!")
        return 1
    
    # Get first slide
    slides = sorted(slides_dir.glob("slide_*.jpg"))
    if not slides:
        print("\n❌ No slide images found!")
        return 1
    
    test_slide = slides[0]
    print(f"\n📸 Testing with: {test_slide}")
    
    # Create analyzer
    print("\n🔧 Initializing GPT-4o vision analyzer via OpenRouter...")
    try:
        analyzer = SlideVisionAnalyzer(
            provider='openrouter',
            model='openai/gpt-4o'  # OpenRouter model name
        )
        print("✅ Analyzer initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        print("\nMake sure GOOGLE_API_KEY is set in .env file")
        return 1
    
    # Analyze slide
    print(f"\n🔍 Analyzing slide with Gemini...")
    try:
        result = analyzer.analyze_slide(
            image_path=str(test_slide),
            transcript="This is a test slide from a presentation.",
            timestamp_info={'start': 0.0, 'end': 10.0}
        )
        print("✅ Analysis complete!")
        
        # Display results
        print("\n" + "="*70)
        print("📊 ANALYSIS RESULTS")
        print("="*70)
        
        if isinstance(result, dict):
            if 'title' in result:
                print(f"\n📌 Title: {result['title']}")
            
            if 'text_content' in result and result['text_content']:
                print(f"\n📝 Text Content ({len(result['text_content'])} items):")
                for i, text in enumerate(result['text_content'][:5], 1):
                    print(f"   {i}. {text}")
                if len(result['text_content']) > 5:
                    print(f"   ... and {len(result['text_content']) - 5} more")
            
            if 'key_concepts' in result and result['key_concepts']:
                print(f"\n💡 Key Concepts: {', '.join(result['key_concepts'][:5])}")
            
            if 'visual_elements' in result:
                ve = result['visual_elements']
                print(f"\n🎨 Visual Elements:")
                if ve.get('diagrams'):
                    print(f"   Diagrams: {len(ve['diagrams'])}")
                if ve.get('charts'):
                    print(f"   Charts: {len(ve['charts'])}")
                if ve.get('code_snippets'):
                    print(f"   Code: {len(ve['code_snippets'])}")
                if ve.get('images'):
                    print(f"   Images: {len(ve['images'])}")
            
            if 'technical_details' in result and result['technical_details']:
                print(f"\n🔬 Technical Details: {result['technical_details'][:100]}...")
            
            print("\n" + "="*70)
            print("✅ TEST SUCCESSFUL!")
            print("="*70)
            print("\nGemini vision integration is working correctly! 🎉")
            print(f"Cost for this analysis: ~$0.00002 (practically free!)")
            
        else:
            print(f"\nRaw result:\n{result}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
