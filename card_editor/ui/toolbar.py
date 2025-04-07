"""
Toolbar UI creation for card editor
"""

import tkinter as tk
from tkinter import ttk

from card_editor.models import EditorTool


def create_toolbar(editor):
    """
    Create the toolbar with editing tools

    Args:
        editor: CardEditor instance
    """
    toolbar = ttk.Frame(editor.root, width=150)
    toolbar.grid(row=0, column=0, sticky="ns", padx=5, pady=5)

    # Zoom controls
    zoom_frame = ttk.LabelFrame(toolbar, text="Zoom")
    zoom_frame.pack(fill="x", padx=5, pady=5)

    editor.zoom_in_btn = ttk.Button(zoom_frame, text="Zoom In", command=editor.zoom_in)
    editor.zoom_in_btn.pack(fill="x", pady=2)

    editor.zoom_out_btn = ttk.Button(zoom_frame, text="Zoom Out", command=editor.zoom_out)
    editor.zoom_out_btn.pack(fill="x", pady=2)

    editor.zoom_fit_btn = ttk.Button(zoom_frame, text="Fit to Window", command=editor.zoom_fit)
    editor.zoom_fit_btn.pack(fill="x", pady=2)

    editor.zoom_actual_btn = ttk.Button(zoom_frame, text="Actual Size (100%)", command=editor.zoom_actual)
    editor.zoom_actual_btn.pack(fill="x", pady=2)

    # Fullscreen toggle
    editor.fullscreen_btn = ttk.Button(toolbar, text="Toggle Fullscreen", command=editor.toggle_fullscreen)
    editor.fullscreen_btn.pack(fill="x", padx=5, pady=5)

    # Tools separator
    ttk.Separator(toolbar, orient=tk.HORIZONTAL).pack(fill="x", padx=5, pady=10)

    # Tool selection
    tools_frame = ttk.LabelFrame(toolbar, text="Tools")
    tools_frame.pack(fill="x", padx=5, pady=5)

    # Note: Select, Pan, and Content-Aware Fill buttons have been removed

    # Auto Fill Text button
    editor.AUTO_FILL_TEXT_btn = tk.Button(
        tools_frame, text="Auto Fill Text", command=lambda: editor.set_tool(EditorTool.AUTO_FILL_TEXT)
    )
    editor.AUTO_FILL_TEXT_btn.pack(fill="x", pady=2)

    # Auto Fill Text settings (collapsible)
    editor.auto_fill_settings_visible = False
    editor.auto_fill_settings_frame = ttk.Frame(tools_frame)

    # Initialize variables for Auto Fill Text settings
    editor.text_color_var = tk.StringVar(value="#000000")  # Default black
    editor.color_detect_mode = tk.StringVar(value="dark")  # Default to detect dark
    editor.fill_tolerance_var = tk.IntVar(value=120)  # Default tolerance 120 (updated)
    editor.fill_border_var = tk.IntVar(value=2)  # Default border 2px (updated)
    editor.advanced_detection_var = tk.BooleanVar(value=True)  # Advanced detection of text
    editor.fill_iterations_var = tk.IntVar(value=1)  # Default iterations 1 (updated)

    # Toggle button for expanding/collapsing the settings
    editor.toggle_settings_btn = ttk.Button(
        tools_frame, text="▼ Auto Fill Settings", command=editor.toggle_auto_fill_settings
    )
    editor.toggle_settings_btn.pack(fill="x", pady=2)

    # Note: Detection Mode frame, Text Color selection, and Eyedropper have been removed

    # Detection options
    detection_frame = ttk.LabelFrame(editor.auto_fill_settings_frame, text="Detection Options")
    detection_frame.pack(fill="x", pady=2, padx=5)

    # Advanced detection checkbox
    advanced_checkbox = ttk.Checkbutton(
        detection_frame,
        text="Advanced text detection",
        variable=editor.advanced_detection_var,
    )
    advanced_checkbox.pack(anchor="w", padx=5, pady=2)

    # Add explanation text
    ttk.Label(
        detection_frame, text="Helps with thin text detection", font=("TkDefaultFont", 8), foreground="gray"
    ).pack(anchor="w", padx=20, pady=0)

    # Tolerance setting
    tolerance_frame = ttk.Frame(editor.auto_fill_settings_frame)
    tolerance_frame.pack(fill="x", pady=2, padx=5)

    ttk.Label(tolerance_frame, text="Tolerance:").pack(side=tk.LEFT, padx=(0, 5))

    tolerance_spinbox = ttk.Spinbox(tolerance_frame, from_=1, to=255, textvariable=editor.fill_tolerance_var, width=5)
    tolerance_spinbox.pack(side=tk.LEFT)

    # Border size setting
    border_frame = ttk.Frame(editor.auto_fill_settings_frame)
    border_frame.pack(fill="x", pady=2, padx=5)

    ttk.Label(border_frame, text="Border Size:").pack(side=tk.LEFT, padx=(0, 5))

    border_spinbox = ttk.Spinbox(border_frame, from_=0, to=10, textvariable=editor.fill_border_var, width=5)
    border_spinbox.pack(side=tk.LEFT)

    # Add iterations setting
    iterations_frame = ttk.Frame(editor.auto_fill_settings_frame)
    iterations_frame.pack(fill="x", pady=2, padx=5)

    ttk.Label(iterations_frame, text="Iterations:").pack(side=tk.LEFT, padx=(0, 5))

    iterations_spinbox = ttk.Spinbox(iterations_frame, from_=1, to=5, textvariable=editor.fill_iterations_var, width=5)
    iterations_spinbox.pack(side=tk.LEFT)

    # Add explanation text for iterations
    ttk.Label(
        iterations_frame, text="Multiple passes for better results", font=("TkDefaultFont", 8), foreground="gray"
    ).pack(side=tk.LEFT, padx=5, pady=0)

    # Add inpainting method selection instead of the PatchMatch checkbox
    editor.inpainting_method_var = tk.StringVar(value="lama")  # Default to lama
    inpainting_frame = ttk.LabelFrame(editor.auto_fill_settings_frame, text="Inpainting Method")
    inpainting_frame.pack(fill="x", pady=2, padx=5)

    ttk.Radiobutton(
        inpainting_frame, text="OpenCV Telea", variable=editor.inpainting_method_var, value="opencv_telea"
    ).pack(anchor="w", padx=5, pady=2)

    ttk.Radiobutton(inpainting_frame, text="OpenCV NS", variable=editor.inpainting_method_var, value="opencv_ns").pack(
        anchor="w", padx=5, pady=2
    )

    ttk.Radiobutton(
        inpainting_frame, text="Patch Match", variable=editor.inpainting_method_var, value="patchmatch"
    ).pack(anchor="w", padx=5, pady=2)

    ttk.Radiobutton(inpainting_frame, text="LaMa", variable=editor.inpainting_method_var, value="lama").pack(
        anchor="w", padx=5, pady=2
    )

    # Add explanation text
    ttk.Label(
        inpainting_frame,
        text="Select the algorithm used for filling text areas",
        font=("TkDefaultFont", 8),
        foreground="gray",
    ).pack(anchor="w", padx=20, pady=0)

    # Other tools continue below
    editor.text_btn = tk.Button(tools_frame, text="Add Text", command=lambda: editor.set_tool(EditorTool.ADD_TEXT))
    editor.text_btn.pack(fill="x", pady=2)

    editor.image_btn = tk.Button(tools_frame, text="Load Image", command=lambda: editor.set_tool(EditorTool.LOAD_IMAGE))
    editor.image_btn.pack(fill="x", pady=2)

    # Action buttons separator
    ttk.Separator(toolbar, orient=tk.HORIZONTAL).pack(fill="x", padx=5, pady=10)

    # Action buttons
    actions_frame = ttk.LabelFrame(toolbar, text="Actions")
    actions_frame.pack(fill="x", padx=5, pady=5)

    editor.apply_btn = ttk.Button(actions_frame, text="Apply Changes", command=editor.apply_tool)
    editor.apply_btn.pack(fill="x", pady=2)

    editor.undo_btn = ttk.Button(actions_frame, text="Undo (Ctrl+Z)", command=editor.undo)
    editor.undo_btn.pack(fill="x", pady=2)

    editor.reset_btn = ttk.Button(actions_frame, text="Reset Selection", command=editor.reset_selection)
    editor.reset_btn.pack(fill="x", pady=2)

    # File operations separator
    ttk.Separator(toolbar, orient=tk.HORIZONTAL).pack(fill="x", padx=5, pady=10)

    # File operations
    file_frame = ttk.LabelFrame(toolbar, text="File")
    file_frame.pack(fill="x", padx=5, pady=5)

    editor.save_btn = ttk.Button(file_frame, text="Save", command=editor.save_image)
    editor.save_btn.pack(fill="x", pady=2)

    editor.save_as_btn = ttk.Button(file_frame, text="Save As...", command=editor.save_image_as)
    editor.save_as_btn.pack(fill="x", pady=2)

    editor.close_btn = ttk.Button(file_frame, text="Close", command=editor.close_editor)
    editor.close_btn.pack(fill="x", pady=2)

    return toolbar
