"""
Image loading tool implementation
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from PIL import Image


def load_image_to_selection(editor):
    """
    Load an image into the selected area

    Args:
        editor: CardEditor instance
    """
    if not editor.selection_coords:
        return

    # Open file dialog
    file_path = filedialog.askopenfilename(
        title="Select Image", filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif"), ("All files", "*.*")]
    )

    if not file_path:
        editor.reset_selection()
        return

    try:
        # Load the image
        overlay_img = Image.open(file_path)

        # Get selection dimensions
        x1, y1, x2, y2 = editor.selection_coords
        sel_width = x2 - x1
        sel_height = y2 - y1

        # Resize overlay image to fit selection
        overlay_img = overlay_img.resize((sel_width, sel_height), Image.LANCZOS)

        # Paste overlay image onto working image
        editor.working_image.paste(overlay_img, (x1, y1))

        # Update display
        editor.update_display()
        editor.reset_selection()
        editor.status_label.config(text=f"Image inserted from {Path(file_path).name}")
        return True
    except Exception as e:
        if hasattr(editor, "root"):
            tk.messagebox.showerror("Error", f"Failed to insert image: {str(e)}")
        return False
