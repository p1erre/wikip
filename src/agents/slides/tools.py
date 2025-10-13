"""
Slide Extraction Tools

Tools for extracting slides from presentation videos using:
- ffmpeg for frame extraction
- OpenCV for slide change detection
- Tesseract/EasyOCR for text extraction
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, List, Dict
import json

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FrameExtractionInput(BaseModel):
    """Input schema for frame extraction"""
    video_path: str = Field(description="Path to the video file")
    output_dir: str = Field(description="Directory to save extracted frames")
    fps: float = Field(default=0.5, description="Frames per second to extract (default: 0.5 = 1 frame every 2 seconds)")


class SlideAnalysisInput(BaseModel):
    """Input schema for slide content analysis"""
    image_path: str = Field(description="Path to the slide image")


class SlideAlignmentInput(BaseModel):
    """Input schema for slide-transcript alignment"""
    slides: list = Field(description="List of slides with timestamps")
    transcript: dict = Field(description="Transcript with segments")


@tool(args_schema=FrameExtractionInput)
def extract_video_frames(
    video_path: str,
    output_dir: str = "./frames",
    fps: float = 0.5
) -> dict[str, Any]:
    """
    Extract frames from video at specified frame rate using ffmpeg.
    
    Args:
        video_path: Path to the video file
        output_dir: Directory to save extracted frames
        fps: Frames per second to extract (0.5 = 1 frame every 2 seconds)
        
    Returns:
        Dictionary with success status and list of frame paths
        
    Example:
        >>> result = extract_video_frames("video.mp4", "./frames", fps=0.5)
        >>> print(f"Extracted {len(result['frames'])} frames")
    """
    logger.info(f"Extracting frames from video: {video_path} at {fps} fps")
    
    try:
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Output pattern for frames
        frame_pattern = str(output_path / "frame_%04d.jpg")
        
        # ffmpeg command to extract frames
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vf", f"fps={fps}",  # Extract at specified fps
            "-q:v", "2",  # High quality
            frame_pattern,
            "-y"  # Overwrite existing files
        ]
        
        # Run ffmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Get list of extracted frames
        frames = sorted(output_path.glob("frame_*.jpg"))
        frame_paths = [str(f) for f in frames]
        
        logger.info(f"Successfully extracted {len(frame_paths)} frames")
        
        return {
            "success": True,
            "num_frames": len(frame_paths),
            "frames": frame_paths,
            "output_dir": output_dir,
        }
        
    except subprocess.CalledProcessError as e:
        error_msg = f"ffmpeg error: {e.stderr}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    except Exception as e:
        error_msg = f"Failed to extract frames: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


@tool
def detect_slide_changes(
    frame_paths: List[str],
    threshold: float = 0.85,
    output_dir: str = "./slides"
) -> dict[str, Any]:
    """
    Detect slide changes by comparing consecutive frames using OpenCV.
    
    Identifies unique slides by detecting significant visual changes between frames.
    
    Args:
        frame_paths: List of paths to extracted frames
        threshold: Similarity threshold (0-1). Lower = more sensitive to changes
        output_dir: Directory to save unique slides
        
    Returns:
        Dictionary with unique slides and their timestamps
        
    Example:
        >>> frames = extract_video_frames("video.mp4")['frames']
        >>> slides = detect_slide_changes(frames, threshold=0.85)
        >>> print(f"Found {len(slides['slides'])} unique slides")
    """
    logger.info(f"Detecting slide changes from {len(frame_paths)} frames")
    
    try:
        import cv2
        import numpy as np
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        unique_slides = []
        prev_frame = None
        slide_count = 0
        
        for i, frame_path in enumerate(frame_paths):
            # Read frame
            frame = cv2.imread(frame_path)
            if frame is None:
                logger.warning(f"Could not read frame: {frame_path}")
                continue
            
            # Convert to grayscale for comparison
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Compare with previous frame
            is_new_slide = False
            if prev_frame is None:
                is_new_slide = True  # First frame
            else:
                # Calculate structural similarity
                from skimage.metrics import structural_similarity as ssim
                similarity = ssim(prev_frame, gray)
                
                if similarity < threshold:
                    is_new_slide = True
                    logger.debug(f"Slide change detected at frame {i} (similarity: {similarity:.3f})")
            
            # Save unique slide
            if is_new_slide:
                slide_count += 1
                slide_filename = f"slide_{slide_count:03d}.jpg"
                slide_path = output_path / slide_filename
                cv2.imwrite(str(slide_path), frame)
                
                # Calculate timestamp (assuming frame number corresponds to time)
                # This will be refined when we have video metadata
                timestamp = i * 2.0  # Assuming 0.5 fps (1 frame per 2 seconds)
                
                unique_slides.append({
                    "slide_number": slide_count,
                    "image_path": str(slide_path),
                    "timestamp": timestamp,
                    "frame_index": i,
                })
                
                prev_frame = gray
        
        logger.info(f"Detected {len(unique_slides)} unique slides")
        
        return {
            "success": True,
            "num_slides": len(unique_slides),
            "slides": unique_slides,
            "output_dir": output_dir,
        }
        
    except ImportError as e:
        error_msg = f"Missing required library: {str(e)}. Install with: pip install opencv-python scikit-image"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    except Exception as e:
        error_msg = f"Failed to detect slide changes: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


@tool
def extract_slides(
    video_path: str,
    output_dir: str = "./slides",
    fps: float = 0.5,
    threshold: float = 0.85
) -> dict[str, Any]:
    """
    Complete workflow: Extract frames and detect unique slides from video.
    
    This is a convenience function that combines frame extraction and slide detection.
    
    Args:
        video_path: Path to the video file
        output_dir: Directory to save slides
        fps: Frames per second to extract
        threshold: Similarity threshold for slide change detection
        
    Returns:
        Dictionary with unique slides and metadata
        
    Example:
        >>> result = extract_slides("presentation.mp4", output_dir="./slides")
        >>> for slide in result['slides']:
        ...     print(f"Slide {slide['slide_number']} at {slide['timestamp']}s")
    """
    logger.info(f"Starting slide extraction from: {video_path}")
    
    # Step 1: Extract frames
    frames_dir = f"{output_dir}/frames"
    frames_result = extract_video_frames.func(video_path, frames_dir, fps)
    
    if not frames_result.get("success"):
        return frames_result
    
    # Step 2: Detect slide changes
    slides_result = detect_slide_changes.func(
        frames_result["frames"],
        threshold,
        output_dir
    )
    
    if not slides_result.get("success"):
        return slides_result
    
    logger.info(f"Slide extraction complete: {slides_result['num_slides']} slides")
    
    return {
        "success": True,
        "video_path": video_path,
        "num_frames": frames_result["num_frames"],
        "num_slides": slides_result["num_slides"],
        "slides": slides_result["slides"],
        "output_dir": output_dir,
    }


@tool(args_schema=SlideAnalysisInput)
def analyze_slide_content(image_path: str) -> dict[str, Any]:
    """
    Extract text content from slide image using OCR (Tesseract/EasyOCR).
    
    Args:
        image_path: Path to the slide image
        
    Returns:
        Dictionary with extracted text and confidence
        
    Example:
        >>> content = analyze_slide_content("slide_001.jpg")
        >>> print(content['text'])
    """
    logger.info(f"Analyzing slide content: {image_path}")
    
    try:
        import pytesseract
        from PIL import Image
        
        # Open image
        image = Image.open(image_path)
        
        # Extract text using Tesseract
        text = pytesseract.image_to_string(image)
        
        # Get detailed data with confidence scores
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        
        # Calculate average confidence
        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        logger.info(f"Extracted {len(text)} characters with {avg_confidence:.1f}% confidence")
        
        return {
            "success": True,
            "image_path": image_path,
            "text": text.strip(),
            "confidence": avg_confidence,
            "num_words": len(text.split()),
        }
        
    except ImportError as e:
        error_msg = f"Missing required library: {str(e)}. Install with: pip install pytesseract pillow"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    except Exception as e:
        error_msg = f"Failed to analyze slide: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


@tool(args_schema=SlideAlignmentInput)
def align_slides_with_transcript(
    slides: list,
    transcript: dict
) -> dict[str, Any]:
    """
    Align slides with transcript segments based on timestamps.
    
    Matches each slide to the transcript segments that occur during that slide's display time.
    
    Args:
        slides: List of slides with timestamps
        transcript: Transcript dictionary with segments
        
    Returns:
        Dictionary with aligned slides and their corresponding transcript text
        
    Example:
        >>> slides = extract_slides("video.mp4")['slides']
        >>> transcript = get_youtube_transcript("video_id")
        >>> aligned = align_slides_with_transcript(slides, transcript)
    """
    logger.info(f"Aligning {len(slides)} slides with transcript")
    
    try:
        transcript_segments = transcript.get('segments', [])
        
        aligned_slides = []
        
        for i, slide in enumerate(slides):
            slide_start = slide['timestamp']
            # End time is the start of next slide, or end of video
            slide_end = slides[i + 1]['timestamp'] if i + 1 < len(slides) else float('inf')
            
            # Find transcript segments within this slide's time range
            matching_segments = [
                seg for seg in transcript_segments
                if seg['start'] >= slide_start and seg['start'] < slide_end
            ]
            
            # Combine segment texts
            slide_transcript = ' '.join(seg['text'] for seg in matching_segments)
            
            aligned_slides.append({
                **slide,
                'transcript': slide_transcript,
                'num_segments': len(matching_segments),
                'duration': slide_end - slide_start if slide_end != float('inf') else None,
            })
        
        logger.info(f"Successfully aligned {len(aligned_slides)} slides with transcript")
        
        return {
            "success": True,
            "num_slides": len(aligned_slides),
            "slides": aligned_slides,
        }
        
    except Exception as e:
        error_msg = f"Failed to align slides: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


def get_slides_tools() -> list:
    """
    Get all slide extraction tools.
    
    Returns:
        List of tool functions for slide extraction
    """
    return [
        extract_video_frames,
        detect_slide_changes,
        extract_slides,
        analyze_slide_content,
        align_slides_with_transcript,
    ]
