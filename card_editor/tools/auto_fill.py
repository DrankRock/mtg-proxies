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

    # Record state before applying auto fill
    if hasattr(editor, "record_state"):
        editor.record_state("Before auto fill text")

    if use_gui:
        # Create the enhanced fill dialog with explicit auto-apply
        def on_apply(description):
            if hasattr(editor, "record_state"):
                editor.record_state(description)

        fill_handler = EnhancedContentAwareFill(editor, editor.selection_coords, on_apply_callback=on_apply)
        # Call the auto_apply_dark_fill method directly
        # We need to wait a bit for the dialog to initialize
        fill_handler.fill_dialog.after(100, fill_handler.auto_apply_dark_fill)
    else:
        # Use the windowless implementation
        apply_auto_dark_fill_windowless(editor)


def apply_auto_dark_fill_windowless(editor, clear_selection=True, iterations=2):
    """
    Apply auto text fill without opening the UI, with automatic text color detection

    Args:
        editor: CardEditor instance
        clear_selection: Whether to clear selection after application
        iterations: Number of times to repeat the process on the same selection (default: 2)
    """
    if not editor.selection_coords:
        return

    # Get the current selection coordinates
    x1, y1, x2, y2 = editor.selection_coords
    print(f"\nDEBUG - Starting apply_auto_dark_fill_windowless with {iterations} iterations")
    print(f"DEBUG - Selection coordinates: ({x1}, {y1}, {x2}, {y2})")

    total_pixels_filled = 0

    # Iterate the specified number of times
    for current_iteration in range(1, iterations + 1):
        print(f"\nDEBUG - Starting iteration {current_iteration} of {iterations}")

        try:
            # Show processing status
            editor.status_label.config(text=f"Applying auto fill (pass {current_iteration}/{iterations})...")

            # Get selection area from the current working image (which may have been modified in previous iterations)
            selection_area = editor.working_image.crop((x1, y1, x2, y2))
            print(f"DEBUG - Selection size: {selection_area.width}x{selection_area.height}")

            # Convert to numpy array for processing
            selection_np = np.array(selection_area)
            print(f"DEBUG - Selection array shape: {selection_np.shape}")

            # AUTOMATIC TEXT COLOR DETECTION
            # First check if the image is RGB/RGBA or grayscale
            if len(selection_np.shape) == 3 and selection_np.shape[2] >= 3:
                # RGB/RGBA image - calculate luminance using only RGB channels
                luminance = (
                    0.299 * selection_np[:, :, 0] + 0.587 * selection_np[:, :, 1] + 0.114 * selection_np[:, :, 2]
                )
            else:
                # Grayscale image
                luminance = selection_np.copy()

            # Calculate histogram of the luminance
            hist, bins = np.histogram(luminance.flatten(), bins=256, range=(0, 256))

            # Calculate median and mean luminance
            median_luminance = np.median(luminance)
            mean_luminance = np.mean(luminance)

            # Perform bi-modal analysis with Otsu's method to find optimal threshold
            otsu_thresh, _ = cv2.threshold(luminance.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Calculate pixel counts below and above threshold
            dark_pixels = np.sum(luminance < otsu_thresh)
            light_pixels = np.sum(luminance >= otsu_thresh)

            # Calculate the ratio of dark to light pixels
            dark_ratio = dark_pixels / (dark_pixels + light_pixels) if (dark_pixels + light_pixels) > 0 else 0

            print(f"DEBUG - Auto-detection stats:")
            print(f"  Otsu threshold: {otsu_thresh}")
            print(f"  Dark pixels: {dark_pixels}, Light pixels: {light_pixels}")
            print(f"  Dark ratio: {dark_ratio:.4f}")
            print(f"  Min luminance: {luminance.min():.2f}, Max luminance: {luminance.max():.2f}")
            print(f"  Mean luminance: {mean_luminance:.2f}, Median luminance: {median_luminance:.2f}")

            # Determine if text is dark or light based on the dark ratio
            # Text typically takes up less area than background
            is_dark_text = dark_ratio < 0.5
            print(f"  Text detected as: {'DARK' if is_dark_text else 'LIGHT'}")

            # Get appropriate target color based on the detection
            if is_dark_text:
                # Text is dark, find darkest point
                if len(selection_np.shape) == 3 and selection_np.shape[2] >= 3:
                    min_y, min_x = np.unravel_index(luminance.argmin(), luminance.shape)
                    target_color = selection_np[min_y, min_x][:3]  # Get only RGB components
                    print(f"  Darkest pixel at ({min_x}, {min_y}) with RGB: {target_color}")
                else:
                    # For grayscale images
                    min_y, min_x = np.unravel_index(selection_np.argmin(), selection_np.shape)
                    dark_value = selection_np[min_y, min_x]
                    target_color = (dark_value, dark_value, dark_value)  # Convert to RGB tuple
                    print(f"  Darkest pixel at ({min_x}, {min_y}) with value: {dark_value}")

                detection_mode = "dark"
            else:
                # Text is light, find lightest point
                if len(selection_np.shape) == 3 and selection_np.shape[2] >= 3:
                    max_y, max_x = np.unravel_index(luminance.argmax(), luminance.shape)
                    target_color = selection_np[max_y, max_x][:3]  # Get only RGB components
                    print(f"  Lightest pixel at ({max_x}, {max_y}) with RGB: {target_color}")
                else:
                    # For grayscale images
                    max_y, max_x = np.unravel_index(selection_np.argmax(), selection_np.shape)
                    light_value = selection_np[max_y, max_x]
                    target_color = (light_value, light_value, light_value)  # Convert to RGB tuple
                    print(f"  Lightest pixel at ({max_x}, {max_y}) with value: {light_value}")

                detection_mode = "light"

            # Extract RGB channels for processing, even if we have RGBA
            if len(selection_np.shape) == 3:
                if selection_np.shape[2] == 4:  # RGBA
                    selection_rgb = selection_np[:, :, :3]  # Take only RGB channels
                    print("DEBUG - Extracted RGB from RGBA for color refinement")
                else:
                    selection_rgb = selection_np  # Already RGB
            else:
                # Convert grayscale to RGB
                selection_rgb = np.stack([selection_np, selection_np, selection_np], axis=2)
                print("DEBUG - Converted grayscale to RGB for color refinement")

            # Refine the color by finding similar colored pixels
            tolerance = editor.fill_tolerance_var.get()

            # Create mask where pixels are within preliminary tolerance of the selected color
            color_diffs = np.sum(np.abs(selection_rgb - np.array(target_color)), axis=2)
            prelim_mask = (color_diffs <= tolerance).astype(np.uint8)

            # If we have very few pixels, gradually increase tolerance
            pixel_count = np.sum(prelim_mask)
            min_pixels = 50  # Minimum number of pixels we want to have

            print(f"  Initial pixel count with tolerance {tolerance}: {pixel_count}")

            temp_tolerance = tolerance
            while pixel_count < min_pixels and temp_tolerance < 200:
                temp_tolerance += 10
                color_diffs = np.sum(np.abs(selection_rgb - np.array(target_color)), axis=2)
                prelim_mask = (color_diffs <= temp_tolerance).astype(np.uint8)
                pixel_count = np.sum(prelim_mask)
                print(f"  Increased tolerance to {temp_tolerance}, new pixel count: {pixel_count}")

            # If we have enough pixels, refine the color by taking the average of similar pixels
            if pixel_count >= min_pixels:
                # Reshape to get all valid pixels
                matching_pixels = selection_rgb[prelim_mask > 0]
                if len(matching_pixels) > 0:
                    refined_color = np.mean(matching_pixels, axis=0)[:3].astype(np.uint8)
                    target_color = tuple(refined_color)
                    print(f"  Refined color to RGB: {target_color}")

            # Get the full image in numpy array format
            img_np = np.array(editor.working_image)

            # Get settings from UI
            tolerance = editor.fill_tolerance_var.get()
            border_size = editor.fill_border_var.get()
            use_advanced = editor.advanced_detection_var.get()
            
            # Get inpainting method - default to "telea" if not defined
            inpainting_method = getattr(editor, "inpainting_method_var", tk.StringVar(value="telea")).get() if hasattr(editor, "inpainting_method_var") else "telea"
            
            # For backward compatibility
            use_patchmatch = hasattr(editor, "use_patchmatch_var") and editor.use_patchmatch_var.get()
            if use_patchmatch and inpainting_method == "telea":
                inpainting_method = "patchmatch"

            print(
                f"DEBUG - Settings: tolerance={tolerance}, border_size={border_size}, use_advanced={use_advanced}, inpainting_method={inpainting_method}"
            )

            # Create mask for inpainting
            mask = np.zeros((editor.working_image.height, editor.working_image.width), dtype=np.uint8)

            if use_advanced:
                print("DEBUG - Using advanced text detection")
                # Advanced text detection approach
                # Extract selection area for processing
                selection_area = img_np[y1:y2, x1:x2]

                # Convert to grayscale for easier processing if it's RGB/RGBA
                if len(selection_area.shape) == 3:
                    if detection_mode == "dark":
                        # For dark text, convert to grayscale directly
                        gray_selection = np.dot(selection_area[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
                        print("DEBUG - Converted RGB to grayscale for dark text")
                    else:  # light mode
                        # Invert to make light text appear dark
                        gray_selection = 255 - np.dot(selection_area[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
                        print("DEBUG - Inverted grayscale for light text")
                else:
                    # Already grayscale
                    gray_selection = selection_area.copy()
                    if detection_mode == "light":
                        gray_selection = 255 - gray_selection  # Invert for light text
                        print("DEBUG - Inverted grayscale for light text (already grayscale)")
                    else:
                        print("DEBUG - Using grayscale (already grayscale)")

                print(
                    f"DEBUG - Grayscale stats: min={gray_selection.min()}, max={gray_selection.max()}, mean={gray_selection.mean():.2f}"
                )

                # Apply adaptive thresholding to better separate text from background
                binary_selection = cv2.adaptiveThreshold(
                    gray_selection,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV,
                    11,  # Block size
                    2,  # Constant subtracted from mean
                )
                print("DEBUG - Applied adaptive thresholding")

                # Apply morphological operations to improve text detection
                # Create a small kernel for thin text
                kernel = np.ones((2, 2), np.uint8)

                # Open operation (erosion followed by dilation) to remove noise
                opened = cv2.morphologyEx(binary_selection, cv2.MORPH_OPEN, kernel)
                print("DEBUG - Applied morphological opening")

                # Additional dilate to ensure thin text is fully covered
                selection_mask = cv2.dilate(opened, kernel, iterations=1)
                print("DEBUG - Applied dilation")

                # Use tolerance as a threshold for final adjustment
                if tolerance > 100:  # If high tolerance, apply additional dilation
                    extra_kernel = np.ones((tolerance // 50 + 1, tolerance // 50 + 1), np.uint8)
                    selection_mask = cv2.dilate(selection_mask, extra_kernel, iterations=1)
                    print(f"DEBUG - Applied additional dilation with kernel size {tolerance // 50 + 1}")

                # Place selection mask into the full mask
                mask[y1:y2, x1:x2] = selection_mask
                print(f"DEBUG - Advanced mask created with {np.sum(selection_mask > 0)} pixels")

            else:
                print("DEBUG - Using simple color-based detection")
                # Simple color-based detection approach
                # Handle different image types
                if len(img_np.shape) == 2:  # Grayscale
                    img_rgb = np.stack([img_np, img_np, img_np], axis=2)
                    print("DEBUG - Converted grayscale to RGB")
                elif len(img_np.shape) == 3:
                    if img_np.shape[2] == 4:  # RGBA
                        img_rgb = img_np[:, :, :3]  # Extract RGB channels
                        print("DEBUG - Extracted RGB from RGBA")
                    elif img_np.shape[2] == 3:  # RGB
                        img_rgb = img_np
                        print("DEBUG - Using RGB image")
                    else:
                        raise ValueError(f"Unexpected image format with {img_np.shape[2]} channels")
                else:
                    raise ValueError(f"Unexpected image shape: {img_np.shape}")

                # Calculate color differences ONLY in the selection area
                # Initialize the color mask with zeros
                color_mask = np.zeros((editor.working_image.height, editor.working_image.width), dtype=np.uint8)

                # Calculate color differences for the selection area
                selection_rgb = img_rgb[y1:y2, x1:x2]

                # Ensure we're only comparing RGB channels
                if len(selection_rgb.shape) == 3 and selection_rgb.shape[2] > 3:
                    selection_rgb = selection_rgb[:, :, :3]  # Use only RGB channels

                # Calculate color differences
                color_diffs = np.sum(np.abs(selection_rgb - np.array(target_color)), axis=2)
                print(
                    f"DEBUG - Color diffs stats: min={color_diffs.min()}, max={color_diffs.max()}, mean={color_diffs.mean():.2f}"
                )

                selection_color_mask = (color_diffs <= tolerance).astype(np.uint8) * 255
                print(f"DEBUG - Simple mask created with {np.sum(selection_color_mask > 0)} pixels")

                # Place the selection color mask into the full mask
                color_mask[y1:y2, x1:x2] = selection_color_mask

                # Set the mask
                mask = color_mask

            # Apply border expansion if needed
            if border_size > 0:
                kernel = np.ones((border_size * 2 + 1, border_size * 2 + 1), np.uint8)
                mask = cv2.dilate(mask, kernel, iterations=1)
                print(f"DEBUG - Applied border expansion with kernel size {border_size * 2 + 1}")

            # Count pixels in mask for feedback
            pixel_count = np.sum(mask > 0)
            total_pixels_filled += pixel_count
            print(f"DEBUG - Final mask has {pixel_count} pixels")

            # Apply inpainting based on selected method
            if inpainting_method == "patchmatch":
                # Use PatchMatch-based inpainting for more seamless results
                patch_size = 7  # Default patch size
                pm_iterations = 10  # Default iterations for PatchMatch

                # Check if we have custom parameters
                if hasattr(editor, "patchmatch_patch_size_var"):
                    patch_size = editor.patchmatch_patch_size_var.get()

                if hasattr(editor, "patchmatch_iterations_var"):
                    pm_iterations = editor.patchmatch_iterations_var.get()

                print(f"DEBUG - Using PatchMatch inpainting with patch_size={patch_size}, iterations={pm_iterations}")
                result_img_array = apply_patchmatch_inpainting(img_np, mask, patch_size, pm_iterations)
                result_img = Image.fromarray(result_img_array)
                fill_method = "PatchMatch"
            elif inpainting_method == "lama":
                # Use LaMa inpainting
                print("DEBUG - Using LaMa inpainting")
                result_img_array = apply_lama_inpainting(img_np, mask)
                result_img = Image.fromarray(result_img_array)
                fill_method = "LaMa"
            elif inpainting_method == "ns":
                # Use OpenCV's Navier-Stokes inpainting
                print("DEBUG - Using OpenCV Navier-Stokes inpainting")
                result_img_array = apply_opencv_ns_inpainting(img_np, mask)
                result_img = Image.fromarray(result_img_array)
                fill_method = "OpenCV NS"
            else:  # Default to "telea"
                # Use OpenCV's Telea inpainting
                print("DEBUG - Using OpenCV Telea inpainting")
                result_img_array = apply_opencv_telea_inpainting(img_np, mask)
                result_img = Image.fromarray(result_img_array)
                fill_method = "OpenCV Telea"

            # Update working image - we'll continue processing with this updated image in the next iteration
            editor.working_image = result_img

            # Only record state once at the end of all iterations
            if current_iteration == iterations and hasattr(editor, "record_state"):
                editor.record_state("Auto fill text")

            # Update UI after each iteration
            editor.update_display()

            # Update status with color info
            color_hex = f"#{target_color[0]:02x}{target_color[1]:02x}{target_color[2]:02x}"
            detection_type = "advanced" if use_advanced else "simple"
            text_type = "dark" if is_dark_text else "light"

            editor.status_label.config(
                text=f"Auto fill pass {current_iteration}/{iterations}: {pixel_count} pixels of {text_type} text matched (color: {color_hex}, method: {fill_method}, tolerance: {tolerance}, border: {border_size}px, {detection_type} detection)"
            )
            print(f"DEBUG - Auto fill iteration {current_iteration} completed successfully")

        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"DEBUG - Error in auto fill iteration {current_iteration}: {str(e)}")
            editor.status_label.config(text=f"Error in auto fill (pass {current_iteration}): {str(e)}")
            break  # Stop processing further iterations if an error occurs

    # Final status update after all iterations
    if iterations > 1:
        text_type = "dark" if is_dark_text else "light"
        detection_type = "advanced" if use_advanced else "simple"
        editor.status_label.config(
            text=f"Auto fill completed: {total_pixels_filled} total pixels of {text_type} text matched over {iterations} passes (method: {fill_method}, tolerance: {tolerance}, border: {border_size}px, {detection_type} detection)"
        )

    # Only clear selection after all iterations are complete
    if clear_selection:
        editor.reset_selection()

    print(f"\nDEBUG - All {iterations} iterations completed")


def apply_patchmatch_inpainting(image_np, mask, patch_size=7, iterations=10):
    """
    Apply PatchMatch-based inpainting to the image using the proper API.

    Args:
        image_np: Numpy array of the image (in RGB format)
        mask: Binary mask where 255 indicates areas to fill (uint8 array)
        patch_size: Size of patches to use for matching (default: 7)
        iterations: Not used by actual API, kept for compatibility

    Returns:
        Numpy array of the filled image
    """
    try:
        print("DEBUG - Attempting to import PyPatchMatch")

        # First try the default import
        try:
            from patchmatch import patch_match

            print("DEBUG - Successfully imported from pypatchmatch")
        except ImportError:
            # Try importing directly from the module file
            print("DEBUG - Trying to import from patch_match")
        print(f"DEBUG - PyPatchMatch imported, using patch_size={patch_size}")

        # PatchMatch requires RGB image
        if len(image_np.shape) == 2:
            # Convert grayscale to RGB
            image_rgb = np.stack([image_np, image_np, image_np], axis=2)
        elif image_np.shape[2] == 4:
            # Take only RGB channels from RGBA
            image_rgb = image_np[:, :, :3]
        else:
            image_rgb = image_np

        # Ensure image is uint8
        if image_rgb.dtype != np.uint8:
            image_rgb = image_rgb.astype(np.uint8)

        # Make sure mask is proper format (uint8, single channel)
        if len(mask.shape) == 3 and mask.shape[2] > 1:
            # Take just one channel
            mask_single = mask[:, :, 0]
        else:
            mask_single = mask

        # Ensure mask is uint8
        if mask_single.dtype != np.uint8:
            mask_single = (mask_single > 0).astype(np.uint8) * 255

        print(f"DEBUG - Image shape: {image_rgb.shape}, Mask shape: {mask_single.shape}")

        # Apply PatchMatch inpainting - using the proper API from the module
        print("DEBUG - Starting PatchMatch inpainting")
        result = patch_match.inpaint(image=image_rgb, mask=mask_single, patch_size=patch_size)
        print("DEBUG - PatchMatch inpainting successful")

        # If original was RGBA, preserve alpha channel
        if len(image_np.shape) == 3 and image_np.shape[2] == 4:
            result_rgba = np.zeros_like(image_np)
            result_rgba[:, :, :3] = result
            result_rgba[:, :, 3] = image_np[:, :, 3]
            return result_rgba

        return result

    except Exception as e:
        print(f"DEBUG - PatchMatch error: {str(e)}")

        # Fall back to OpenCV Telea algorithm
        print("DEBUG - Falling back to OpenCV inpainting (NS method for better quality)")
        img_cv = (
            cv2.cvtColor(image_np[:, :, :3], cv2.COLOR_RGB2BGR)
            if len(image_np.shape) == 3
            else cv2.cvtColor(image_np, cv2.COLOR_GRAY2BGR)
        )

        # Use NS (Navier-Stokes) method instead of Telea for better quality
        result = cv2.inpaint(img_cv, mask, 3, cv2.INPAINT_NS)
        result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)

        # If original was RGBA, preserve alpha channel
        if len(image_np.shape) == 3 and image_np.shape[2] == 4:
            result_rgba = np.zeros_like(image_np)
            result_rgba[:, :, :3] = result_rgb
            result_rgba[:, :, 3] = image_np[:, :, 3]
            return result_rgba

        return result_rgb


def apply_lama_inpainting(image_np, mask):
    """
    Apply LaMa (Large Mask Inpainting) to the image.
    
    Args:
        image_np: Numpy array of the image
        mask: Binary mask where 255 indicates areas to fill (uint8 array)
        
    Returns:
        Numpy array of the filled image
    """
    try:
        from simple_lama_inpainting import SimpleLama
        from PIL import Image as PILImage
        
        print("DEBUG - Using LaMa inpainting")
        
        # Convert numpy array to PIL Image
        if len(image_np.shape) == 3 and image_np.shape[2] == 4:
            # RGBA image
            image_pil = PILImage.fromarray(image_np)
        elif len(image_np.shape) == 3 and image_np.shape[2] == 3:
            # RGB image
            image_pil = PILImage.fromarray(image_np)
        else:
            # Grayscale image - convert to RGB
            if len(image_np.shape) == 2:
                rgb_array = np.stack([image_np] * 3, axis=2)
                image_pil = PILImage.fromarray(rgb_array.astype(np.uint8))
            else:
                image_pil = PILImage.fromarray(image_np)
            
        # Convert mask to PIL Image
        # LaMa expects a binary mask where white (255) indicates areas to fill
        mask_pil = PILImage.fromarray(mask).convert('L')
        
        print(f"DEBUG - Image for LaMa: {image_pil.mode}, {image_pil.size}")
        print(f"DEBUG - Mask for LaMa: {mask_pil.mode}, {mask_pil.size}, min={np.min(mask)}, max={np.max(mask)}")
        
        # Initialize LaMa model
        simple_lama = SimpleLama()
        
        # Apply inpainting
        result_pil = simple_lama(image_pil, mask_pil)
        
        # Convert back to numpy array
        result_np = np.array(result_pil)
        
        # If original was RGBA, preserve alpha channel
        if len(image_np.shape) == 3 and image_np.shape[2] == 4:
            result_rgba = np.zeros_like(image_np)
            result_rgba[:, :, :3] = result_np[:, :, :3]  # Assuming result_np is RGB
            result_rgba[:, :, 3] = image_np[:, :, 3]     # Alpha from original
            return result_rgba
            
        return result_np
        
    except Exception as e:
        print(f"DEBUG - LaMa inpainting error: {str(e)}")
        
        # Fall back to OpenCV Telea algorithm
        print("DEBUG - Falling back to OpenCV inpainting (Telea method)")
        return apply_opencv_telea_inpainting(image_np, mask)


def apply_opencv_telea_inpainting(image_np, mask):
    """
    Apply OpenCV's Telea inpainting algorithm to the image.
    
    Args:
        image_np: Numpy array of the image
        mask: Binary mask where 255 indicates areas to fill (uint8 array)
        
    Returns:
        Numpy array of the filled image
    """
    print("DEBUG - Using OpenCV Telea inpainting")
    
    # Convert to BGR format for OpenCV
    if len(image_np.shape) == 3 and image_np.shape[2] == 4:
        img_cv = cv2.cvtColor(image_np[:, :, :3], cv2.COLOR_RGB2BGR)  # RGBA to BGR
    elif len(image_np.shape) == 3 and image_np.shape[2] == 3:
        img_cv = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)  # RGB to BGR
    else:
        img_cv = cv2.cvtColor(image_np, cv2.COLOR_GRAY2BGR)  # Grayscale to BGR
        
    # Apply inpainting
    result = cv2.inpaint(img_cv, mask, 5, cv2.INPAINT_TELEA)
    
    # Convert back to RGB
    result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    
    # If original was RGBA, preserve alpha channel
    if len(image_np.shape) == 3 and image_np.shape[2] == 4:
        result_rgba = np.zeros_like(image_np)
        result_rgba[:, :, :3] = result_rgb
        result_rgba[:, :, 3] = image_np[:, :, 3]
        return result_rgba
        
    return result_rgb


def apply_opencv_ns_inpainting(image_np, mask):
    """
    Apply OpenCV's Navier-Stokes inpainting algorithm to the image.
    
    Args:
        image_np: Numpy array of the image
        mask: Binary mask where 255 indicates areas to fill (uint8 array)
        
    Returns:
        Numpy array of the filled image
    """
    print("DEBUG - Using OpenCV Navier-Stokes inpainting")
    
    # Convert to BGR format for OpenCV
    if len(image_np.shape) == 3 and image_np.shape[2] == 4:
        img_cv = cv2.cvtColor(image_np[:, :, :3], cv2.COLOR_RGB2BGR)  # RGBA to BGR
    elif len(image_np.shape) == 3 and image_np.shape[2] == 3:
        img_cv = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)  # RGB to BGR
    else:
        img_cv = cv2.cvtColor(image_np, cv2.COLOR_GRAY2BGR)  # Grayscale to BGR
        
    # Apply inpainting with Navier-Stokes method
    result = cv2.inpaint(img_cv, mask, 3, cv2.INPAINT_NS)
    
    # Convert back to RGB
    result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    
    # If original was RGBA, preserve alpha channel
    if len(image_np.shape) == 3 and image_np.shape[2] == 4:
        result_rgba = np.zeros_like(image_np)
        result_rgba[:, :, :3] = result_rgb
        result_rgba[:, :, 3] = image_np[:, :, 3]
        return result_rgba
        
    return result_rgb