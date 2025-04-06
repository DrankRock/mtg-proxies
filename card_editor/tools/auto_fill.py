"""
Auto-fill tool implementation
"""

import tkinter as tk

import cv2
import numpy as np
from PIL import Image

from contentAwareFill import EnhancedContentAwareFill


def apply_auto_dark_fill(editor, use_gui=False):
    """
    Apply auto dark content-aware fill to the selected area

    Args:
        editor: CardEditor instance
        use_gui: Whether to use the GUI or the windowless implementation
    """
    if not editor.selection_coords:
        return

    if use_gui:
        # Create the enhanced fill dialog with explicit auto-apply
        fill_handler = EnhancedContentAwareFill(editor, editor.selection_coords)

        # Call the auto_apply_dark_fill method directly
        # We need to wait a bit for the dialog to initialize
        fill_handler.fill_dialog.after(100, fill_handler.auto_apply_dark_fill)
    else:
        # Use the windowless implementation
        apply_auto_dark_fill_windowless(editor)


def apply_auto_dark_fill_windowless(editor, clear_selection=True):
    """
    Apply auto text fill without opening the UI

    Args:
        editor: CardEditor instance
        clear_selection: Whether to clear selection after application
    """
    if not editor.selection_coords:
        return

    # Get the current selection coordinates
    x1, y1, x2, y2 = editor.selection_coords

    try:
        # Show processing status
        editor.status_label.config(text="Applying auto fill...")

        # Get selection area
        selection_area = editor.working_image.crop((x1, y1, x2, y2))

        # Convert to numpy array for processing
        selection_np = np.array(selection_area)

        # Get color to match based on the selected detection mode
        detection_mode = editor.color_detect_mode.get()

        if detection_mode == "dark":
            # Detect darkest pixel
            if len(selection_np.shape) == 3 and selection_np.shape[2] >= 3:
                luminance = (
                    0.299 * selection_np[:, :, 0] + 0.587 * selection_np[:, :, 1] + 0.114 * selection_np[:, :, 2]
                )
                min_y, min_x = np.unravel_index(luminance.argmin(), luminance.shape)
                target_color = selection_np[min_y, min_x][:3]
            else:
                min_y, min_x = np.unravel_index(selection_np.argmin(), selection_np.shape)
                dark_value = selection_np[min_y, min_x]
                target_color = (dark_value, dark_value, dark_value)

        elif detection_mode == "light":
            # Detect lightest pixel
            if len(selection_np.shape) == 3 and selection_np.shape[2] >= 3:
                luminance = (
                    0.299 * selection_np[:, :, 0] + 0.587 * selection_np[:, :, 1] + 0.114 * selection_np[:, :, 2]
                )
                max_y, max_x = np.unravel_index(luminance.argmax(), luminance.shape)
                target_color = selection_np[max_y, max_x][:3]
            else:
                max_y, max_x = np.unravel_index(selection_np.argmax(), selection_np.shape)
                light_value = selection_np[max_y, max_x]
                target_color = (light_value, light_value, light_value)

        else:  # custom
            # Use the color from the color picker
            color_hex = editor.text_color_var.get()
            # Convert HEX to RGB
            target_color = (int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16))

        # Get the full image in numpy array format
        img_np = np.array(editor.working_image)

        # Get settings from UI
        tolerance = editor.fill_tolerance_var.get()
        border_size = editor.fill_border_var.get()
        use_advanced = editor.advanced_detection_var.get()

        # Create mask for inpainting
        mask = np.zeros((editor.working_image.height, editor.working_image.width), dtype=np.uint8)

        if use_advanced:
            # Advanced text detection approach
            # Extract selection area for processing
            selection_area = img_np[y1:y2, x1:x2]

            # Convert to grayscale for easier processing if it's RGB
            if len(selection_area.shape) == 3:
                if detection_mode == "dark" or detection_mode == "custom":
                    # For dark text or custom color, convert to grayscale or calculate color distance
                    if detection_mode == "custom":
                        # Calculate distance from target color
                        target_color_np = np.array(target_color)
                        color_diffs = np.sum(np.abs(selection_area - target_color_np.reshape(1, 1, 3)), axis=2)
                        gray_selection = color_diffs.astype(np.uint8)
                    else:
                        # Convert RGB to grayscale using standard formula
                        gray_selection = np.dot(selection_area[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
                else:  # light mode
                    # Invert to make light text appear dark
                    gray_selection = 255 - np.dot(selection_area[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
            else:
                # Already grayscale
                gray_selection = selection_area.copy()
                if detection_mode == "light":
                    gray_selection = 255 - gray_selection  # Invert for light text

            # Apply adaptive thresholding to better separate text from background
            binary_selection = cv2.adaptiveThreshold(
                gray_selection,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV,
                11,  # Block size
                2,  # Constant subtracted from mean
            )

            # Apply morphological operations to improve text detection
            # Create a small kernel for thin text
            kernel = np.ones((2, 2), np.uint8)

            # Open operation (erosion followed by dilation) to remove noise
            opened = cv2.morphologyEx(binary_selection, cv2.MORPH_OPEN, kernel)

            # Additional dilate to ensure thin text is fully covered
            selection_mask = cv2.dilate(opened, kernel, iterations=1)

            # Use tolerance as a threshold for final adjustment
            if tolerance > 100:  # If high tolerance, apply additional dilation
                extra_kernel = np.ones((tolerance // 50 + 1, tolerance // 50 + 1), np.uint8)
                selection_mask = cv2.dilate(selection_mask, extra_kernel, iterations=1)

            # Place selection mask into the full mask
            mask[y1:y2, x1:x2] = selection_mask

        else:
            # Simple color-based detection approach
            # Handle different image types
            if len(img_np.shape) == 2:  # Grayscale
                img_rgb = np.stack([img_np, img_np, img_np], axis=2)
            elif len(img_np.shape) == 3:
                if img_np.shape[2] == 4:  # RGBA
                    img_rgb = img_np[:, :, :3]
                elif img_np.shape[2] == 3:  # RGB
                    img_rgb = img_np
                else:
                    raise ValueError(f"Unexpected image format with {img_np.shape[2]} channels")
            else:
                raise ValueError(f"Unexpected image shape: {img_np.shape}")

            # Calculate color differences ONLY in the selection area
            # Initialize the color mask with zeros
            color_mask = np.zeros((editor.working_image.height, editor.working_image.width), dtype=np.uint8)

            # Calculate color differences for the selection area
            selection_rgb = img_rgb[y1:y2, x1:x2]
            color_diffs = np.sum(np.abs(selection_rgb - np.array(target_color)), axis=2)
            selection_color_mask = (color_diffs <= tolerance).astype(np.uint8) * 255

            # Place the selection color mask into the full mask
            color_mask[y1:y2, x1:x2] = selection_color_mask

            # Set the mask
            mask = color_mask

        # Apply border expansion if needed
        if border_size > 0:
            kernel = np.ones((border_size * 2 + 1, border_size * 2 + 1), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=1)

        # Count pixels in mask for feedback
        pixel_count = np.sum(mask > 0)

        # Apply OpenCV inpainting (using Telea algorithm)
        img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        result = cv2.inpaint(img_cv, mask, 5, cv2.INPAINT_TELEA)

        # Convert back to RGB and PIL format
        result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        result_img = Image.fromarray(result_rgb)

        # Update working image
        editor.working_image = result_img

        # Update UI
        editor.update_display()

        if clear_selection:
            editor.reset_selection()

        # Update status with color info
        color_hex = f"#{target_color[0]:02x}{target_color[1]:02x}{target_color[2]:02x}"
        detection_type = "advanced" if use_advanced else "simple"
        editor.status_label.config(
            text=f"Auto fill applied: {pixel_count} pixels matched (color: {color_hex}, tolerance: {tolerance}, border: {border_size}px, {detection_type} detection)"
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        editor.status_label.config(text=f"Error in auto fill: {str(e)}")
