"""
Presets panel UI creation for card editor
"""

import tkinter as tk
from tkinter import ttk

from card_editor.presets import add_preset, load_preset_from_file, remove_preset, rename_preset, save_all_presets


def create_presets_panel(editor):
    """
    Create the presets panel on the right side

    Args:
        editor: CardEditor instance
    """
    presets_panel = ttk.Frame(editor.root, width=200)
    presets_panel.grid(row=0, column=2, sticky="ns", padx=5, pady=5)

    # Presets title
    presets_title = ttk.Label(presets_panel, text="Presets", font=("Arial", 12, "bold"))
    presets_title.pack(fill="x", pady=5)

    # Presets selection frame
    presets_frame = ttk.LabelFrame(presets_panel, text="Available Presets")
    presets_frame.pack(fill="x", padx=5, pady=5)

    # Presets listbox
    editor.presets_list = tk.Listbox(presets_frame, height=6)
    editor.presets_list.pack(fill="x", padx=5, pady=5)
    editor.presets_list.bind("<<ListboxSelect>>", editor.on_preset_selected)

    # Preset management buttons
    preset_buttons_frame = ttk.Frame(presets_frame)
    preset_buttons_frame.pack(fill="x", padx=5, pady=5)

    ttk.Button(preset_buttons_frame, text="Add", command=editor.add_preset).pack(side=tk.LEFT, padx=2)
    ttk.Button(preset_buttons_frame, text="Remove", command=editor.remove_preset).pack(side=tk.LEFT, padx=2)
    ttk.Button(preset_buttons_frame, text="Rename", command=editor.rename_preset).pack(side=tk.LEFT, padx=2)

    # Separator
    ttk.Separator(presets_panel, orient=tk.HORIZONTAL).pack(fill="x", padx=5, pady=10)

    # Rectangle zones frame
    zones_frame = ttk.LabelFrame(presets_panel, text="Card Zones")
    zones_frame.pack(fill="x", padx=5, pady=5)

    # Image zone
    editor.image_zone_var = tk.BooleanVar(value=False)
    editor.image_zone_frame = ttk.Frame(zones_frame)
    editor.image_zone_frame.pack(fill="x", padx=5, pady=5)

    ttk.Checkbutton(
        editor.image_zone_frame, text="Image Zone", variable=editor.image_zone_var, command=editor.zone_checkbox_changed
    ).pack(anchor="w")

    editor.image_zone_info = ttk.Label(editor.image_zone_frame, text="Not configured")
    editor.image_zone_info.pack(anchor="w", padx=20)

    ttk.Button(editor.image_zone_frame, text="Set", command=lambda: editor.set_preset_zone("image")).pack(
        anchor="w", padx=20
    )
    ttk.Button(editor.image_zone_frame, text="Apply", command=lambda: editor.apply_preset_zone("image")).pack(
        anchor="w", padx=20
    )

    # Name zone
    editor.name_zone_var = tk.BooleanVar(value=False)
    editor.name_zone_frame = ttk.Frame(zones_frame)
    editor.name_zone_frame.pack(fill="x", padx=5, pady=5)

    ttk.Checkbutton(
        editor.name_zone_frame, text="Name Zone", variable=editor.name_zone_var, command=editor.zone_checkbox_changed
    ).pack(anchor="w")

    editor.name_zone_info = ttk.Label(editor.name_zone_frame, text="Not configured")
    editor.name_zone_info.pack(anchor="w", padx=20)

    ttk.Button(editor.name_zone_frame, text="Set", command=lambda: editor.set_preset_zone("name")).pack(
        anchor="w", padx=20
    )
    ttk.Button(editor.name_zone_frame, text="Apply", command=lambda: editor.apply_preset_zone("name")).pack(
        anchor="w", padx=20
    )

    # Type zone
    editor.type_zone_var = tk.BooleanVar(value=False)
    editor.type_zone_frame = ttk.Frame(zones_frame)
    editor.type_zone_frame.pack(fill="x", padx=5, pady=5)

    ttk.Checkbutton(
        editor.type_zone_frame, text="Type Zone", variable=editor.type_zone_var, command=editor.zone_checkbox_changed
    ).pack(anchor="w")

    editor.type_zone_info = ttk.Label(editor.type_zone_frame, text="Not configured")
    editor.type_zone_info.pack(anchor="w", padx=20)

    ttk.Button(editor.type_zone_frame, text="Set", command=lambda: editor.set_preset_zone("type")).pack(
        anchor="w", padx=20
    )
    ttk.Button(editor.type_zone_frame, text="Apply", command=lambda: editor.apply_preset_zone("type")).pack(
        anchor="w", padx=20
    )

    # Description zone
    editor.description_zone_var = tk.BooleanVar(value=False)
    editor.description_zone_frame = ttk.Frame(zones_frame)
    editor.description_zone_frame.pack(fill="x", padx=5, pady=5)

    ttk.Checkbutton(
        editor.description_zone_frame,
        text="Description Zone",
        variable=editor.description_zone_var,
        command=editor.zone_checkbox_changed,
    ).pack(anchor="w")

    editor.description_zone_info = ttk.Label(editor.description_zone_frame, text="Not configured")
    editor.description_zone_info.pack(anchor="w", padx=20)

    ttk.Button(editor.description_zone_frame, text="Set", command=lambda: editor.set_preset_zone("description")).pack(
        anchor="w", padx=20
    )
    ttk.Button(
        editor.description_zone_frame, text="Apply", command=lambda: editor.apply_preset_zone("description")
    ).pack(anchor="w", padx=20)

    # Batch process button
    ttk.Button(presets_panel, text="Process All Selected Zones", command=editor.process_all_zones).pack(
        fill="x", padx=5, pady=10
    )

    # Save and load presets
    presets_file_frame = ttk.Frame(presets_panel)
    presets_file_frame.pack(fill="x", padx=5, pady=5)

    ttk.Button(presets_file_frame, text="Save Presets", command=editor.save_presets).pack(side=tk.LEFT, padx=2)
    ttk.Button(presets_file_frame, text="Load Presets", command=editor.load_presets_file).pack(side=tk.LEFT, padx=2)

    return presets_panel
