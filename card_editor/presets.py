"""
Functions for managing card presets
"""

import json
import tkinter as tk
from pathlib import Path
from tkinter import simpledialog

from card_editor.models import CardPreset


def load_presets():
    """
    Load presets from the presets folder. Returns a list of CardPreset objects.
    """
    try:
        # Create presets directory if it doesn't exist
        presets_dir = Path("./presets")
        presets_dir.mkdir(exist_ok=True)

        # Check if any preset files exist
        preset_files = list(presets_dir.glob("*.json"))
        presets = []

        if preset_files:
            # Load each preset from its file
            for preset_file in preset_files:
                try:
                    with open(preset_file, "r") as f:
                        preset_data = json.load(f)
                    # Add to presets list
                    presets.append(CardPreset.from_dict(preset_data))
                except Exception as e:
                    print(f"Error loading preset {preset_file}: {str(e)}")
        else:
            # Create default "Normal mtg card" preset
            default_preset = CardPreset(name="Normal mtg card")
            presets.append(default_preset)

            # Save the default preset
            save_preset(default_preset)

        return presets
    except Exception as e:
        # Create default preset on error
        default_preset = CardPreset(name="Normal mtg card")
        presets = [default_preset]
        return presets


def save_preset(preset):
    """
    Save a single preset to file.
    Returns True if successful, False otherwise.
    """
    try:
        # Create presets directory if it doesn't exist
        presets_dir = Path("./presets")
        presets_dir.mkdir(exist_ok=True)

        # Create valid filename from preset name
        # Replace spaces and special chars with underscores
        filename = "".join(c if c.isalnum() else "_" for c in preset.name) + ".json"
        file_path = presets_dir / filename

        # Save preset to file
        with open(file_path, "w") as f:
            json.dump(preset.to_dict(), f, indent=4)

        return True
    except Exception as e:
        print(f"Failed to save preset '{preset.name}': {str(e)}")
        return False


def load_preset_from_file(file_path):
    """
    Load a preset from a specific file.
    Returns the loaded preset.
    """
    try:
        with open(file_path, "r") as f:
            preset_data = json.load(f)
        return CardPreset.from_dict(preset_data)
    except Exception as e:
        print(f"Failed to load preset from file: {str(e)}")
        return None


def add_preset(presets, parent_window=None):
    """
    Add a new preset and return it.
    If parent_window is provided, will show UI dialogs.
    """
    name = simpledialog.askstring("New Preset", "Enter preset name:")
    if not name:
        return None

    # Check if name already exists
    if any(p.name == name for p in presets):
        if parent_window:
            tk.messagebox.showwarning("Duplicate Name", "A preset with this name already exists.")
        return None

    # Create new preset
    new_preset = CardPreset(name=name)
    presets.append(new_preset)

    # Save the new preset
    save_preset(new_preset)

    return new_preset


def remove_preset(presets, index, parent_window=None):
    """
    Remove a preset at the given index.
    Returns True if successful, False otherwise.
    """
    if not presets or index >= len(presets):
        return False

    preset_to_remove = presets[index]

    if parent_window and not tk.messagebox.askyesno("Confirm Removal", f"Remove preset '{preset_to_remove.name}'?"):
        return False

    # Try to remove the preset file
    try:
        presets_dir = Path("./presets")
        # Create filename same way as save_preset does
        filename = "".join(c if c.isalnum() else "_" for c in preset_to_remove.name) + ".json"
        file_path = presets_dir / filename

        if file_path.exists():
            file_path.unlink()  # Delete the file
    except Exception as e:
        print(f"Error removing preset file: {str(e)}")

    # Remove preset from list
    del presets[index]
    return True


def rename_preset(presets, index, parent_window=None):
    """
    Rename a preset at the given index.
    Returns True if successful, False otherwise.
    """
    if not presets or index >= len(presets):
        return False

    preset_to_rename = presets[index]
    old_name = preset_to_rename.name

    new_name = simpledialog.askstring("Rename Preset", "Enter new name:", initialvalue=old_name)
    if not new_name or new_name == old_name:
        return False

    # Check if name already exists
    if any(p.name == new_name for p in presets):
        if parent_window:
            tk.messagebox.showwarning("Duplicate Name", "A preset with this name already exists.")
        return False

    # Try to remove the old preset file
    try:
        presets_dir = Path("./presets")
        # Create old filename same way as save_preset does
        old_filename = "".join(c if c.isalnum() else "_" for c in old_name) + ".json"
        old_file_path = presets_dir / old_filename

        if old_file_path.exists():
            old_file_path.unlink()  # Delete the old file
    except Exception as e:
        print(f"Error removing old preset file: {str(e)}")

    # Update preset name
    preset_to_rename.name = new_name

    # Save with new name
    save_preset(preset_to_rename)

    return True


def save_all_presets(presets):
    """
    Save all presets to files.
    Returns the number of successfully saved presets.
    """
    if not presets:
        return 0

    # Create presets directory if it doesn't exist
    presets_dir = Path("./presets")
    presets_dir.mkdir(exist_ok=True)

    # Save each preset to its own file
    success_count = 0
    for preset in presets:
        if save_preset(preset):
            success_count += 1

    return success_count
