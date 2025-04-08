"""
Data models for the Card Editor
"""

from enum import Enum, auto


class EditorTool(Enum):
    """Enum representing the available editing tools"""

    SELECT = auto()
    CONTENT_AWARE_FILL = auto()
    AUTO_FILL_TEXT = auto()
    ADD_TEXT = auto()
    LOAD_IMAGE = auto()
    PAN = auto()


class CardPreset:
    """
    Represents a template for card layout with zones for different card elements
    """

    def __init__(self, name, image_rect=None, name_rect=None, type_rect=None, description_rect=None):
        self.name = name
        self.image_rect = image_rect or {"x": 0.10, "y": 0.20, "width": 0.80, "height": 0.50}
        self.name_rect = name_rect or {"x": 0.10, "y": 0.05, "width": 0.80, "height": 0.10}
        self.type_rect = type_rect or {"x": 0.10, "y": 0.75, "width": 0.80, "height": 0.08}
        self.description_rect = description_rect or {"x": 0.10, "y": 0.85, "width": 0.80, "height": 0.12}

    def to_dict(self):
        """Convert preset to dictionary for serialization"""
        return {
            "name": self.name,
            "image_rect": self.image_rect,
            "name_rect": self.name_rect,
            "type_rect": self.type_rect,
            "description_rect": self.description_rect,
        }

    @classmethod
    def from_dict(cls, data):
        """Create preset from dictionary data"""
        return cls(
            name=data["name"],
            image_rect=data["image_rect"],
            name_rect=data["name_rect"],
            type_rect=data["type_rect"],
            description_rect=data["description_rect"],
        )
