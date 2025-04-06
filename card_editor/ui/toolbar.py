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

    # Using tk.Button instead of ttk.Button for better border control
    editor.select_btn = tk.Button(tools_frame, text="Select", command=lambda: editor.set_tool(EditorTool.SELECT))
    editor.select_btn.pack(fill="x", pady=2)

    editor.pan_btn = tk.Button(tools_frame, text="Pan", command=lambda: editor.set_tool(EditorTool.PAN))
    editor.pan_btn.pack(fill="x", pady=2)

    editor.fill_btn = tk.Button(
        tools_frame, text="Content-Aware Fill", command=lambda: editor.set_tool(EditorTool.CONTENT_AWARE_FILL)
    )
    editor.fill_btn.pack(fill="x", pady=2)

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
    editor.fill_tolerance_var = tk.IntVar(value=80)  # Default tolerance 80
    editor.fill_border_var = tk.IntVar(value=3)  # Default border 3px
    editor.advanced_detection_var = tk.BooleanVar(value=True)  # Advanced detection of text

    # Toggle button for expanding/collapsing the settings
    editor.toggle_settings_btn = ttk.Button(
        tools_frame, text="▼ Auto Fill Settings", command=editor.toggle_auto_fill_settings
    )
    editor.toggle_settings_btn.pack(fill="x", pady=2)

    # Color detection mode frame
    detect_frame = ttk.LabelFrame(editor.auto_fill_settings_frame, text="Detection Mode")
    detect_frame.pack(fill="x", pady=2, padx=5)

    ttk.Radiobutton(detect_frame, text="Detect Dark Colors", variable=editor.color_detect_mode, value="dark").pack(
        anchor="w", padx=5, pady=2
    )

    ttk.Radiobutton(detect_frame, text="Detect Light Colors", variable=editor.color_detect_mode, value="light").pack(
        anchor="w", padx=5, pady=2
    )

    ttk.Radiobutton(detect_frame, text="Select Specific Color", variable=editor.color_detect_mode, value="custom").pack(
        anchor="w", padx=5, pady=2
    )

    # Custom text color selection
    color_frame = ttk.Frame(editor.auto_fill_settings_frame)
    color_frame.pack(fill="x", pady=2, padx=5)

    ttk.Label(color_frame, text="Text Color:").pack(side=tk.LEFT, padx=(0, 5))

    editor.color_button = tk.Button(
        color_frame, bg=editor.text_color_var.get(), width=3, command=editor.pick_text_color
    )
    editor.color_button.pack(side=tk.LEFT, padx=5)

    # Add eyedropper button
    eyedropper_btn = ttk.Button(color_frame, text="🔍", width=3, command=editor.activate_text_eyedropper)
    eyedropper_btn.pack(side=tk.LEFT, padx=5)

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

    # Then place the reset button after it:
    editor.reset_btn = ttk.Button(actions_frame, text="Reset Selection", command=editor.reset_selection)
    editor.reset_btn.pack(fill="x", pady=2)

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
