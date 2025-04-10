"""
UI utility functions for card editor
"""

from PIL import Image, ImageTk


def display_image(editor):
    """
    Update the canvas with the current **base** image (working_image).
    Does NOT handle overlays like placement image - that's done in editor.update_display.

    Args:
        editor: CardEditor instance
    """
    # Apply zoom to the base working image
    new_size = (int(editor.img_width * editor.zoom_factor), int(editor.img_height * editor.zoom_factor))

    # Check if size is valid
    if new_size[0] <= 0 or new_size[1] <= 0:
        print(f"Warning: Invalid resize dimensions requested: {new_size}. Skipping display update.")
        # Optionally clear the canvas or show an error placeholder
        editor.canvas.delete("all")
        editor.image_id = None
        editor.tk_image = None
        return

    try:
        editor.display_image = editor.working_image.resize(new_size, Image.LANCZOS)
    except ValueError as e:
        print(f"Error resizing image: {e}. Size: {new_size}")
        # Handle error, maybe skip update or show placeholder
        editor.canvas.delete("all")
        editor.image_id = None
        editor.tk_image = None
        return

    # Convert to PhotoImage
    editor.tk_image = ImageTk.PhotoImage(editor.display_image)  # Store reference

    # Clear canvas (only base image items, specific overlay handled elsewhere)
    # If placement_img_id exists, it will be redrawn by update_display caller
    if editor.image_id:
        editor.canvas.delete(editor.image_id)
    # Clear selection rect if it exists (will be redrawn if needed)
    # if editor.selection_rect:
    #      editor.canvas.delete(editor.selection_rect)
    #      editor.selection_rect = None # Ensure it's cleared

    # Draw the new base image
    editor.image_id = editor.canvas.create_image(0, 0, anchor="nw", image=editor.tk_image)

    # Update canvas scroll region
    editor.canvas.config(scrollregion=(0, 0, new_size[0], new_size[1]))

    # DO NOT redraw selection here - let update_display handle it after overlays
    # if editor.selection_coords and not editor.is_placing_image:
    #     draw_selection_rect(editor)


def draw_selection_rect(editor):
    """
    Draw the standard selection rectangle on the canvas (red dashed).
    Only called when NOT in placement mode.

    Args:
        editor: CardEditor instance
    """
    if editor.is_placing_image:  # Should not be called during placement
        return

    if editor.selection_rect:
        editor.canvas.delete(editor.selection_rect)
        editor.selection_rect = None  # Clear old reference

    if editor.selection_coords:
        x1, y1, x2, y2 = editor.selection_coords
        # Convert image coordinates to display coordinates
        cx1 = int(x1 * editor.zoom_factor)
        cy1 = int(y1 * editor.zoom_factor)
        cx2 = int(x2 * editor.zoom_factor)
        cy2 = int(y2 * editor.zoom_factor)

        # Ensure coordinates are valid before drawing
        if cx1 < cx2 and cy1 < cy2:
            editor.selection_rect = editor.canvas.create_rectangle(
                cx1, cy1, cx2, cy2, outline="red", width=2, dash=(4, 4)
            )
        else:
            print(f"Skipping drawing invalid selection rect: ({cx1},{cy1}) to ({cx2},{cy2})")
