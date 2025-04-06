"""
Auto text color detection module for Enhanced Content-Aware Fill.
This module provides functionality to detect whether text in a selection
is dark on light background or light on dark background.

"""

import cv2
import numpy as np
from scipy import ndimage


def auto_detect_text_color(image, selection_coords):
    """
    Automatically detect whether text in the selection is dark or light.

    Args:
        image: PIL Image to analyze
        selection_coords: Tuple (x1, y1, x2, y2) of selection coordinates

    Returns:
        tuple: (is_dark_text, color_rgb, point_xy, threshold)
            - is_dark_text: Boolean, True if text is detected as dark, False if light
            - color_rgb: RGB tuple of the detected text color
            - point_xy: (x, y) coordinates of the detected text color in the original image
            - threshold: Recommended threshold value for color selection
    """
    # Extract the selection area
    x1, y1, x2, y2 = selection_coords

    # Ensure coordinates are within bounds
    x1 = max(0, min(x1, image.width - 1))
    y1 = max(0, min(y1, image.height - 1))
    x2 = max(0, min(x2, image.width))
    y2 = max(0, min(y2, image.height))

    # Crop the image to the selection area
    selection_area = image.crop((x1, y1, x2, y2))

    # Convert to numpy array for processing
    selection_np = np.array(selection_area)

    # Calculate luminance
    if len(selection_np.shape) == 3 and selection_np.shape[2] >= 3:
        # For RGB/RGBA images - calculate luminance
        luminance = 0.299 * selection_np[:, :, 0] + 0.587 * selection_np[:, :, 1] + 0.114 * selection_np[:, :, 2]
    else:
        # For grayscale images
        luminance = selection_np.copy()

    # Calculate histogram of the luminance
    hist, bins = np.histogram(luminance.flatten(), bins=256, range=(0, 256))

    # Calculate median and mean luminance
    median_luminance = np.median(luminance)
    mean_luminance = np.mean(luminance)

    # Perform bi-modal analysis to detect foreground/background separation
    # Use Otsu's method to find optimal threshold
    otsu_thresh, _ = cv2.threshold(luminance.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Calculate pixel counts below and above threshold
    dark_pixels = np.sum(luminance < otsu_thresh)
    light_pixels = np.sum(luminance >= otsu_thresh)

    # Calculate the ratio of dark to light pixels
    dark_ratio = dark_pixels / (dark_pixels + light_pixels) if (dark_pixels + light_pixels) > 0 else 0

    # For debugging
    # print(f"Otsu threshold: {otsu_thresh}, Dark ratio: {dark_ratio}, Mean: {mean_luminance}, Median: {median_luminance}")

    # Determine if text is dark or light
    # Typically, text takes up less area than background
    is_dark_text = dark_ratio < 0.5

    # Find either the darkest or lightest point based on our determination
    if is_dark_text:
        # Text is dark, find darkest point
        target_y, target_x = np.unravel_index(luminance.argmin(), luminance.shape)
        # Get the color of the darkest pixel
        if len(selection_np.shape) == 3 and selection_np.shape[2] >= 3:
            color = selection_np[target_y, target_x][:3]  # Get only RGB components
        else:
            # For grayscale images
            color_value = selection_np[target_y, target_x]
            color = (color_value, color_value, color_value)  # Convert to RGB tuple

        # Adjust threshold for dark text (typically need higher tolerance)
        threshold = 60
    else:
        # Text is light, find lightest point
        target_y, target_x = np.unravel_index(luminance.argmax(), luminance.shape)
        # Get the color of the lightest pixel
        if len(selection_np.shape) == 3 and selection_np.shape[2] >= 3:
            color = selection_np[target_y, target_x][:3]  # Get only RGB components
        else:
            # For grayscale images
            color_value = selection_np[target_y, target_x]
            color = (color_value, color_value, color_value)  # Convert to RGB tuple

        # Adjust threshold for light text (typically need lower tolerance)
        threshold = 50

    # Calculate position in original image coordinates
    point = (x1 + target_x, y1 + target_y)

    # Further analyze to refine the color by finding similar colored pixels
    # This helps avoid selecting noise or outlier pixels
    if len(selection_np.shape) == 3 and selection_np.shape[2] >= 3:
        # Create mask where pixels are within preliminary tolerance of the selected color
        color_diffs = np.sum(np.abs(selection_np - np.array(color)), axis=2)
        prelim_mask = (color_diffs <= threshold).astype(np.uint8)

        # If we have very few pixels, gradually increase tolerance
        pixel_count = np.sum(prelim_mask)
        min_pixels = 50  # Minimum number of pixels we want to have

        while pixel_count < min_pixels and threshold < 200:
            threshold += 10
            color_diffs = np.sum(np.abs(selection_np - np.array(color)), axis=2)
            prelim_mask = (color_diffs <= threshold).astype(np.uint8)
            pixel_count = np.sum(prelim_mask)

        # If we have enough pixels, refine the color by taking the average of similar pixels
        if pixel_count >= min_pixels:
            refined_color = np.mean(selection_np[prelim_mask > 0], axis=0)[:3].astype(np.uint8)
            color = tuple(refined_color)

    return (is_dark_text, color, point, threshold)


def get_text_mask(image, selection_coords, tolerance=None, border_size=3):
    """
    Generate a mask for text in the selection area with automatic detection
    of whether text is dark or light.

    Args:
        image: PIL Image to analyze
        selection_coords: Tuple (x1, y1, x2, y2) of selection coordinates
        tolerance: Optional tolerance override (if None, auto-detected)
        border_size: Size of border expansion around detected text pixels

    Returns:
        tuple: (mask, is_dark_text, color_rgb)
            - mask: numpy array mask where text pixels are 255, others 0
            - is_dark_text: Boolean, True if text is detected as dark, False if light
            - color_rgb: RGB tuple of the detected text color
    """
    # First detect whether text is dark or light
    is_dark_text, color, point, auto_tolerance = auto_detect_text_color(image, selection_coords)

    # Use provided tolerance if specified, otherwise use auto-detected
    if tolerance is None:
        tolerance = auto_tolerance

    # Extract the selection area
    x1, y1, x2, y2 = selection_coords

    # Ensure coordinates are within bounds
    x1 = max(0, min(x1, image.width - 1))
    y1 = max(0, min(y1, image.height - 1))
    x2 = max(0, min(x2, image.width))
    y2 = max(0, min(y2, image.height))

    # Convert to numpy array for processing
    img_np = np.array(image)

    # Create a base mask that's zero everywhere except in the current selection
    base_mask = np.zeros((img_np.shape[0], img_np.shape[1]), dtype=np.uint8)
    base_mask[y1:y2, x1:x2] = 255

    # Handle different image types
    if len(img_np.shape) == 2:  # Grayscale
        # Convert grayscale to RGB for consistent processing
        img_rgb = np.stack([img_np, img_np, img_np], axis=2)
    elif len(img_np.shape) == 3:
        if img_np.shape[2] == 4:  # RGBA
            img_rgb = img_np[:, :, :3]  # Take just the RGB channels
        elif img_np.shape[2] == 3:  # RGB
            img_rgb = img_np
        else:
            raise ValueError(f"Unexpected image format with {img_np.shape[2]} channels")
    else:
        raise ValueError(f"Unexpected image shape: {img_np.shape}")

    # Calculate color difference
    color_diffs = np.sum(np.abs(img_rgb - np.array(color)), axis=2)
    color_mask = (color_diffs <= tolerance).astype(np.uint8) * 255

    # Intersect the color mask with the base mask to restrict to current selection
    mask = cv2.bitwise_and(color_mask, base_mask)

    # Apply border expansion if needed
    if border_size > 0:
        kernel = np.ones((border_size * 2 + 1, border_size * 2 + 1), np.uint8)
        expanded_mask = cv2.dilate(mask, kernel, iterations=1)
        # Re-intersect with the base mask to ensure we don't expand outside the selection
        mask = cv2.bitwise_and(expanded_mask, base_mask)

    return (mask, is_dark_text, color)


def analyze_text_regions(image, selection_coords):
    """
    Analyze the text regions in an image selection using advanced image processing
    to improve text detection in complex cases.

    Args:
        image: PIL Image to analyze
        selection_coords: Tuple (x1, y1, x2, y2) of selection coordinates

    Returns:
        tuple: (is_dark_text, color_rgb, point_xy, threshold, confidence)
    """
    # Extract the selection area
    x1, y1, x2, y2 = selection_coords

    # Ensure coordinates are within bounds
    x1 = max(0, min(x1, image.width - 1))
    y1 = max(0, min(y1, image.height - 1))
    x2 = max(0, min(x2, image.width))
    y2 = max(0, min(y2, image.height))

    # Crop the image to the selection area
    selection_area = image.crop((x1, y1, x2, y2))

    # Convert to numpy array for processing
    img_np = np.array(selection_area)

    # Convert to grayscale if needed
    if len(img_np.shape) == 3:
        # RGB or RGBA image
        if img_np.shape[2] == 4:  # RGBA
            # Convert to RGB first
            img_rgb = img_np[:, :, :3]
        else:
            img_rgb = img_np

        # Convert to grayscale
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    else:
        # Already grayscale
        gray = img_np

    # Apply adaptive thresholding to better separate text
    # Block size and C value can be adjusted based on image characteristics
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

    # Also get the inverse
    binary_inv = cv2.bitwise_not(binary)

    # Use connected component analysis on both binary and inverse binary
    # This helps determine if text is dark or light
    num_labels_dark, labels_dark, stats_dark, centroids_dark = cv2.connectedComponentsWithStats(binary, connectivity=8)

    num_labels_light, labels_light, stats_light, centroids_light = cv2.connectedComponentsWithStats(
        binary_inv, connectivity=8
    )

    # Analyze component statistics to determine text properties
    # Typically, text components have certain characteristics:
    # - Similar sizes
    # - Aligned horizontally or vertically
    # - Consistent spacing

    # Filter out very small components (noise)
    min_area = 5  # Minimum area to consider a valid component

    # Process dark components (potential dark text)
    valid_dark_components = []
    for i in range(1, num_labels_dark):  # Skip background (label 0)
        area = stats_dark[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            valid_dark_components.append({
                "area": area,
                "width": stats_dark[i, cv2.CC_STAT_WIDTH],
                "height": stats_dark[i, cv2.CC_STAT_HEIGHT],
                "x": stats_dark[i, cv2.CC_STAT_LEFT],
                "y": stats_dark[i, cv2.CC_STAT_TOP],
                "centroid": centroids_dark[i],
            })

    # Process light components (potential light text)
    valid_light_components = []
    for i in range(1, num_labels_light):  # Skip background (label 0)
        area = stats_light[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            valid_light_components.append({
                "area": area,
                "width": stats_light[i, cv2.CC_STAT_WIDTH],
                "height": stats_light[i, cv2.CC_STAT_HEIGHT],
                "x": stats_light[i, cv2.CC_STAT_LEFT],
                "y": stats_light[i, cv2.CC_STAT_TOP],
                "centroid": centroids_light[i],
            })

    # Calculate text-likeness score for dark and light components
    dark_score = calculate_text_likeness(valid_dark_components, gray.shape)
    light_score = calculate_text_likeness(valid_light_components, gray.shape)

    # Additional analysis: check if components align like text (horizontally or vertically)
    dark_alignment = calculate_alignment_score(valid_dark_components)
    light_alignment = calculate_alignment_score(valid_light_components)

    # Combine scores
    dark_total_score = dark_score * (1 + dark_alignment)
    light_total_score = light_score * (1 + light_alignment)

    # Determine if text is dark or light based on combined scores
    is_dark_text = dark_total_score > light_total_score
    confidence = abs(dark_total_score - light_total_score) / max(dark_total_score + light_total_score, 1)

    # Get the appropriate color based on our determination
    if is_dark_text:
        # Find dark pixels - first get the darkest 10% of pixels
        flat_gray = gray.flatten()
        sorted_pixels = np.sort(flat_gray)
        dark_threshold = sorted_pixels[int(len(sorted_pixels) * 0.1)]

        # Create a mask of dark pixels
        dark_mask = gray < dark_threshold

        # Find the average color of these dark pixels in the original image
        if len(img_np.shape) == 3:
            dark_color = np.mean(img_rgb[dark_mask], axis=0).astype(np.uint8)
        else:
            # For grayscale
            dark_value = np.mean(gray[dark_mask]).astype(np.uint8)
            dark_color = (dark_value, dark_value, dark_value)

        # Find the location of the darkest pixel for point reference
        darkest_y, darkest_x = np.unravel_index(gray.argmin(), gray.shape)
        point = (x1 + darkest_x, y1 + darkest_y)

        # Set an appropriate threshold - can be tuned based on testing
        threshold = 60

        return (is_dark_text, tuple(dark_color), point, threshold, confidence)
    else:
        # Find light pixels - first get the lightest 10% of pixels
        flat_gray = gray.flatten()
        sorted_pixels = np.sort(flat_gray)
        light_threshold = sorted_pixels[int(len(sorted_pixels) * 0.9)]

        # Create a mask of light pixels
        light_mask = gray > light_threshold

        # Find the average color of these light pixels in the original image
        if len(img_np.shape) == 3:
            light_color = np.mean(img_rgb[light_mask], axis=0).astype(np.uint8)
        else:
            # For grayscale
            light_value = np.mean(gray[light_mask]).astype(np.uint8)
            light_color = (light_value, light_value, light_value)

        # Find the location of the lightest pixel for point reference
        lightest_y, lightest_x = np.unravel_index(gray.argmax(), gray.shape)
        point = (x1 + lightest_x, y1 + lightest_y)

        # Set an appropriate threshold - can be tuned based on testing
        threshold = 50

        return (is_dark_text, tuple(light_color), point, threshold, confidence)


def calculate_text_likeness(components, image_shape):
    """
    Calculate how likely the given components represent text.

    Args:
        components: List of component dictionaries with stats
        image_shape: Shape of the image (height, width)

    Returns:
        float: Score indicating text-likeness (higher is more text-like)
    """
    if not components:
        return 0.0

    # Text-likeness factors:

    # 1. Component count - text typically consists of multiple components
    component_count_score = min(1.0, len(components) / 10.0)

    # 2. Component density - text components are often close to each other
    image_area = image_shape[0] * image_shape[1]
    components_area = sum(c["area"] for c in components)
    density_score = components_area / image_area
    # Penalize if too dense (might be a background) or too sparse
    density_score = 1.0 - abs(0.15 - density_score) * 2.0
    density_score = max(0.0, min(1.0, density_score))

    # 3. Size consistency - text components often have similar sizes
    if len(components) > 1:
        areas = [c["area"] for c in components]
        mean_area = np.mean(areas)
        std_area = np.std(areas)
        cv_area = std_area / mean_area if mean_area > 0 else float("inf")
        # Lower coefficient of variation means more consistent sizes
        size_consistency_score = max(0.0, min(1.0, 1.0 - min(cv_area, 1.0)))
    else:
        size_consistency_score = 0.5  # Neutral for single component

    # 4. Aspect ratio - text components often have specific aspect ratios
    # (not too elongated in either direction)
    aspect_ratios = []
    for c in components:
        if c["height"] > 0 and c["width"] > 0:
            aspect_ratio = c["width"] / c["height"]
            aspect_ratios.append(aspect_ratio)

    if aspect_ratios:
        # Calculate how close aspect ratios are to typical text aspect ratios
        # (around 0.5-2.0 for most characters)
        aspect_score = 0.0
        for ar in aspect_ratios:
            if 0.2 <= ar <= 5.0:
                aspect_closeness = 1.0 - min(abs(1.0 - ar) / 4.0, 1.0)
                aspect_score += aspect_closeness
        aspect_score /= len(aspect_ratios)
    else:
        aspect_score = 0.0

    # Combine all factors with weights
    final_score = (
        0.3 * component_count_score + 0.25 * density_score + 0.25 * size_consistency_score + 0.2 * aspect_score
    )

    return final_score


def calculate_alignment_score(components):
    """
    Calculate how well components align like text (horizontally or vertically).

    Args:
        components: List of component dictionaries with stats

    Returns:
        float: Alignment score (higher means better alignment)
    """
    if len(components) < 3:
        return 0.0  # Need at least 3 components to measure alignment

    # Get centroids
    centroids = np.array([c["centroid"] for c in components])

    # Check horizontal alignment (y-coordinates of centroids should be similar for each text line)
    # Group components by approximate y-coordinate to find potential text lines
    y_coords = centroids[:, 1]
    y_sorted_indices = np.argsort(y_coords)
    y_sorted = y_coords[y_sorted_indices]

    # Find potential line breaks using a threshold
    line_height_estimate = np.median([c["height"] for c in components])
    line_threshold = max(line_height_estimate * 0.5, 5)  # Adaptive threshold

    lines = []
    current_line = [y_sorted_indices[0]]

    for i in range(1, len(y_sorted)):
        if y_sorted[i] - y_sorted[i - 1] > line_threshold:
            # New line
            lines.append(current_line)
            current_line = [y_sorted_indices[i]]
        else:
            current_line.append(y_sorted_indices[i])

    if current_line:
        lines.append(current_line)

    # Calculate horizontal alignment score based on how many lines we found
    # and how well components align within each line
    if not lines:
        return 0.0

    # Average number of components per line
    avg_components_per_line = len(components) / len(lines)

    # Score based on having multiple components per line (typical for text)
    if avg_components_per_line < 1.5:
        horizontal_alignment_score = 0.1  # Poor alignment
    elif avg_components_per_line < 3:
        horizontal_alignment_score = 0.5  # Moderate alignment
    else:
        horizontal_alignment_score = 1.0  # Good alignment

    # Check vertical alignment within each line
    vertical_variance_scores = []

    for line in lines:
        if len(line) < 2:
            continue

        # Get y-coordinates of this line's components
        line_y_coords = [centroids[idx][1] for idx in line]
        # Calculate variance of y-coordinates
        line_y_variance = np.var(line_y_coords)

        # Normalize by line height estimate
        if line_height_estimate > 0:
            normalized_variance = line_y_variance / (line_height_estimate * line_height_estimate)
            # Lower variance means better alignment
            line_score = max(0.0, min(1.0, 1.0 - normalized_variance))
            vertical_variance_scores.append(line_score)

    # Average vertical alignment score across all lines
    if vertical_variance_scores:
        vertical_alignment_score = np.mean(vertical_variance_scores)
    else:
        vertical_alignment_score = 0.0

    # Combine horizontal and vertical alignment scores
    alignment_score = 0.7 * horizontal_alignment_score + 0.3 * vertical_alignment_score

    return alignment_score


def enhanced_auto_detect_text_color(image, selection_coords):
    """
    Enhanced text color detection that combines traditional luminance analysis
    with advanced text region analysis for more robust results.

    Args:
        image: PIL Image to analyze
        selection_coords: Tuple (x1, y1, x2, y2) of selection coordinates

    Returns:
        tuple: (is_dark_text, color_rgb, point_xy, threshold)
    """
    # Get results from both methods
    basic_is_dark, basic_color, basic_point, basic_threshold = auto_detect_text_color(image, selection_coords)

    try:
        # Try the advanced method
        advanced_is_dark, advanced_color, advanced_point, advanced_threshold, confidence = analyze_text_regions(
            image, selection_coords
        )

        # If confidence is high enough, use advanced method
        if confidence > 0.3:
            return (advanced_is_dark, advanced_color, advanced_point, advanced_threshold)
        else:
            # Fall back to basic method
            return (basic_is_dark, basic_color, basic_point, basic_threshold)
    except Exception as e:
        # If advanced method fails, fall back to basic method
        print(f"Advanced text detection failed: {str(e)}. Using basic method.")
        return (basic_is_dark, basic_color, basic_point, basic_threshold)
