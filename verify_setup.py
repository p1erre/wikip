#!/usr/bin/env python3
"""
Setup Verification Script

Run this script to verify your environment is set up correctly.

Usage:
    python verify_setup.py
"""

import sys
from pathlib import Path


def check_python_version() -> bool:
    """Check if Python version is 3.11+"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 11:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro}")
        print(f"   ⚠️  Python 3.11+ required")
        return False


def check_dependencies() -> bool:
    """Check if required packages are installed"""
    print("\n📦 Checking dependencies...")
    
    required = {
        "langgraph": "LangGraph",
        "langchain": "LangChain",
        "langchain_openai": "LangChain OpenAI",
        "pydantic": "Pydantic",
        "yt_dlp": "yt-dlp",
        "youtube_transcript_api": "YouTube Transcript API",
    }
    
    all_installed = True
    
    for module, name in required.items():
        try:
            __import__(module)
            print(f"   ✅ {name}")
        except ImportError:
            print(f"   ❌ {name} - not installed")
            all_installed = False
    
    return all_installed


def check_env_file() -> bool:
    """Check if .env file exists"""
    print("\n🔑 Checking environment configuration...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("   ✅ .env file found")
        
        # Check if API key is set
        with open(env_file) as f:
            content = f.read()
            if "OPENAI_API_KEY=sk-" in content or "ANTHROPIC_API_KEY=sk-ant-" in content:
                print("   ✅ API key appears to be set")
                return True
            else:
                print("   ⚠️  .env file exists but API key may not be set")
                print("   💡 Make sure to add your API key to .env")
                return True
    else:
        print("   ⚠️  .env file not found")
        if env_example.exists():
            print("   💡 Copy .env.example to .env and add your API key")
        return False


def check_project_structure() -> bool:
    """Check if project structure is correct"""
    print("\n📁 Checking project structure...")
    
    required_paths = [
        "src/tools/youtube_tools.py",
        "src/agents/video_agent.py",
        "examples/01_basic_agent.py",
        "examples/02_custom_graph.py",
        "docs/LANGGRAPH_TUTORIAL.md",
        "docs/QUICK_START.md",
        "README.md",
    ]
    
    all_exist = True
    
    for path_str in required_paths:
        path = Path(path_str)
        if path.exists():
            print(f"   ✅ {path_str}")
        else:
            print(f"   ❌ {path_str} - missing")
            all_exist = False
    
    return all_exist


def test_imports() -> bool:
    """Test if we can import our modules"""
    print("\n🧪 Testing imports...")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        
        from src.tools.youtube_tools import get_tools
        print("   ✅ Can import YouTube tools")
        
        from src.agents.video_agent import create_video_agent
        print("   ✅ Can import video agent")
        
        return True
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False


def print_summary(checks: dict[str, bool]) -> None:
    """Print summary of all checks"""
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60 + "\n")
    
    all_passed = all(checks.values())
    
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")
    
    print("\n" + "="*60 + "\n")
    
    if all_passed:
        print("🎉 All checks passed! You're ready to go!")
        print("\n📚 Next steps:")
        print("   1. Read docs/QUICK_START.md")
        print("   2. Run: python examples/01_basic_agent.py")
        print("   3. Read docs/LANGGRAPH_TUTORIAL.md")
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
        print("\n💡 Common fixes:")
        print("   - Install dependencies: pip install -r requirements.txt")
        print("   - Create .env file: cp .env.example .env")
        print("   - Add API key to .env file")
    
    print()


def main() -> None:
    """Run all verification checks"""
    print("\n" + "="*60)
    print("VIDEO-TO-BOOK SETUP VERIFICATION")
    print("="*60 + "\n")
    
    checks = {
        "Python Version": check_python_version(),
        "Dependencies": check_dependencies(),
        "Environment File": check_env_file(),
        "Project Structure": check_project_structure(),
        "Module Imports": test_imports(),
    }
    
    print_summary(checks)
    
    # Exit with error code if any check failed
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
