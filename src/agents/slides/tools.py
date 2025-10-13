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
from typing import Any, List, Dict, Optional, Tuple
import json

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _save_slide_group(slide_group: List[dict], slide_number: int, output_path: Path, unique_slides: list) -> None:
    """
    Save a group of progressive slides by keeping the most complete version (last frame).
    Also tracks all intermediate states for potential OCR merging.
    
    Args:
        slide_group: List of frame dictionaries in the group
        slide_number: Slide number to assign
        output_path: Directory to save slides
        unique_slides: List to append slide info to
    """
    import cv2
    
    # Use the last frame (most complete version) as the main slide
    last_frame_data = slide_group[-1]
    
    slide_filename = f"slide_{slide_number:03d}.jpg"
    slide_path = output_path / slide_filename
    cv2.imwrite(str(slide_path), last_frame_data["frame"])
    
    # Calculate timestamp from first frame in group
    first_frame_index = slide_group[0]["frame_index"]
    last_frame_index = last_frame_data["frame_index"]
    timestamp = first_frame_index * 2.0  # Assuming 0.5 fps
    
    slide_info = {
        "slide_number": slide_number,
        "image_path": str(slide_path),
        "timestamp": timestamp,
        "frame_index": first_frame_index,
        "num_progressive_states": len(slide_group),
        "progressive_frames": [f["frame_index"] for f in slide_group],
    }
    
    # Save intermediate states if there are multiple
    if len(slide_group) > 1:
        states_dir = output_path / f"slide_{slide_number:03d}_states"
        states_dir.mkdir(exist_ok=True)
        
        for idx, frame_data in enumerate(slide_group):
            state_filename = f"state_{idx+1:02d}.jpg"
            state_path = states_dir / state_filename
            cv2.imwrite(str(state_path), frame_data["frame"])
        
        slide_info["states_dir"] = str(states_dir)
        logger.debug(f"Saved {len(slide_group)} progressive states for slide {slide_number}")
    
    unique_slides.append(slide_info)


def _save_single_slide(frame, frame_index: int, slide_number: int, output_path: Path, unique_slides: list) -> None:
    """
    Save a single slide (non-progressive mode).
    
    Args:
        frame: OpenCV frame to save
        frame_index: Index of the frame
        slide_number: Slide number to assign
        output_path: Directory to save slides
        unique_slides: List to append slide info to
    """
    import cv2
    
    slide_filename = f"slide_{slide_number:03d}.jpg"
    slide_path = output_path / slide_filename
    cv2.imwrite(str(slide_path), frame)
    
    timestamp = frame_index * 2.0  # Assuming 0.5 fps
    
    unique_slides.append({
        "slide_number": slide_number,
        "image_path": str(slide_path),
        "timestamp": timestamp,
        "frame_index": frame_index,
        "num_progressive_states": 1,
    })


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
    output_dir: str = "./slides",
    progressive_threshold: float = 0.95,
    detect_progressive: bool = True
) -> dict[str, Any]:
    """
    Detect slide changes by comparing consecutive frames using OpenCV.
    
    Supports detection of progressive slides (slides with content appearing incrementally).
    Uses two thresholds:
    - threshold: Detects major slide changes (completely different slides)
    - progressive_threshold: Detects minor changes (content additions on same slide)
    
    Args:
        frame_paths: List of paths to extracted frames
        threshold: Major change threshold (0-1). Lower = more sensitive
        output_dir: Directory to save unique slides
        progressive_threshold: Minor change threshold for progressive content (0-1)
        detect_progressive: If True, groups progressive slides and saves the most complete version
        
    Returns:
        Dictionary with unique slides and their timestamps
        
    Example:
        >>> frames = extract_video_frames("video.mp4")['frames']
        >>> slides = detect_slide_changes(frames, threshold=0.85, detect_progressive=True)
        >>> print(f"Found {len(slides['slides'])} unique slides")
    """
    logger.info(f"Detecting slide changes from {len(frame_paths)} frames")
    logger.info(f"Progressive detection: {detect_progressive}, thresholds: major={threshold}, minor={progressive_threshold}")
    
    try:
        import cv2
        import numpy as np
        from skimage.metrics import structural_similarity as ssim
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        unique_slides = []
        current_slide_group = []  # Group of frames belonging to same progressive slide
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
            
            # Determine change type
            is_major_change = False
            is_minor_change = False
            
            if prev_frame is None:
                is_major_change = True  # First frame
            else:
                # Calculate structural similarity
                similarity = ssim(prev_frame, gray)
                
                if similarity < threshold:
                    # Major change - completely different slide
                    is_major_change = True
                    logger.debug(f"Major slide change at frame {i} (similarity: {similarity:.3f})")
                elif detect_progressive and similarity < progressive_threshold:
                    # Minor change - progressive content on same slide
                    is_minor_change = True
                    logger.debug(f"Progressive content at frame {i} (similarity: {similarity:.3f})")
            
            # Handle slide grouping
            if is_major_change:
                # Save previous slide group (if any)
                if current_slide_group:
                    slide_count += 1
                    _save_slide_group(current_slide_group, slide_count, output_path, unique_slides)
                
                # Start new slide group
                current_slide_group = [{
                    "frame_path": frame_path,
                    "frame": frame,
                    "gray": gray,
                    "frame_index": i,
                }]
                prev_frame = gray
                
            elif is_minor_change or not detect_progressive:
                # Add to current slide group (progressive content)
                if not detect_progressive and similarity < threshold:
                    # Old behavior: treat as new slide
                    slide_count += 1
                    _save_single_slide(frame, i, slide_count, output_path, unique_slides)
                    prev_frame = gray
                else:
                    # Add to group for progressive slides
                    current_slide_group.append({
                        "frame_path": frame_path,
                        "frame": frame,
                        "gray": gray,
                        "frame_index": i,
                    })
                    prev_frame = gray
        
        # Save last slide group
        if current_slide_group:
            slide_count += 1
            _save_slide_group(current_slide_group, slide_count, output_path, unique_slides)
        
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
    threshold: float = 0.85,
    progressive_threshold: float = 0.95,
    detect_progressive: bool = True
) -> dict[str, Any]:
    """
    Complete workflow: Extract frames and detect unique slides from video.
    
    This is a convenience function that combines frame extraction and slide detection.
    Supports progressive slides (slides with content appearing incrementally).
    
    Args:
        video_path: Path to the video file
        output_dir: Directory to save slides
        fps: Frames per second to extract
        threshold: Major slide change threshold (0-1)
        progressive_threshold: Minor change threshold for progressive content (0-1)
        detect_progressive: If True, groups progressive slides and saves most complete version
        
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
        output_dir,
        progressive_threshold,
        detect_progressive
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


@tool
def extract_slides_robust(
    video_path: str,
    output_dir: str = "./slides",
    fps_sample: float = 2.0,
    build_policy: str = "build_collapse",
    presenter_roi: Optional[Tuple[float, float, float, float]] = None,
    save_keyframes: bool = True,
) -> dict[str, Any]:
    """
    Extract unique slides using robust algorithm with progressive reveal detection.
    
    This is an advanced slide extraction method that:
    - Handles progressive reveals (builds) intelligently
    - Uses motion masking to ignore presenter movements
    - Performs global deduplication across the entire video
    - Supports perceptual hashing and SSIM verification
    
    Args:
        video_path: Path to the video file
        output_dir: Directory to save slides and metadata
        fps_sample: Frames per second to sample (default: 2.0)
        build_policy: How to handle progressive reveals:
            - "build_collapse": Keep final fully revealed slide (default)
            - "build_preserve": Create sub-slides for each build step
        presenter_roi: Optional region to mask presenter (x1, y1, x2, y2) in [0,1]
            Example: (0.72, 0.72, 0.98, 0.98) for bottom-right corner
        save_keyframes: Whether to save slide images to disk
        
    Returns:
        Dictionary with segments, clusters, and metadata
        
    Example:
        >>> result = extract_slides_robust(
        ...     "presentation.mp4",
        ...     output_dir="./slides",
        ...     build_policy="build_collapse",
        ...     presenter_roi=(0.72, 0.72, 0.98, 0.98)
        ... )
        >>> print(f"Found {len(result['clusters'])} unique slides")
        >>> print(f"Total segments: {len(result['segments'])}")
    """
    logger.info(f"Starting robust slide extraction from: {video_path}")
    logger.info(f"Build policy: {build_policy}, FPS: {fps_sample}")
    
    try:
        from src.agents.slides.slideseg import SlideDeduplicator
        import cv2
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize deduplicator
        dedup = SlideDeduplicator(
            fps_sample=fps_sample,
            build_policy=build_policy,
            presenter_roi=presenter_roi,
        )
        
        # Process video
        result = dedup.process_video(video_path)
        
        # Save keyframes if requested
        slides = []
        if save_keyframes:
            for cid, cluster in enumerate(result["clusters"]):
                rep_idx = cluster["rep_idx"]
                seg_data = result["segments"][rep_idx]
                
                # Get the actual segment object to access keyframe
                segment = dedup.segments[rep_idx]
                
                # Save keyframe (use original color frame, not processed grayscale)
                slide_filename = f"slide_{cid+1:03d}.jpg"
                slide_path = output_path / slide_filename
                cv2.imwrite(str(slide_path), segment.keyframe_original)
                
                # Build slide info
                slide_info = {
                    "slide_number": cid + 1,
                    "cluster_id": cid,
                    "image_path": str(slide_path),
                    "timestamp": seg_data["start"],
                    "duration": seg_data["end"] - seg_data["start"],
                    "num_occurrences": len(cluster["members"]),
                    "occurrences": [
                        {
                            "segment_idx": idx,
                            "start": result["segments"][idx]["start"],
                            "end": result["segments"][idx]["end"],
                        }
                        for idx in cluster["members"]
                    ],
                    "num_builds": len(seg_data.get("builds", [])),
                    "builds": seg_data.get("builds", []),
                }
                slides.append(slide_info)
        
        # Save metadata
        metadata_path = output_path / "slides_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump({
                "video_path": video_path,
                "build_policy": build_policy,
                "fps_sample": fps_sample,
                "num_unique_slides": len(result["clusters"]),
                "num_segments": len(result["segments"]),
                "slides": slides,
            }, f, indent=2)
        
        logger.info(f"Extracted {len(result['clusters'])} unique slides")
        logger.info(f"Total segments: {len(result['segments'])}")
        
        return {
            "success": True,
            "video_path": video_path,
            "num_unique_slides": len(result["clusters"]),
            "num_segments": len(result["segments"]),
            "slides": slides,
            "clusters": result["clusters"],
            "segments": result["segments"],
            "output_dir": output_dir,
            "metadata_path": str(metadata_path),
        }
        
    except ImportError as e:
        error_msg = f"Missing required library: {str(e)}. Install with: pip install imagehash"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    except Exception as e:
        error_msg = f"Failed to extract slides: {str(e)}"
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
        extract_slides_robust,
        analyze_slide_content,
        align_slides_with_transcript,
    ]
