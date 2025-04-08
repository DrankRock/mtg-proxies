"""
Enhanced Content-Aware Fill module for image editing
"""

# Import the auto text detection functionality
from .auto_text_color import auto_detect_text_color, enhanced_auto_detect_text_color, get_text_mask

# Import the main class directly into the package namespace
from .enhanced_content_aware_fill import EnhancedContentAwareFill

# This makes it so you can import directly from the package
# e.g., from content_aware_fill import EnhancedContentAwareFill
__all__ = ["EnhancedContentAwareFill", "auto_detect_text_color", "enhanced_auto_detect_text_color", "get_text_mask"]
