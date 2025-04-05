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

        if algorithm in ["opencv_telea", "opencv_ns"]:
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
        def process_preview():
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
                if algorithm in ["opencv_telea", "opencv_ns"]:
                    after_img = self.apply_opencv_inpainting(img_copy, preview=True)
                elif algorithm == "patch_based":
                    after_img = self.apply_patch_based(img_copy, preview=True)
                elif algorithm == "lama_pytorch":
                    after_img = self.apply_lama_pytorch(img_copy, preview=True)
                elif algorithm == "deepfill_tf":
                    after_img = self.apply_deepfill_tf(img_copy, preview=True)
                else:
                    after_img = img_copy.copy()  # Default fallback

                # Get color influence if set
                influence = self.influence_var.get()
                if influence > 0:
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

                # Create initial display with "after" result
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

        # Start processing thread
        self.process_thread = threading.Thread(target=process_preview)
        self.process_thread.daemon = True
        self.process_thread.start()

    def update_preview_canvas(self):
        """Update the preview canvas with the processed image"""
        if self.preview_photo and self.before_photo:
            self.preview_canvas.delete("all")

            # Set canvas size to match the preview
            self.preview_canvas.config(width=self.preview_photo.width(), height=self.preview_photo.height())

            # Draw the "after" version as the default
            self.image_item = self.preview_canvas.create_image(0, 0, anchor="nw", image=self.preview_photo)

            # Add mouse hover binding to show before/after
            def on_mouse_enter(event):
                # Show the "before" version on hover
                self.preview_canvas.itemconfig(self.image_item, image=self.before_photo)

            def on_mouse_leave(event):
                # Show the "after" version when not hovering
                self.preview_canvas.itemconfig(self.image_item, image=self.preview_photo)

            self.preview_canvas.bind("<Enter>", on_mouse_enter)
            self.preview_canvas.bind("<Leave>", on_mouse_leave)

            self.preview_status.config(text="Ready - hover to see original")
