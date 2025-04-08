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

    # Use lambda functions to avoid method reference issues during initialization
    editor.zoom_in_btn = ttk.Button(zoom_frame, text="Zoom In", command=lambda: editor.zoom_in())
    editor.zoom_in_btn.pack(fill="x", pady=2)

    editor.zoom_out_btn = ttk.Button(zoom_frame, text="Zoom Out", command=lambda: editor.zoom_out())
    editor.zoom_out_btn.pack(fill="x", pady=2)

    editor.zoom_fit_btn = ttk.Button(zoom_frame, text="Fit to Window", command=lambda: editor.zoom_fit())
    editor.zoom_fit_btn.pack(fill="x", pady=2)

    editor.zoom_actual_btn = ttk.Button(zoom_frame, text="Actual Size (100%)", command=lambda: editor.zoom_actual())
    editor.zoom_actual_btn.pack(fill="x", pady=2)

    # Fullscreen toggle
    editor.fullscreen_btn = ttk.Button(toolbar, text="Toggle Fullscreen", command=lambda: editor.toggle_fullscreen())
    editor.fullscreen_btn.pack(fill="x", padx=5, pady=5)

    # Tools separator
    ttk.Separator(toolbar, orient=tk.HORIZONTAL).pack(fill="x", padx=5, pady=10)

    # Tool selection
    tools_frame = ttk.LabelFrame(toolbar, text="Tools")
    tools_frame.pack(fill="x", padx=5, pady=5)

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

    # Initialize selection mode variable
    editor.selection_mode_var = tk.StringVar(value="rectangle")  # Default to rectangle selection
    editor.brush_size_var = tk.IntVar(value=20)  # Default brush size 20px

    # Toggle button for expanding/collapsing the settings
    editor.toggle_settings_btn = ttk.Button(
        tools_frame, text="▼ Auto Fill Settings", command=lambda: editor.toggle_auto_fill_settings()
    )
    editor.toggle_settings_btn.pack(fill="x", pady=2)

    # Add Selection Mode frame to auto_fill_settings_frame
    selection_mode_frame = ttk.LabelFrame(editor.auto_fill_settings_frame, text="Selection Mode")
    selection_mode_frame.pack(fill="x", pady=2, padx=5)

    # Create button frame for selection mode options
    button_frame = ttk.Frame(selection_mode_frame)
    button_frame.pack(fill="x", pady=2)

    # Try to load icons
    try:
        import os

        from PIL import Image, ImageTk

        # Get resources path (relative to the ui folder)
        resources_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources")

        # Load icons
        rectangle_dark = ImageTk.PhotoImage(Image.open(os.path.join(resources_path, "rectangle_select_dark.ico")))
        rectangle_light = ImageTk.PhotoImage(Image.open(os.path.join(resources_path, "rectangle_select.ico")))
        spot_healing_dark = ImageTk.PhotoImage(Image.open(os.path.join(resources_path, "spot_healing_dark.ico")))
        spot_healing_light = ImageTk.PhotoImage(Image.open(os.path.join(resources_path, "spot_healing.ico")))

        # Store references to icons
        editor.rectangle_dark_icon = rectangle_dark
        editor.rectangle_light_icon = rectangle_light
        editor.spot_healing_dark_icon = spot_healing_dark
        editor.spot_healing_light_icon = spot_healing_light

        icons_loaded = True
    except Exception as e:
        print(f"Failed to load icons: {e}")
        icons_loaded = False

    # Function to update button appearance based on selection
    def update_selection_buttons():
        current_mode = editor.selection_mode_var.get()

        if icons_loaded:
            # Update rectangle button
            if current_mode == "rectangle":
                editor.rectangle_btn.config(bg="gray", image=editor.rectangle_light_icon)
            else:
                editor.rectangle_btn.config(bg=editor.root.cget("bg"), image=editor.rectangle_dark_icon)

            # Update spot healing button
            if current_mode == "spot_healing":
                editor.spot_healing_btn.config(bg="gray", image=editor.spot_healing_light_icon)
            else:
                editor.spot_healing_btn.config(bg=editor.root.cget("bg"), image=editor.spot_healing_dark_icon)
        else:
            # Text fallback if icons failed to load
            if current_mode == "rectangle":
                editor.rectangle_btn.config(bg="gray", fg="white")
            else:
                editor.rectangle_btn.config(bg=editor.root.cget("bg"), fg="black")

            if current_mode == "spot_healing":
                editor.spot_healing_btn.config(bg="gray", fg="white")
            else:
                editor.spot_healing_btn.config(bg=editor.root.cget("bg"), fg="black")

        # Show/hide brush size control based on selection mode
        if current_mode == "spot_healing":
            editor.brush_size_frame.pack(fill="x", pady=2, padx=5)
        else:
            editor.brush_size_frame.pack_forget()

    # Create selection mode buttons
    if icons_loaded:
        editor.rectangle_btn = tk.Button(
            button_frame,
            image=editor.rectangle_dark_icon,
            command=lambda: [editor.selection_mode_var.set("rectangle"), update_selection_buttons()],
        )
        editor.spot_healing_btn = tk.Button(
            button_frame,
            image=editor.spot_healing_dark_icon,
            command=lambda: [editor.selection_mode_var.set("spot_healing"), update_selection_buttons()],
        )
    else:
        # Fallback to text buttons
        editor.rectangle_btn = tk.Button(
            button_frame,
            text="Rectangle",
            command=lambda: [editor.selection_mode_var.set("rectangle"), update_selection_buttons()],
        )
        editor.spot_healing_btn = tk.Button(
            button_frame,
            text="Spot Healing",
            command=lambda: [editor.selection_mode_var.set("spot_healing"), update_selection_buttons()],
        )

    # Pack buttons side by side
    editor.rectangle_btn.pack(side=tk.LEFT, padx=5, pady=2)
    editor.spot_healing_btn.pack(side=tk.LEFT, padx=5, pady=2)

    # Add label explaining the selection modes
    ttk.Label(
        selection_mode_frame,
        text="Rectangle: Draw selection box | Spot healing: Use brush",
        font=("TkDefaultFont", 8),
        foreground="gray",
    ).pack(anchor="w", padx=5, pady=2)

    # Create brush size control frame (hidden by default for rectangle mode)
    editor.brush_size_frame = ttk.Frame(editor.auto_fill_settings_frame)

    # Add brush size control widgets
    brush_size_inner_frame = ttk.Frame(editor.brush_size_frame)
    brush_size_inner_frame.pack(fill="x")

    ttk.Label(brush_size_inner_frame, text="Brush Size:").pack(side=tk.LEFT, padx=(0, 5))
    brush_size_spinbox = ttk.Spinbox(
        brush_size_inner_frame, from_=1, to=100, textvariable=editor.brush_size_var, width=5
    )
    brush_size_spinbox.pack(side=tk.LEFT)

    # Initialize button appearance
    update_selection_buttons()

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

    editor.apply_btn = ttk.Button(actions_frame, text="Apply Changes", command=lambda: editor.apply_tool())
    editor.apply_btn.pack(fill="x", pady=2)

    editor.undo_btn = ttk.Button(actions_frame, text="Undo (Ctrl+Z)", command=lambda: editor.undo())
    editor.undo_btn.pack(fill="x", pady=2)

    editor.reset_btn = ttk.Button(actions_frame, text="Reset Selection", command=lambda: editor.reset_selection())
    editor.reset_btn.pack(fill="x", pady=2)

    # File operations separator
    ttk.Separator(toolbar, orient=tk.HORIZONTAL).pack(fill="x", padx=5, pady=10)

    # File operations
    file_frame = ttk.LabelFrame(toolbar, text="File")
    file_frame.pack(fill="x", padx=5, pady=5)

    editor.save_btn = ttk.Button(file_frame, text="Save", command=lambda: editor.save_image())
    editor.save_btn.pack(fill="x", pady=2)

    editor.save_as_btn = ttk.Button(file_frame, text="Save As...", command=lambda: editor.save_image_as())
    editor.save_as_btn.pack(fill="x", pady=2)

    editor.close_btn = ttk.Button(file_frame, text="Close", command=lambda: editor.close_editor())
    editor.close_btn.pack(fill="x", pady=2)

    return toolbar
