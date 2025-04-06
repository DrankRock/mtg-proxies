"""
History management for undo functionality
"""

from PIL import Image


class HistoryManager:
    """
    Manages a history of image states for undo operations
    """

    def __init__(self, max_history=5):
        """
        Initialize the history manager

        Args:
            max_history: Maximum number of history states to keep
        """
        self.history = []
        self.current_index = -1
        self.max_history = max_history

    def add_state(self, image, description=""):
        """
        Add a new state to the history

        Args:
            image: PIL Image object to store
            description: Optional description of the operation
        """
        # Create a deep copy of the image
        image_copy = image.copy()

        # If we're not at the end of the history (user has undone and then makes a new change),
        # remove all states after the current one
        if self.current_index < len(self.history) - 1:
            self.history = self.history[: self.current_index + 1]

        # Add the new state
        self.history.append((image_copy, description))
        self.current_index = len(self.history) - 1

        # If we've exceeded the maximum history size, remove the oldest state
        if len(self.history) > self.max_history:
            self.history.pop(0)
            self.current_index -= 1

    def can_undo(self):
        """
        Check if undo is possible

        Returns:
            bool: True if there are states to undo to
        """
        return self.current_index > 0

    def undo(self):
        """
        Move to the previous state in history

        Returns:
            tuple: (image, description) of the previous state, or None if cannot undo
        """
        if not self.can_undo():
            return None

        self.current_index -= 1
        return self.history[self.current_index]

    def get_current_state(self):
        """
        Get the current state

        Returns:
            tuple: (image, description) of the current state, or None if history is empty
        """
        if len(self.history) == 0:
            return None

        return self.history[self.current_index]

    def clear(self):
        """Clear the history"""
        self.history = []
        self.current_index = -1
