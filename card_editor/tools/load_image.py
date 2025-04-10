"""
Image loading tool implementation
(Note: Core logic moved to CardEditor class for placement mode)
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from PIL import Image


def load_image_to_selection(editor):
    """
    Initiates the image loading process in the editor,
    which now leads to placement mode.

    Args:
        editor: CardEditor instance
    """
    # This function now just calls the editor's method
    # The actual file dialog and placement setup happens there.
    editor.load_image_to_selection()


# Keep the old logic commented out for reference if needed
# def old_load_image_to_selection(editor):
#     """
#     Load an image into the selected area (Old immediate paste logic)
#
#     Args:
#         editor: CardEditor instance
#     """
#     if not editor.selection_coords:
#         return False # Indicate failure or do nothing
#
#     # Open file dialog
#     file_path = filedialog.askopenfilename(
#         title="Select Image", filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif"), ("All files", "*.*")]
#     )
#
#     if not file_path:
#         # editor.reset_selection() # Don't reset selection if cancelled
#         return False
#
#     try:
#         # Record state before loading image
#         if hasattr(editor, "record_state"):
#             editor.record_state("Before loading image")
#
#         # Load the image
#         overlay_img = Image.open(file_path)
#
#         # Get selection dimensions
#         x1, y1, x2, y2 = editor.selection_coords
#         sel_width = x2 - x1
#         sel_height = y2 - y1
#
#         # Resize overlay image to fit selection (using LANCZOS for quality)
#         # Consider aspect ratio preservation later if needed
#         overlay_img = overlay_img.resize((sel_width, sel_height), Image.LANCZOS)
#
#         # Ensure working image is RGBA if overlay has alpha
#         if overlay_img.mode == 'RGBA' and editor.working_image.mode != 'RGBA':
#              editor.working_image = editor.working_image.convert('RGBA')
#         # Ensure overlay is RGBA if working image is RGBA (for consistency)
#         elif overlay_img.mode != 'RGBA' and editor.working_image.mode == 'RGBA':
#              overlay_img = overlay_img.convert('RGBA')
#
#         # Paste overlay image onto working image
#         # Use overlay as mask if it has alpha channel for proper blending
#         paste_mask = overlay_img if overlay_img.mode == 'RGBA' else None
#         editor.working_image.paste(overlay_img, (x1, y1), mask=paste_mask)
#
#         # Record state after loading image
#         if hasattr(editor, "record_state"):
#             editor.record_state(f"Inserted image from {Path(file_path).name}")
#
#         # Update display
#         editor.update_display()
#         editor.reset_selection() # Clear selection after paste
#         editor.status_label.config(text=f"Image inserted from {Path(file_path).name}")
#         return True
#     except Exception as e:
#         if hasattr(editor, "root"):
#             tk.messagebox.showerror("Error", f"Failed to insert image: {str(e)}")
#         editor.reset_selection() # Reset selection on error
#         return False
