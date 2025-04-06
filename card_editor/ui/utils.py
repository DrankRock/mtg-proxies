"""
UI utility functions for card editor
"""

from PIL import Image, ImageTk


def display_image(editor):
    """
    Update the canvas with the current image

    Args:
        editor: CardEditor instance
    """
    # Apply zoom
    new_size = (int(editor.img_width * editor.zoom_factor), int(editor.img_height * editor.zoom_factor))
    editor.display_image = editor.working_image.resize(new_size, Image.LANCZOS)

    # Convert to PhotoImage
    editor.tk_image = ImageTk.PhotoImage(editor.display_image)

    # Clear canvas and draw new image
    editor.canvas.delete("all")
    editor.image_id = editor.canvas.create_image(0, 0, anchor="nw", image=editor.tk_image)

    # Update canvas scroll region
    editor.canvas.config(scrollregion=(0, 0, new_size[0], new_size[1]))

    # Redraw selection if exists
    if editor.selection_coords:
        draw_selection_rect(editor)


def draw_selection_rect(editor):
    """
    Draw the selection rectangle on the canvas

    Args:
        editor: CardEditor instance
    """
    if editor.selection_rect:
        editor.canvas.delete(editor.selection_rect)

    if editor.selection_coords:
        x1, y1, x2, y2 = editor.selection_coords
        # Convert image coordinates to display coordinates
        x1 = int(x1 * editor.zoom_factor)
        y1 = int(y1 * editor.zoom_factor)
        x2 = int(x2 * editor.zoom_factor)
        y2 = int(y2 * editor.zoom_factor)

        editor.selection_rect = editor.canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=2, dash=(4, 4))
