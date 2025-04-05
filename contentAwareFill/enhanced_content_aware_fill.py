"""Main module for Enhanced Content-Aware Fill with multiple algorithm options"""

import os
import threading
import time
import tkinter as tk
from tkinter import colorchooser, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from .fill_algorithms import FillAlgorithmsMixin
from .fill_operations import FillOperationsMixin

# Import components using relative imports for package structure
from .ui_handlers import UIHandlersMixin
from .utils import UtilsMixin


class EnhancedContentAwareFill(UIHandlersMixin, FillAlgorithmsMixin, FillOperationsMixin, UtilsMixin):
    """Enhanced Content-Aware Fill with multiple algorithm options"""

    def __init__(self, editor, selection_coords):
        """
        Initialize the enhanced content-aware fill

        Args:
            editor: The CardEditor instance
            selection_coords: The coordinates of the selection (x1, y1, x2, y2)
        """
        self.editor = editor
        self.selection_coords = selection_coords
        self.root = editor.root
        self.working_image = editor.working_image

        # Create the dialog
        self.setup_dialog()

    def setup_dialog(self):
        """Set up the dialog with algorithm options"""
        # Create a dialog
        self.fill_dialog = tk.Toplevel(self.root)
        self.fill_dialog.title("Enhanced Content-Aware Fill")
        self.fill_dialog.geometry("550x650")
        self.fill_dialog.transient(self.root)
        self.fill_dialog.grab_set()

        # Variables
        self.color_var = tk.StringVar(value="#000000")
        self.influence_var = tk.DoubleVar(value=0.0)  # 0 = pure inpainting, 1 = pure color
        self.algorithm_var = tk.StringVar(value="opencv_telea")
        self.radius_var = tk.IntVar(value=5)
        self.preview_var = tk.BooleanVar(value=True)
        self.patch_size_var = tk.IntVar(value=5)
        self.search_area_var = tk.IntVar(value=15)
        self.feather_edge_var = tk.IntVar(value=2)
        self.eyedropper_active = False

        # Preview image reference
        self.preview_image = None
        self.preview_photo = None
        self.is_processing = False
        self.process_thread = None

        # Main frame with scrolling
        main_frame = ttk.Frame(self.fill_dialog)
        main_frame.pack(fill="both", expand=True)

        # Canvas for scrolling
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Main content frame with left and right sections
        main_content = ttk.Frame(scrollable_frame, padding=10)
        main_content.pack(fill="both", expand=True)

        # Left column - settings
        settings_frame = ttk.Frame(main_content)
        settings_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=(0, 10))

        # Right column - preview
        preview_frame = ttk.LabelFrame(main_content, text="Preview", padding=10)
        preview_frame.pack(side=tk.RIGHT, fill="both", expand=True, padx=(10, 0))

        # Preview controls
        preview_controls = ttk.Frame(preview_frame)
        preview_controls.pack(fill="x", pady=(0, 10))

        ttk.Checkbutton(
            preview_controls, text="Live preview", variable=self.preview_var, command=self.toggle_preview
        ).pack(side=tk.LEFT)

        self.preview_status = ttk.Label(preview_controls, text="")
        self.preview_status.pack(side=tk.RIGHT)

        # Preview canvas
        self.preview_canvas = tk.Canvas(preview_frame, bg="gray", width=300, height=300)
        self.preview_canvas.pack(fill="both", expand=True)

        # Add "Before/After" label
        ttk.Label(preview_frame, text="Before/After (hover to compare)", foreground="blue").pack(
            anchor="w", pady=(10, 0)
        )

        # Settings column
        frame = settings_frame
        row = 0

        # Create UI
        # Algorithm selection
        algorithm_frame = ttk.LabelFrame(frame, text="Algorithm Selection", padding=10)
        algorithm_frame.grid(row=row, column=0, sticky="ew", pady=10)
        row += 1

        # Traditional algorithms
        ttk.Radiobutton(
            algorithm_frame,
            text="OpenCV Telea (Default, Fast)",
            variable=self.algorithm_var,
            value="opencv_telea",
            command=self.update_ui_for_algorithm,
        ).pack(anchor="w", pady=2)

        ttk.Radiobutton(
            algorithm_frame,
            text="OpenCV NS (Better Quality)",
            variable=self.algorithm_var,
            value="opencv_ns",
            command=self.update_ui_for_algorithm,
        ).pack(anchor="w", pady=2)

        ttk.Radiobutton(
            algorithm_frame,
            text="Patch-Based Filling (Texture Preservation)",
            variable=self.algorithm_var,
            value="patch_based",
            command=self.update_ui_for_algorithm,
        ).pack(anchor="w", pady=2)

        # Conditional deep learning options with clear warnings
        deep_learning_header = ttk.Label(
            algorithm_frame,
            text="Deep Learning Options (Require additional packages)",
            font=("TkDefaultFont", 10, "bold"),
        )
        deep_learning_header.pack(anchor="w", pady=(10, 2))

        has_torch = self.check_module_available("torch")
        has_tf = self.check_module_available("tensorflow")

        # PyTorch-based option
        pytorch_radio = ttk.Radiobutton(
            algorithm_frame,
            text="LaMa (PyTorch - High Quality)" + (" - Not Available" if not has_torch else ""),
            variable=self.algorithm_var,
            value="lama_pytorch",
            command=self.update_ui_for_algorithm,
        )
        pytorch_radio.pack(anchor="w", pady=2)
        if not has_torch:
            pytorch_radio.config(state="disabled")

        # TensorFlow-based option
        tf_radio = ttk.Radiobutton(
            algorithm_frame,
            text="DeepFill v2 (TensorFlow)" + (" - Not Available" if not has_tf else ""),
            variable=self.algorithm_var,
            value="deepfill_tf",
            command=self.update_ui_for_algorithm,
        )
        tf_radio.pack(anchor="w", pady=2)
        if not has_tf:
            tf_radio.config(state="disabled")

        # Installation information if modules not found
        if not has_torch or not has_tf:
            install_frame = ttk.Frame(algorithm_frame)
            install_frame.pack(anchor="w", pady=5, fill="x")

            install_text = "To use deep learning methods, install:"
            if not has_torch:
                install_text += "\n• PyTorch: pip install torch torchvision"
            if not has_tf:
                install_text += "\n• TensorFlow: pip install tensorflow"

            ttk.Label(install_frame, text=install_text, foreground="blue").pack(anchor="w", pady=2)

        # Color influence frame
        color_frame = ttk.LabelFrame(frame, text="Color Settings", padding=10)
        color_frame.grid(row=row, column=0, sticky="ew", pady=10)
        row += 1

        ttk.Label(color_frame, text="Influence Color:").grid(row=0, column=0, sticky="w", pady=5)
        color_select_frame = ttk.Frame(color_frame)
        color_select_frame.grid(row=0, column=1, sticky="w", pady=5)

        color_entry = ttk.Entry(color_select_frame, textvariable=self.color_var, width=8)
        color_entry.pack(side=tk.LEFT)

        self.color_button = tk.Button(color_select_frame, bg=self.color_var.get(), width=3, command=self.pick_color)
        self.color_button.pack(side=tk.LEFT, padx=5)

        # Eyedropper button
        eyedropper_btn = ttk.Button(color_select_frame, text="🔍", width=3, command=self.activate_eyedropper)
        eyedropper_btn.pack(side=tk.LEFT)

        ttk.Label(color_select_frame, text="Pick from image", foreground="blue").pack(side=tk.LEFT, padx=5)

        # Influence strength
        ttk.Label(color_frame, text="Color Influence:").grid(row=1, column=0, sticky="w", pady=10)
        influence_frame = ttk.Frame(color_frame)
        influence_frame.grid(row=1, column=1, sticky="we", pady=10)

        influence_scale = ttk.Scale(influence_frame, from_=0, to=1.0, variable=self.influence_var, orient="horizontal")
        influence_scale.pack(side=tk.LEFT, fill="x", expand=True)

        self.influence_label = ttk.Label(influence_frame, text="0%")
        self.influence_label.pack(side=tk.LEFT, padx=5)

        # Setup influence label update
        self.influence_var.trace_add("write", self.update_influence_label)

        # Algorithm-specific settings frame
        self.algorithm_settings_frame = ttk.LabelFrame(frame, text="Algorithm Settings", padding=10)
        self.algorithm_settings_frame.grid(row=row, column=0, sticky="ew", pady=10)
        row += 1

        # Application buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=row, column=0, sticky="ew", pady=10)
        row += 1

        self.apply_button = ttk.Button(button_frame, text="Apply", command=self.apply_fill)
        self.apply_button.pack(side=tk.LEFT, padx=5)

        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_fill)
        self.cancel_button.pack(side=tk.LEFT, padx=5)

        # Progress and status
        self.status_label = ttk.Label(frame, text="Ready")
        self.status_label.grid(row=row, column=0, sticky="w", pady=10)
        row += 1

        self.progress = ttk.Progressbar(frame, orient="horizontal", mode="indeterminate", length=200)
        self.progress.grid(row=row, column=0, sticky="ew", pady=5)

        # Initialize UI for selected algorithm
        self.update_ui_for_algorithm()

        # Make sure dialog is properly cleaned up on window close
        self.fill_dialog.protocol("WM_DELETE_WINDOW", self.cancel_fill)

        # Initial preview
        if self.preview_var.get():
            self.update_preview()
