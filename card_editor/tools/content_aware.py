"""
Content-aware fill tool implementation
"""

import tkinter as tk

from contentAwareFill import EnhancedContentAwareFill


def apply_content_aware_fill(editor, selection_coords=None):
    """
    Open the content-aware fill dialog

    Args:
        editor: CardEditor instance
        selection_coords: Optional coordinates, uses editor's current selection if None
    """
    if selection_coords is None:
        selection_coords = editor.selection_coords

    if not selection_coords:
        return

    # Record state before applying content-aware fill
    if hasattr(editor, "record_state"):
        editor.record_state("Before content-aware fill")

    # Create fill handler with callback function
    def on_apply(description):
        if hasattr(editor, "record_state"):
            editor.record_state(description)

    # Create the enhanced fill dialog with callback
    fill_handler = EnhancedContentAwareFill(editor, selection_coords, on_apply_callback=on_apply)
    return fill_handler
