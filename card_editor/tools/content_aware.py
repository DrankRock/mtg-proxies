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

    # Create the enhanced fill dialog
    fill_handler = EnhancedContentAwareFill(editor, selection_coords)
    return fill_handler
