# Installing Slide Extraction Dependencies

## Quick Install

The robust slide extraction algorithm requires additional image processing libraries. Install them with:

```bash
# Using pip
pip install opencv-python pillow imagehash scikit-image numpy

# Or using uv
uv pip install opencv-python pillow imagehash scikit-image numpy

# Or install all project dependencies
pip install -e .
# or
uv sync
```

## Verifying Installation

Test that all dependencies are installed correctly:

```bash
python -c "import cv2, PIL, imagehash, skimage; print('✅ All dependencies installed!')"
```

## Optional: OCR Support

For text extraction from slides (optional):

### macOS
```bash
# Install Tesseract OCR
brew install tesseract

# Install Python wrapper
pip install pytesseract
```

### Ubuntu/Debian
```bash
# Install Tesseract OCR
sudo apt-get update
sudo apt-get install tesseract-ocr

# Install Python wrapper
pip install pytesseract
```

### Windows
1. Download Tesseract installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install and add to PATH
3. Install Python wrapper: `pip install pytesseract`

## Testing the Installation

Run the example script to verify everything works:

```bash
# Make sure you have a test video
python examples/09_robust_slide_extraction.py
```

## Troubleshooting

### "No module named 'cv2'"
```bash
pip install opencv-python
```

### "No module named 'imagehash'"
```bash
pip install imagehash
```

### "No module named 'skimage'"
```bash
pip install scikit-image
```

### "ImportError: numpy.core.multiarray failed to import"
```bash
# Upgrade numpy
pip install --upgrade numpy
```

### OCR Not Working
```bash
# Verify Tesseract is installed
tesseract --version

# If not found, install it (see above)
# Then install Python wrapper
pip install pytesseract
```

## System Requirements

- **Python**: 3.11 or higher
- **Memory**: At least 2GB RAM (4GB+ recommended for large videos)
- **Disk Space**: Depends on video size and number of slides
- **OS**: macOS, Linux, or Windows

## Performance Tips

1. **Faster Processing**: Reduce `fps_sample` (e.g., 1.0 instead of 2.0)
2. **Lower Memory**: Process shorter video segments
3. **Better Accuracy**: Increase `fps_sample` (e.g., 3.0 or 4.0)

## Next Steps

After installation:

1. Read [docs/ROBUST_SLIDE_EXTRACTION.md](docs/ROBUST_SLIDE_EXTRACTION.md) for usage guide
2. Run [examples/09_robust_slide_extraction.py](examples/09_robust_slide_extraction.py) for examples
3. Integrate with your video analysis workflow

## Getting Help

If you encounter issues:

1. Check that all dependencies are installed: `pip list | grep -E "opencv|imagehash|scikit-image"`
2. Verify Python version: `python --version` (should be 3.11+)
3. Try reinstalling: `pip install --force-reinstall opencv-python imagehash scikit-image`
4. Check the [troubleshooting section](docs/ROBUST_SLIDE_EXTRACTION.md#troubleshooting) in the main docs
