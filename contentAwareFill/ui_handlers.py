"""UI handler methods for the Enhanced Content-Aware Fill dialog"""

import threading
import tkinter as tk
from tkinter import colorchooser, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk


class UIHandlersMixin:
    """Mixin class for UI handling methods"""

    def update_ui_for_algorithm(self):
        """Update UI elements based on selected algorithm"""
        # Clear the algorithm settings frame
        for widget in self.algorithm_settings_frame.winfo_children():
            widget.destroy()

        algorithm = self.algorithm_var.get()

        if algorithm == "none":
            # No settings needed for "None" option
            ttk.Label(
                self.algorithm_settings_frame,
                text="No algorithm selected - original image will be displayed",
                foreground="blue",
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=5)

        elif algorithm in ["opencv_telea", "opencv_ns"]:
            # OpenCV settings
            ttk.Label(self.algorithm_settings_frame, text="Inpainting Radius:").grid(
                row=0, column=0, sticky="w", pady=5
            )

            radius_frame = ttk.Frame(self.algorithm_settings_frame)
            radius_frame.grid(row=0, column=1, sticky="w", pady=5)

            radius_scale = ttk.Scale(radius_frame, from_=1, to=20, variable=self.radius_var, orient="horizontal")
            radius_scale.pack(side=tk.LEFT, fill="x", expand=True)

            radius_label = ttk.Label(radius_frame, textvariable=self.radius_var)
            radius_label.pack(side=tk.LEFT, padx=5)

            # Edge feathering
            ttk.Label(self.algorithm_settings_frame, text="Edge Feathering:").grid(row=1, column=0, sticky="w", pady=5)

            feather_frame = ttk.Frame(self.algorithm_settings_frame)
            feather_frame.grid(row=1, column=1, sticky="w", pady=5)

            feather_scale = ttk.Scale(
                feather_frame, from_=0, to=10, variable=self.feather_edge_var, orient="horizontal"
            )
            feather_scale.pack(side=tk.LEFT, fill="x", expand=True)

            feather_label = ttk.Label(feather_frame, textvariable=self.feather_edge_var)
            feather_label.pack(side=tk.LEFT, padx=5)

            ttk.Label(
                self.algorithm_settings_frame,
                text="Feathering creates a gradual transition at the selection edges",
                foreground="gray",
            ).grid(row=2, column=0, columnspan=2, sticky="w")

        elif algorithm == "patch_based":
            # Patch-based settings
            ttk.Label(self.algorithm_settings_frame, text="Patch Size:").grid(row=0, column=0, sticky="w", pady=5)

            patch_frame = ttk.Frame(self.algorithm_settings_frame)
            patch_frame.grid(row=0, column=1, sticky="w", pady=5)

            patch_scale = ttk.Scale(patch_frame, from_=3, to=15, variable=self.patch_size_var, orient="horizontal")
            patch_scale.pack(side=tk.LEFT, fill="x", expand=True)

            patch_label = ttk.Label(patch_frame, textvariable=self.patch_size_var)
            patch_label.pack(side=tk.LEFT, padx=5)

            # Search area
            ttk.Label(self.algorithm_settings_frame, text="Search Area:").grid(row=1, column=0, sticky="w", pady=5)

            search_frame = ttk.Frame(self.algorithm_settings_frame)
            search_frame.grid(row=1, column=1, sticky="w", pady=5)

            search_scale = ttk.Scale(search_frame, from_=5, to=50, variable=self.search_area_var, orient="horizontal")
            search_scale.pack(side=tk.LEFT, fill="x", expand=True)

            search_label = ttk.Label(search_frame, textvariable=self.search_area_var)
            search_label.pack(side=tk.LEFT, padx=5)

            ttk.Label(
                self.algorithm_settings_frame,
                text="Larger search area may give better results but is slower",
                foreground="gray",
            ).grid(row=2, column=0, columnspan=2, sticky="w")

        elif algorithm == "lama_pytorch":
            # LaMa (PyTorch) settings
            if not self.check_module_available("torch"):
                ttk.Label(
                    self.algorithm_settings_frame,
                    text="PyTorch not installed. Install with:\npip install torch torchvision",
                    foreground="red",
                ).grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
            else:
                ttk.Label(
                    self.algorithm_settings_frame, text="First use will download the model (~100 MB)", foreground="blue"
                ).grid(row=0, column=0, columnspan=2, sticky="w", pady=5)

                # Edge feathering
                ttk.Label(self.algorithm_settings_frame, text="Edge Feathering:").grid(
                    row=1, column=0, sticky="w", pady=5
                )

                feather_frame = ttk.Frame(self.algorithm_settings_frame)
                feather_frame.grid(row=1, column=1, sticky="w", pady=5)

                feather_scale = ttk.Scale(
                    feather_frame, from_=0, to=10, variable=self.feather_edge_var, orient="horizontal"
                )
                feather_scale.pack(side=tk.LEFT, fill="x", expand=True)

                feather_label = ttk.Label(feather_frame, textvariable=self.feather_edge_var)
                feather_label.pack(side=tk.LEFT, padx=5)

        elif algorithm == "deepfill_tf":
            # DeepFill (TensorFlow) settings
            if not self.check_module_available("tensorflow"):
                ttk.Label(
                    self.algorithm_settings_frame,
                    text="TensorFlow not installed. Install with:\npip install tensorflow",
                    foreground="red",
                ).grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
            else:
                ttk.Label(
                    self.algorithm_settings_frame, text="First use will download the model (~30 MB)", foreground="blue"
                ).grid(row=0, column=0, columnspan=2, sticky="w", pady=5)

                # Edge feathering
                ttk.Label(self.algorithm_settings_frame, text="Edge Feathering:").grid(
                    row=1, column=0, sticky="w", pady=5
                )

                feather_frame = ttk.Frame(self.algorithm_settings_frame)
                feather_frame.grid(row=1, column=1, sticky="w", pady=5)

                feather_scale = ttk.Scale(
                    feather_frame, from_=0, to=10, variable=self.feather_edge_var, orient="horizontal"
                )
                feather_scale.pack(side=tk.LEFT, fill="x", expand=True)

                feather_label = ttk.Label(feather_frame, textvariable=self.feather_edge_var)
                feather_label.pack(side=tk.LEFT, padx=5)

        # Update the preview if enabled
        if self.preview_var.get():
            self.update_preview()

    def update_influence_label(self, *args):
        """Update the influence percentage label"""
        self.influence_label.config(text=f"{int(self.influence_var.get() * 100)}%")

    def pick_color(self):
        """Open color picker dialog"""
        color = colorchooser.askcolor(self.color_var.get())[1]
        if color:
            self.color_var.set(color)
            self.color_button.config(bg=color)
            if self.preview_var.get():
                self.update_preview()

    def activate_eyedropper(self):
        """Activate the eyedropper tool to pick a color from the image"""
        self.eyedropper_active = True
        self.fill_dialog.grab_release()  # Allow interaction with main window
        self.editor.canvas.config(cursor="crosshair")
        self.editor.status_label.config(text="Click on image to sample color")

        # If we have toggle_eyedropper_mode function, call it
        if hasattr(self, "toggle_eyedropper_mode"):
            self.toggle_eyedropper_mode(True)

        # Store original bindings
        self.original_click = self.editor.canvas.bind("<Button-1>")

        # Create new binding for color picking
        def pick_color_from_image(event):
            if not self.eyedropper_active:
                return

            # Calculate image coordinates from canvas coordinates
            canvas_x = self.editor.canvas.canvasx(event.x)
            canvas_y = self.editor.canvas.canvasy(event.y)
            image_x = int(canvas_x / self.editor.zoom_factor)
            image_y = int(canvas_y / self.editor.zoom_factor)

            # Check if within image bounds
            if 0 <= image_x < self.editor.img_width and 0 <= image_y < self.editor.img_height:
                # Get color at this position
                try:
                    rgb = self.editor.working_image.getpixel((image_x, image_y))[:3]
                    hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
                    self.color_var.set(hex_color)
                    self.color_button.config(bg=hex_color)

                    # Reset cursor and bindings
                    self.editor.canvas.config(cursor="")
                    self.eyedropper_active = False
                    self.fill_dialog.grab_set()  # Restore dialog as modal
                    self.editor.status_label.config(text="Color sampled")

                    # If we have toggle_eyedropper_mode function, call it
                    if hasattr(self, "toggle_eyedropper_mode"):
                        self.toggle_eyedropper_mode(False)

                    # Restore original binding
                    self.editor.canvas.bind("<Button-1>", self.original_click)

                    # Update preview
                    if self.preview_var.get():
                        self.update_preview()
                except Exception as e:
                    print(f"Error sampling color: {e}")

        # Set temporary binding
        self.editor.canvas.bind("<Button-1>", pick_color_from_image)

    def toggle_preview(self):
        """Toggle the preview on/off"""
        if self.preview_var.get():
            self.update_preview()
        else:
            # Clear preview
            self.preview_canvas.delete("all")
            self.preview_status.config(text="Preview disabled")

    def update_preview(self):
        """Update the preview with the current settings"""
        if self.is_processing:
            return

        self.is_processing = True
        self.progress.start(10)
        self.status_label.config(text="Processing...")
        self.preview_status.config(text="Generating preview...")

        # Create a thread for processing to avoid freezing UI
        self.process_thread = threading.Thread(target=self.process_preview)
        self.process_thread.daemon = True
        self.process_thread.start()

    def process_preview(self):
        try:
            # Get a copy of the working image
            img_copy = self.editor.working_image.copy()
            algorithm = self.algorithm_var.get()

            # Get selection coordinates
            x1, y1, x2, y2 = self.selection_coords

            # Create a before/after comparison image
            # Make a copy of the original for the "before" part
            before_img = img_copy.copy()

            # Apply the selected algorithm to get "after" preview
            if algorithm == "none":
                # For "None" option, use the original image as the "after" image as well
                after_img = before_img.copy()
            elif algorithm in ["opencv_telea", "opencv_ns"]:
                after_img = self.apply_opencv_inpainting(img_copy, preview=True)
            elif algorithm == "patch_based":
                after_img = self.apply_patch_based(img_copy, preview=True)
            elif algorithm == "lama_pytorch":
                after_img = self.apply_lama_pytorch(img_copy, preview=True)
            elif algorithm == "deepfill_tf":
                after_img = self.apply_deepfill_tf(img_copy, preview=True)
            else:
                after_img = img_copy.copy()  # Default fallback

            # Get color influence if set - only apply if we're not using "none" algorithm
            influence = self.influence_var.get()
            if influence > 0 and algorithm != "none":
                after_img = self.apply_color_influence(after_img, preview=True)

            # Create side-by-side preview
            # For preview, crop to the selection area plus some margin
            margin = 50  # pixels around the selection
            crop_x1 = max(0, x1 - margin)
            crop_y1 = max(0, y1 - margin)
            crop_x2 = min(img_copy.width, x2 + margin)
            crop_y2 = min(img_copy.height, y2 + margin)

            # Crop both images to the same region
            before_crop = before_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
            after_crop = after_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))

            # Create preview image (scaled down if needed)
            preview_width = self.preview_canvas.winfo_width() - 10
            if preview_width < 100:  # If canvas not yet sized, use a default
                preview_width = 300

            # Calculate aspect ratio and preview size
            aspect_ratio = before_crop.height / before_crop.width
            preview_height = int(preview_width * aspect_ratio)

            # Resize for preview
            before_preview = before_crop.resize((preview_width, preview_height), Image.LANCZOS)
            after_preview = after_crop.resize((preview_width, preview_height), Image.LANCZOS)

            # Store both images for the split preview
            self.before_preview = before_preview
            self.after_preview = after_preview

            # For "none" algorithm, both before and after are the same
            if algorithm == "none":
                # Use same image for both
                self.preview_photo = ImageTk.PhotoImage(before_preview)
                self.before_photo = ImageTk.PhotoImage(before_preview)
            else:
                # Create initial display with "after" result for other algorithms
                self.preview_photo = ImageTk.PhotoImage(after_preview)
                self.before_photo = ImageTk.PhotoImage(before_preview)

            # Update UI in main thread
            self.fill_dialog.after(0, self.update_preview_canvas)
        except Exception as e:
            print(f"Preview error: {e}")
            self.fill_dialog.after(0, lambda: self.preview_status.config(text=f"Preview error: {str(e)}"))
        finally:
            self.is_processing = False
            self.fill_dialog.after(0, self.progress.stop)

    def update_preview_canvas(self):
        """Update the preview canvas with the processed image"""
        if self.preview_photo and self.before_photo:
            self.preview_canvas.delete("all")

            # Apply zoom factor to determine display dimensions
            zoomed_width = int(self.preview_photo.width() * self.zoom_level)
            zoomed_height = int(self.preview_photo.height() * self.zoom_level)

            # Configure canvas scrollregion for the zoomed image
            self.preview_canvas.config(scrollregion=(0, 0, zoomed_width, zoomed_height))

            # Draw the "after" version as the default with a tag for scaling
            self.image_item = self.preview_canvas.create_image(
                0, 0, anchor="nw", image=self.preview_photo, tags=("preview_image",)
            )

            # Scale the image if zoomed
            if self.zoom_level != 1.0:
                self.preview_canvas.scale("preview_image", 0, 0, self.zoom_level, self.zoom_level)

            # Add mouse hover binding to show before/after
            def on_mouse_enter(event):
                # Show the "before" version on hover
                self.preview_canvas.itemconfig(self.image_item, image=self.before_photo)
                self.is_hovering = True

            def on_mouse_leave(event):
                # Show the "after" version when not hovering
                self.preview_canvas.itemconfig(self.image_item, image=self.preview_photo)
                self.is_hovering = False

            self.preview_canvas.bind("<Enter>", on_mouse_enter)
            self.preview_canvas.bind("<Leave>", on_mouse_leave)

            self.preview_status.config(text=f"Ready - hover to see original (Zoom: {int(self.zoom_level * 100)}%)")

    def zoom_preview(self, factor):
        """Change the zoom level of the preview

        Args:
            factor: Zoom factor (use 1.0 to reset, >1.0 to zoom in, <1.0 to zoom out)
        """
        if not hasattr(self, "preview_photo") or not self.preview_photo:
            return

        # Calculate new zoom level
        if factor == 1.0:
            # Reset zoom
            self.zoom_level = 1.0
        else:
            # Adjust zoom
            new_zoom = self.zoom_level * factor
            # Limit zoom range (0.1x to 5.0x)
            self.zoom_level = max(0.1, min(5.0, new_zoom))

        # Update the canvas
        self.update_preview_canvas()

        # Update zoom status
        self.zoom_percentage.config(text=f"{int(self.zoom_level * 100)}%")

    def toggle_eyedropper_mode(self, active):
        """Toggle between eyedropper mode and normal preview mode

        Args:
            active: True to activate eyedropper mode, False to deactivate
        """
        if active:
            # If eyedropper is active, disable panning temporarily
            self.preview_canvas.unbind("<ButtonPress-1>")
            self.preview_canvas.unbind("<B1-Motion>")
            self.preview_canvas.unbind("<ButtonRelease-1>")
        else:
            # Restore panning when eyedropper is done
            self.preview_canvas.bind("<ButtonPress-1>", self.start_pan)
            self.preview_canvas.bind("<B1-Motion>", self.do_pan)
            self.preview_canvas.bind("<ButtonRelease-1>", self.end_pan)

    def start_pan(self, event):
        """Start canvas panning operation

        Args:
            event: The mouse event
        """
        # Only start panning with left mouse button
        if event.num == 1:
            self.is_panning = True
            self.preview_canvas.scan_mark(event.x, event.y)
            # Remember current hover state
            self.hover_state_before_pan = getattr(self, "is_hovering", False)

    def do_pan(self, event):
        """Continue canvas panning operation

        Args:
            event: The mouse event
        """
        if hasattr(self, "is_panning") and self.is_panning:
            self.preview_canvas.scan_dragto(event.x, event.y, gain=1)

    def end_pan(self, event):
        """End canvas panning operation

        Args:
            event: The mouse event
        """
        if hasattr(self, "is_panning") and self.is_panning:
            self.is_panning = False
            # Restore proper hover state based on current mouse position
            x, y = self.preview_canvas.winfo_pointerxy()
            canvas_x, canvas_y = self.preview_canvas.winfo_rootx(), self.preview_canvas.winfo_rooty()
            canvas_width, canvas_height = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()

            # Check if mouse is within canvas bounds
            if canvas_x <= x < canvas_x + canvas_width and canvas_y <= y < canvas_y + canvas_height:
                # Mouse is over canvas
                if not getattr(self, "is_hovering", False):
                    if hasattr(self, "image_item") and hasattr(self, "before_photo"):
                        self.preview_canvas.itemconfig(self.image_item, image=self.before_photo)
                    self.is_hovering = True
            else:
                # Mouse is outside canvas
                if getattr(self, "is_hovering", False):
                    if hasattr(self, "image_item") and hasattr(self, "preview_photo"):
                        self.preview_canvas.itemconfig(self.image_item, image=self.preview_photo)
                    self.is_hovering = False
