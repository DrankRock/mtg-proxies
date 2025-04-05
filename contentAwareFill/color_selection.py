"""Color-based selection functionality for Enhanced Content-Aware Fill"""

import threading
import tkinter as tk
from tkinter import ttk

import cv2
import numpy as np
from PIL import Image, ImageTk


class ColorSelectionMixin:
    """Mixin class for color-based selection functionality"""

    def setup_color_selection_ui(self):
        """Add color selection UI elements to the dialog"""
        # Add a new section for color-based selection in the settings frame
        self.color_selection_frame = ttk.LabelFrame(self.settings_frame, text="Color-Based Selection", padding=10)
        # Insert after algorithm selection but before color settings
        self.color_selection_frame.grid(row=1, column=0, sticky="ew", pady=10)

        # Color selection button
        selection_btn_frame = ttk.Frame(self.color_selection_frame)
        selection_btn_frame.pack(fill="x", pady=5)

        self.color_selection_active = False
        self.selection_color_var = tk.StringVar(value="#ffffff")

        ttk.Label(selection_btn_frame, text="Select by Color:").pack(side=tk.LEFT, padx=(0, 5))

        self.selection_color_button = tk.Button(selection_btn_frame, bg=self.selection_color_var.get(), width=3)
        self.selection_color_button.pack(side=tk.LEFT, padx=5)

        # Eyedropper button for selection color
        self.color_selection_btn = ttk.Button(
            selection_btn_frame, text="🔍", width=3, command=self.activate_color_selection
        )
        self.color_selection_btn.pack(side=tk.LEFT, padx=5)

        # Make clicking on the color button also trigger the eyedropper
        self.selection_color_button.config(command=self.activate_color_selection)

        ttk.Label(selection_btn_frame, text="Click to select areas by color").pack(side=tk.LEFT, padx=5)

        # Tolerance slider
        tolerance_frame = ttk.Frame(self.color_selection_frame)
        tolerance_frame.pack(fill="x", pady=5)

        self.tolerance_var = tk.IntVar(value=10)
        ttk.Label(tolerance_frame, text="Color Tolerance:").pack(side=tk.LEFT, padx=(0, 5))

        # Create scale with integer steps
        tolerance_scale = ttk.Scale(
            tolerance_frame,
            from_=1,
            to=255,
            variable=self.tolerance_var,
            orient="horizontal",
            command=lambda val: self.on_slider_change(val, self.tolerance_var),
        )
        tolerance_scale.pack(side=tk.LEFT, fill="x", expand=True)

        self.tolerance_label = ttk.Label(tolerance_frame, text="10")
        self.tolerance_label.pack(side=tk.LEFT, padx=5)

        # Border size slider
        border_frame = ttk.Frame(self.color_selection_frame)
        border_frame.pack(fill="x", pady=5)

        self.border_size_var = tk.IntVar(value=1)
        ttk.Label(border_frame, text="Border Size:").pack(side=tk.LEFT, padx=(0, 5))

        border_scale = ttk.Scale(
            border_frame,
            from_=0,
            to=10,
            variable=self.border_size_var,
            orient="horizontal",
            command=lambda val: self.on_slider_change(val, self.border_size_var),
        )
        border_scale.pack(side=tk.LEFT, fill="x", expand=True)

        self.border_label = ttk.Label(border_frame, text="1")
        self.border_label.pack(side=tk.LEFT, padx=5)

        # Apply button
        apply_frame = ttk.Frame(self.color_selection_frame)
        apply_frame.pack(fill="x", pady=5)

        self.apply_selection_btn = ttk.Button(
            apply_frame, text="Apply Color Selection", command=self.apply_color_selection
        )
        self.apply_selection_btn.pack(side=tk.LEFT, padx=5)

        self.reset_selection_btn = ttk.Button(apply_frame, text="Reset Selection", command=self.reset_color_selection)
        self.reset_selection_btn.pack(side=tk.LEFT, padx=5)

        # Store original selection
        self.original_selection_coords = self.selection_coords
        self.color_mask = None
        self.selection_preview_timer = None

    # Modify the update_selection_preview method to work with zoom:
    def update_selection_preview(self, preview_img, crop_coords=None):
        """Update the preview with the color-based selection overlay

        Args:
            preview_img: PIL Image with the preview
            crop_coords: List of [x1, y1, x2, y2] coordinates of the crop
        """
        self.status_label.config(text="Color selection preview ready")

        # Store the crop coordinates if provided
        if crop_coords:
            self.preview_crop_coords = crop_coords

        # Update the preview if available
        if self.preview_var.get() and hasattr(self, "preview_canvas"):
            # Scale the preview to fit the canvas
            preview_width = self.preview_canvas.winfo_width() - 10
            if preview_width < 100:  # If canvas not yet sized, use a default
                preview_width = 300

            # Calculate aspect ratio and preview size
            aspect_ratio = preview_img.height / preview_img.width
            preview_height = int(preview_width * aspect_ratio)

            # Resize for preview
            preview_img_resized = preview_img.resize((preview_width, preview_height), Image.LANCZOS)

            # Create image for canvas
            self.selection_preview_photo = ImageTk.PhotoImage(preview_img_resized)

            # Update canvas
            self.preview_canvas.delete("all")

            # Configure canvas scrollregion for the zoomed image
            zoomed_width = int(self.selection_preview_photo.width() * self.zoom_level)
            zoomed_height = int(self.selection_preview_photo.height() * self.zoom_level)
            self.preview_canvas.config(scrollregion=(0, 0, zoomed_width, zoomed_height))

            # Draw the image with a tag for scaling
            self.image_item = self.preview_canvas.create_image(
                0, 0, anchor="nw", image=self.selection_preview_photo, tags=("preview_image",)
            )

            # Scale the image if zoomed
            if self.zoom_level != 1.0:
                self.preview_canvas.scale("preview_image", 0, 0, self.zoom_level, self.zoom_level)

            self.preview_status.config(
                text=f"Selection preview - apply to confirm (Zoom: {int(self.zoom_level * 100)}%)"
            )

            # Store this preview for color picking
            self.before_preview = preview_img

    def apply_color_selection(self):
        """Apply the color-based selection to update the selection coordinates"""
        if not hasattr(self, "color_mask") or self.color_mask is None:
            self.status_label.config(text="No color selection to apply. Pick a color first.")
            return

        # Get the original selection coordinates
        orig_x1, orig_y1, orig_x2, orig_y2 = self.selection_coords

        # Find the bounding rectangle of the mask within the current selection
        y_indices, x_indices = np.where(self.color_mask > 0)

        if len(y_indices) == 0 or len(x_indices) == 0:
            self.status_label.config(text="No pixels selected with current settings. Try increasing tolerance.")
            return

        # We don't need to update the selection coordinates, since we're using the mask
        # to determine what gets filled, not creating a new rectangular selection

        # Store the color mask for use during inpainting
        self.use_color_mask = True

        # Display the number of pixels selected and the percentage of the original selection
        pixel_count = np.sum(self.color_mask > 0)
        original_area = (orig_x2 - orig_x1) * (orig_y2 - orig_y1)
        percentage = (pixel_count / original_area) * 100 if original_area > 0 else 0

        self.status_label.config(text=f"Color selection applied: {pixel_count} pixels ({percentage:.1f}% of selection)")

        # Update the preview if preview is enabled
        if hasattr(self, "preview_var") and self.preview_var.get():
            self.update_preview()

    def reset_color_selection(self):
        """Reset to the original rectangular selection"""
        if hasattr(self, "original_selection_coords"):
            # Store the original coordinates
            self.selection_coords = self.original_selection_coords

            # Clear the color mask
            self.color_mask = None
            self.use_color_mask = False

            self.status_label.config(text="Selection reset to original rectangle")

            # Update the preview if enabled
            if hasattr(self, "preview_var") and self.preview_var.get():
                self.update_preview()

    def apply_opencv_inpainting_with_color_mask(self, image, preview=False):
        """Apply OpenCV inpainting algorithm with color-based mask

        Args:
            image: PIL Image to process
            preview: Whether this is for preview (lower quality for speed)

        Returns:
            PIL Image with inpainting applied
        """
        # Convert PIL image to OpenCV format
        img_cv = np.array(image)
        # Convert RGB to BGR (OpenCV uses BGR)
        img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2BGR)

        # Get selection coordinates
        x1, y1, x2, y2 = self.selection_coords

        # Ensure coordinates are within bounds
        x1 = max(0, min(x1, image.width - 1))
        y1 = max(0, min(y1, image.height - 1))
        x2 = max(0, min(x2, image.width))
        y2 = max(0, min(y2, image.height))

        # Create mask for inpainting
        if hasattr(self, "use_color_mask") and self.use_color_mask and self.color_mask is not None:
            # Use the color-based mask directly
            mask = self.color_mask
        else:
            # Use the traditional rectangular mask
            mask = np.zeros((image.height, image.width), dtype=np.uint8)
            mask[y1:y2, x1:x2] = 255

        # If feathering is enabled, create a soft mask
        feather = self.feather_edge_var.get()
        if feather > 0:
            # Apply blur to create feathered edges
            mask = cv2.GaussianBlur(mask, (feather * 2 + 1, feather * 2 + 1), 0)

        # Get inpainting radius
        inpaint_radius = self.radius_var.get()

        # Apply appropriate inpainting algorithm
        if self.algorithm_var.get() == "opencv_telea":
            result = cv2.inpaint(img_cv, mask, inpaint_radius, cv2.INPAINT_TELEA)
        else:  # opencv_ns
            result = cv2.inpaint(img_cv, mask, inpaint_radius, cv2.INPAINT_NS)

        # Convert back to RGB and PIL format
        result_rgb = cv2.cvtColor(result.astype(np.uint8), cv2.COLOR_BGR2RGB)
        return Image.fromarray(result_rgb)

    def on_slider_change(self, value, var):
        """Handle slider changes with debounce and integer-only values"""
        # Convert to integer
        int_value = int(float(value))
        var.set(int_value)

        # Update label
        if var == self.tolerance_var:
            self.tolerance_label.config(text=str(int_value))
        elif var == self.border_size_var:
            self.border_label.config(text=str(int_value))

        # Update preview if we have a color selected
        if hasattr(self, "selected_color"):
            # Cancel previous timer if exists
            if hasattr(self, "selection_preview_timer") and self.selection_preview_timer:
                self.fill_dialog.after_cancel(self.selection_preview_timer)

            # Set a new timer
            self.selection_preview_timer = self.fill_dialog.after(300, self.preview_color_selection)

    # Modify activate_color_selection method in ColorSelectionMixin
    def activate_color_selection(self):
        """Activate the color selection tool within the preview image"""
        if self.color_selection_active:
            return

        # Ensure we have a preview first
        if not hasattr(self, "preview_canvas") or not self.preview_canvas.winfo_exists():
            self.status_label.config(text="Preview not available. Enable preview first.")
            return

        # Force preview update if not already showing
        if not self.preview_var.get():
            self.preview_var.set(True)
            self.toggle_preview()

        # Set the flag to indicate eyedropper is active
        self.color_selection_active = True

        # Change cursor and show instruction
        self.fill_dialog.grab_release()  # Allow interaction with dialog elements
        self.preview_canvas.config(cursor="crosshair")
        self.status_label.config(text="Click on preview image to select color for masking (showing original image)")

        # If we have toggle_eyedropper_mode function, call it to disable panning
        if hasattr(self, "toggle_eyedropper_mode"):
            self.toggle_eyedropper_mode(True)

        # Store original bindings
        try:
            self.original_preview_click = self.preview_canvas.bind("<Button-1>")
        except:
            # If there's no binding yet
            self.original_preview_click = ""

        # Temporarily show the original image for color selection
        if hasattr(self, "image_item") and hasattr(self, "before_photo"):
            self.preview_canvas.itemconfig(self.image_item, image=self.before_photo)

        # Create new binding for color picking
        def pick_selection_color(event):
            if not self.color_selection_active:
                return

            try:
                # Get the current preview image - use original image
                if not hasattr(self, "before_preview") or self.before_preview is None:
                    self.status_label.config(text="Original image not available")
                    return

                # Get coordinates within the preview
                # Need to account for canvas scrolling and zooming
                canvas_x = self.preview_canvas.canvasx(event.x)
                canvas_y = self.preview_canvas.canvasy(event.y)

                # Apply inverse zoom to get the actual image coordinates
                preview_x = int(canvas_x / self.zoom_level)
                preview_y = int(canvas_y / self.zoom_level)

                # Check if within preview bounds
                if 0 <= preview_x < self.before_preview.width and 0 <= preview_y < self.before_preview.height:
                    # Get original image coordinates (map from preview to original)
                    x1, y1, x2, y2 = self.selection_coords

                    # Calculate proportion within preview
                    prop_x = preview_x / self.before_preview.width
                    prop_y = preview_y / self.before_preview.height

                    # Map to position within the selection in the original image
                    orig_x = int(x1 + prop_x * (x2 - x1))
                    orig_y = int(y1 + prop_y * (y2 - y1))

                    # Get color from ORIGINAL image, not the filled one
                    orig_rgb = self.editor.working_image.getpixel((orig_x, orig_y))

                    # Ensure we have RGB values
                    if isinstance(orig_rgb, tuple) and len(orig_rgb) >= 3:
                        rgb = orig_rgb[:3]
                    else:
                        # Handle grayscale images
                        rgb = (orig_rgb, orig_rgb, orig_rgb)

                    # Format as hex
                    hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

                    # Update UI
                    self.selection_color_var.set(hex_color)
                    self.selection_color_button.config(bg=hex_color)

                    # Store selected color for mask creation
                    self.selected_color = rgb
                    self.selected_point = (orig_x, orig_y)

                    # Reset cursor and bindings
                    self.preview_canvas.config(cursor="")
                    self.color_selection_active = False

                    # Re-enable panning
                    if hasattr(self, "toggle_eyedropper_mode"):
                        self.toggle_eyedropper_mode(False)

                    # Restore original binding if it exists
                    if self.original_preview_click:
                        self.preview_canvas.bind("<Button-1>", self.original_preview_click)

                    # Restore the after image display if appropriate
                    if not getattr(self, "is_hovering", False):
                        if hasattr(self, "image_item") and hasattr(self, "preview_photo"):
                            self.preview_canvas.itemconfig(self.image_item, image=self.preview_photo)

                    self.status_label.config(text="Color selected for masking")

                    # Show a preview of what will be selected
                    self.preview_color_selection()
            except Exception as e:
                import traceback

                traceback.print_exc()
                self.status_label.config(text=f"Error selecting color: {str(e)}")
                self.color_selection_active = False

                # Re-enable panning on error
                if hasattr(self, "toggle_eyedropper_mode"):
                    self.toggle_eyedropper_mode(False)

                # Restore the after image display
                if not getattr(self, "is_hovering", False):
                    if hasattr(self, "image_item") and hasattr(self, "preview_photo"):
                        self.preview_canvas.itemconfig(self.image_item, image=self.preview_photo)

        # Set temporary binding
        self.preview_canvas.bind("<Button-1>", pick_selection_color)

    def preview_color_selection(self):
        """Generate a preview of the color-based selection"""
        if not hasattr(self, "selected_color"):
            self.status_label.config(text="Please select a color first")
            return

        # Show processing state
        self.status_label.config(text="Processing color selection...")
        self.progress.start(10)

        # Process in a separate thread
        def process_preview():
            try:
                # Create a color mask based on the selected color and tolerance
                img_np = np.array(self.editor.working_image)

                # Get the current selection coordinates
                x1, y1, x2, y2 = self.selection_coords

                # Ensure coordinates are within bounds
                x1 = max(0, min(x1, img_np.shape[1] - 1))
                y1 = max(0, min(y1, img_np.shape[0] - 1))
                x2 = max(0, min(x2, img_np.shape[1]))
                y2 = max(0, min(y2, img_np.shape[0]))

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
                tolerance = self.tolerance_var.get()

                # Create mask where pixels are within tolerance
                color_diffs = np.sum(np.abs(img_rgb - np.array(self.selected_color)), axis=2)
                color_mask = (color_diffs <= tolerance).astype(np.uint8) * 255

                # Intersect the color mask with the base mask to restrict to current selection
                mask = cv2.bitwise_and(color_mask, base_mask)

                # Apply border expansion if needed
                border_size = self.border_size_var.get()
                if border_size > 0:
                    kernel = np.ones((border_size * 2 + 1, border_size * 2 + 1), np.uint8)
                    expanded_mask = cv2.dilate(mask, kernel, iterations=1)
                    # Re-intersect with the base mask to ensure we don't expand outside the selection
                    mask = cv2.bitwise_and(expanded_mask, base_mask)

                # Store the mask for later use
                self.color_mask = mask

                # Create a preview overlay
                overlay = np.zeros_like(img_np)

                # Color the overlay (semi-transparent blue)
                if len(overlay.shape) == 3:
                    if overlay.shape[2] == 4:  # RGBA
                        overlay[mask > 0] = [64, 64, 255, 128]  # Blue with alpha
                    else:  # RGB
                        overlay[mask > 0] = [64, 64, 255]  # Blue
                else:  # Grayscale
                    overlay[mask > 0] = 200  # Light gray

                # Combine with original image for preview
                alpha = 0.5
                preview = img_np.copy()

                # Create appropriate mask for the blend
                if len(preview.shape) == 3:
                    if preview.shape[2] == 4:  # RGBA
                        mask_nd = np.stack([mask, mask, mask, mask], axis=2)
                    else:  # RGB
                        mask_nd = np.stack([mask, mask, mask], axis=2)
                else:  # Grayscale
                    mask_nd = mask

                # Use OpenCV's addWeighted for blending where the mask is active
                if len(preview.shape) == 3:
                    # For color images
                    preview_blend = cv2.addWeighted(
                        preview.astype(np.float32), 1 - alpha, overlay.astype(np.float32), alpha, 0
                    ).astype(np.uint8)
                    preview = np.where(mask_nd > 0, preview_blend, preview)
                else:
                    # For grayscale images
                    preview_float = preview.astype(np.float32)
                    overlay_float = overlay.astype(np.float32)
                    preview = np.where(
                        mask > 0, ((1 - alpha) * preview_float + alpha * overlay_float).astype(np.uint8), preview
                    )

                # Crop preview to just show the current selection area
                selection_preview = preview[y1:y2, x1:x2]

                # Convert back to PIL for display
                preview_img = Image.fromarray(selection_preview)

                # Update the preview in the main thread
                self.fill_dialog.after(0, lambda: self.update_selection_preview(preview_img, [x1, y1, x2, y2]))

            except Exception as e:
                import traceback

                traceback.print_exc()
                self.fill_dialog.after(0, lambda: self.status_label.config(text=f"Error: {str(e)}"))
            finally:
                self.fill_dialog.after(0, self.progress.stop)

        # Start the processing thread
        thread = threading.Thread(target=process_preview)
        thread.daemon = True
        thread.start()
