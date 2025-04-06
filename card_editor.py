import json
import os
import tkinter as tk
from enum import Enum, auto
from pathlib import Path
from tkinter import colorchooser, filedialog, simpledialog, ttk

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk

from contentAwareFill import EnhancedContentAwareFill


class EditorTool(Enum):
    SELECT = auto()
    CONTENT_AWARE_FILL = auto()
    AUTO_FILL_TEXT = auto()
    ADD_TEXT = auto()
    LOAD_IMAGE = auto()
    PAN = auto()


class CardPreset:
    def __init__(self, name, image_rect=None, name_rect=None, type_rect=None, description_rect=None):
        self.name = name
        self.image_rect = image_rect or {"x": 0.10, "y": 0.20, "width": 0.80, "height": 0.50}
        self.name_rect = name_rect or {"x": 0.10, "y": 0.05, "width": 0.80, "height": 0.10}
        self.type_rect = type_rect or {"x": 0.10, "y": 0.75, "width": 0.80, "height": 0.08}
        self.description_rect = description_rect or {"x": 0.10, "y": 0.85, "width": 0.80, "height": 0.12}

    def to_dict(self):
        return {
            "name": self.name,
            "image_rect": self.image_rect,
            "name_rect": self.name_rect,
            "type_rect": self.type_rect,
            "description_rect": self.description_rect,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            image_rect=data["image_rect"],
            name_rect=data["name_rect"],
            type_rect=data["type_rect"],
            description_rect=data["description_rect"],
        )


class CardEditor:
    def __init__(self, root, image_path):
        self.root = root
        self.image_path = image_path
        self.on_save_callback = None  # Will be set by launch_editor if needed

        # Set up window
        self.root.title(f"Card Editor - {Path(image_path).name}")
        self.root.geometry("1200x800")

        # Configure main grid
        self.root.grid_columnconfigure(0, weight=0)  # Toolbar
        self.root.grid_columnconfigure(1, weight=1)  # Canvas
        self.root.grid_columnconfigure(2, weight=0)  # Presets
        self.root.grid_rowconfigure(0, weight=1)

        # Load the image
        self.original_image = Image.open(image_path)
        self.working_image = self.original_image.copy()
        self.display_image = None  # For zoomed/transformed image

        # Image metadata
        self.img_width, self.img_height = self.working_image.size

        # Create toolbar
        self.create_toolbar()

        # Create canvas for image display
        self.canvas_frame = ttk.Frame(root)
        self.canvas_frame.grid(row=0, column=1, sticky="nsew")
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)

        # Canvas for image display with scrollbars
        self.canvas = tk.Canvas(self.canvas_frame, bg="gray", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Scrollbars
        self.h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")

        self.v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")

        self.canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)

        self.create_presets_panel()

        # Status bar
        self.status_frame = ttk.Frame(root)
        self.status_frame.grid(row=1, column=0, columnspan=2, sticky="ew")

        self.status_label = ttk.Label(self.status_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.coords_label = ttk.Label(self.status_frame, text="")
        self.coords_label.pack(side=tk.RIGHT, padx=5)

        # Set initial tool
        self.current_tool = EditorTool.CONTENT_AWARE_FILL
        self.selected_tool_button = None  # Track the currently selected tool button

        # Drawing state
        self.start_x = None
        self.start_y = None
        self.selection_rect = None
        self.selection_coords = None  # Format: (x1, y1, x2, y2) in image coordinates

        # Zoom and pan
        self.zoom_factor = 1.0
        self.pan_start_x = 0
        self.pan_start_y = 0

        # Presets variables
        self.presets = []
        self.current_preset = None
        self.load_presets()  # Load presets from file if available

        # Set up event bindings
        self.setup_bindings()

        # Display the image
        self.update_display()

        # Initialize with PAN tool selected
        self.set_tool(EditorTool.PAN)

    def load_presets(self):
        """Load presets from presets folder"""
        try:
            # Create presets directory if it doesn't exist
            presets_dir = Path("./presets")
            presets_dir.mkdir(exist_ok=True)

            # Check if any preset files exist
            preset_files = list(presets_dir.glob("*.json"))

            if preset_files:
                # Load each preset from its file
                self.presets = []
                for preset_file in preset_files:
                    try:
                        with open(preset_file, "r") as f:
                            preset_data = json.load(f)
                        # Add to presets list
                        self.presets.append(CardPreset.from_dict(preset_data))
                    except Exception as e:
                        print(f"Error loading preset {preset_file}: {str(e)}")

                # Update UI
                self.update_presets_list()
                self.status_label.config(text="Presets loaded")
            else:
                # Create default "Normal mtg card" preset
                default_preset = CardPreset(name="Normal mtg card")
                self.presets.append(default_preset)
                self.update_presets_list()

                # Save the default preset
                self.save_preset(default_preset)
        except Exception as e:
            # Create default preset on error
            default_preset = CardPreset(name="Normal mtg card")
            self.presets.append(default_preset)
            self.update_presets_list()
            tk.messagebox.showwarning("Error", f"Failed to load presets: {str(e)}\nUsing default preset.")

    def save_preset(self, preset):
        """Save a single preset to file"""
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
            tk.messagebox.showerror("Error", f"Failed to save preset '{preset.name}': {str(e)}")
            return False

    def load_presets_file(self):
        """Load a single preset from a user-selected file"""
        file_path = filedialog.askopenfilename(
            title="Load Preset", filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )

        if not file_path:
            return

        try:
            with open(file_path, "r") as f:
                preset_data = json.load(f)

            # Convert to CardPreset object
            new_preset = CardPreset.from_dict(preset_data)

            # Check if a preset with this name already exists
            existing_index = None
            for i, preset in enumerate(self.presets):
                if preset.name == new_preset.name:
                    existing_index = i
                    break

            if existing_index is not None:
                # Ask user if they want to replace the existing preset
                if tk.messagebox.askyesno(
                    "Duplicate Name", f"A preset named '{new_preset.name}' already exists. Replace it?"
                ):
                    self.presets[existing_index] = new_preset
                    # Save the updated preset
                    self.save_preset(new_preset)
                else:
                    return
            else:
                # Add the new preset
                self.presets.append(new_preset)
                # Save the new preset
                self.save_preset(new_preset)

            # Update UI
            self.update_presets_list()

            # Select the new preset
            if existing_index is not None:
                self.presets_list.selection_set(existing_index)
            else:
                self.presets_list.selection_set(len(self.presets) - 1)

            self.on_preset_selected(None)
            self.status_label.config(text=f"Preset '{new_preset.name}' loaded")
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to load preset: {str(e)}")

    def save_presets(self):
        """Save all presets to files"""
        if not self.presets:
            tk.messagebox.showinfo("No Presets", "No presets to save")
            return

        # Create presets directory if it doesn't exist
        presets_dir = Path("./presets")
        presets_dir.mkdir(exist_ok=True)

        # Save each preset to its own file
        success_count = 0
        for preset in self.presets:
            if self.save_preset(preset):
                success_count += 1

        self.status_label.config(text=f"{success_count} presets saved")

    def update_presets_list(self):
        """Update the presets listbox with current presets"""
        self.presets_list.delete(0, tk.END)

        for preset in self.presets:
            self.presets_list.insert(tk.END, preset.name)

        # Select first preset if available
        if self.presets and not self.current_preset:
            self.presets_list.selection_set(0)
            self.on_preset_selected(None)

    def on_preset_selected(self, event):
        """Handle preset selection"""
        if not self.presets:
            return

        selection = self.presets_list.curselection()
        if not selection:
            return

        index = selection[0]
        self.current_preset = self.presets[index]

        # Update zone labels
        self.update_zone_info()

        # Set checkbox states based on whether the zones are defined
        # For simplicity, we'll consider a zone as defined if it exists in the preset
        self.image_zone_var.set(True if self.current_preset.image_rect else False)
        self.name_zone_var.set(True if self.current_preset.name_rect else False)
        self.type_zone_var.set(True if self.current_preset.type_rect else False)
        self.description_zone_var.set(True if self.current_preset.description_rect else False)

    def update_zone_info(self):
        """Update zone information labels based on current preset"""
        if not self.current_preset:
            return

        # Image zone
        img_rect = self.current_preset.image_rect
        self.image_zone_info.config(
            text=f"X: {img_rect['x']:.2f}%, Y: {img_rect['y']:.2f}%\n"
            f"W: {img_rect['width']:.2f}%, H: {img_rect['height']:.2f}%"
        )

        # Name zone
        name_rect = self.current_preset.name_rect
        self.name_zone_info.config(
            text=f"X: {name_rect['x']:.2f}%, Y: {name_rect['y']:.2f}%\n"
            f"W: {name_rect['width']:.2f}%, H: {name_rect['height']:.2f}%"
        )

        # Type zone
        type_rect = self.current_preset.type_rect
        self.type_zone_info.config(
            text=f"X: {type_rect['x']:.2f}%, Y: {type_rect['y']:.2f}%\n"
            f"W: {type_rect['width']:.2f}%, H: {type_rect['height']:.2f}%"
        )

        # Description zone
        desc_rect = self.current_preset.description_rect
        self.description_zone_info.config(
            text=f"X: {desc_rect['x']:.2f}%, Y: {desc_rect['y']:.2f}%\n"
            f"W: {desc_rect['width']:.2f}%, H: {desc_rect['height']:.2f}%"
        )

    def add_preset(self):
        """Add a new preset"""
        name = simpledialog.askstring("New Preset", "Enter preset name:")
        if name:
            # Check if name already exists
            if any(p.name == name for p in self.presets):
                tk.messagebox.showwarning("Duplicate Name", "A preset with this name already exists.")
                return

            # Create new preset
            new_preset = CardPreset(name=name)
            self.presets.append(new_preset)

            # Save the new preset
            self.save_preset(new_preset)

            # Update UI
            self.update_presets_list()

            # Select the new preset
            self.presets_list.selection_set(len(self.presets) - 1)
            self.on_preset_selected(None)

    def remove_preset(self):
        """Remove the selected preset"""
        if not self.presets:
            return

        selection = self.presets_list.curselection()
        if not selection:
            tk.messagebox.showinfo("No Selection", "Please select a preset to remove")
            return

        index = selection[0]
        preset_to_remove = self.presets[index]

        if tk.messagebox.askyesno("Confirm Removal", f"Remove preset '{preset_to_remove.name}'?"):
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
            del self.presets[index]

            # Update UI
            self.update_presets_list()

            # Reset current preset if none left
            if not self.presets:
                self.current_preset = None

    def rename_preset(self):
        """Rename the selected preset"""
        if not self.presets:
            return

        selection = self.presets_list.curselection()
        if not selection:
            tk.messagebox.showinfo("No Selection", "Please select a preset to rename")
            return

        index = selection[0]
        preset_to_rename = self.presets[index]
        old_name = preset_to_rename.name

        new_name = simpledialog.askstring("Rename Preset", "Enter new name:", initialvalue=old_name)
        if new_name and new_name != old_name:
            # Check if name already exists
            if any(p.name == new_name for p in self.presets):
                tk.messagebox.showwarning("Duplicate Name", "A preset with this name already exists.")
                return

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
            self.save_preset(preset_to_rename)

            # Update UI
            self.update_presets_list()
            self.presets_list.selection_set(index)

    def zone_checkbox_changed(self):
        """Handle zone checkbox state changes"""
        # This function is called when any zone checkbox is toggled
        pass

    def set_preset_zone(self, zone_type):
        """Set the zone coordinates from the current selection"""
        if not self.current_preset:
            tk.messagebox.showinfo("No Preset", "Please select or create a preset first")
            return

        if not self.selection_coords:
            tk.messagebox.showinfo("No Selection", "Please make a selection on the image first")
            return

        # Convert pixel coordinates to percentage
        x1, y1, x2, y2 = self.selection_coords
        x_percent = x1 / self.img_width
        y_percent = y1 / self.img_height
        width_percent = (x2 - x1) / self.img_width
        height_percent = (y2 - y1) / self.img_height

        # Update the appropriate zone in the current preset
        if zone_type == "image":
            self.current_preset.image_rect = {
                "x": round(x_percent, 2),
                "y": round(y_percent, 2),
                "width": round(width_percent, 2),
                "height": round(height_percent, 2),
            }
            # Enable checkbox
            self.image_zone_var.set(True)
        elif zone_type == "name":
            self.current_preset.name_rect = {
                "x": round(x_percent, 2),
                "y": round(y_percent, 2),
                "width": round(width_percent, 2),
                "height": round(height_percent, 2),
            }
            # Enable checkbox
            self.name_zone_var.set(True)
        elif zone_type == "type":
            self.current_preset.type_rect = {
                "x": round(x_percent, 2),
                "y": round(y_percent, 2),
                "width": round(width_percent, 2),
                "height": round(height_percent, 2),
            }
            # Enable checkbox
            self.type_zone_var.set(True)
        elif zone_type == "description":
            self.current_preset.description_rect = {
                "x": round(x_percent, 2),
                "y": round(y_percent, 2),
                "width": round(width_percent, 2),
                "height": round(height_percent, 2),
            }
            # Enable checkbox
            self.description_zone_var.set(True)

        # Update zone info display
        self.update_zone_info()

        # Reset selection
        self.reset_selection()

        self.status_label.config(text=f"{zone_type.capitalize()} zone set")

        # Save preset after updating
        self.save_preset(self.current_preset)

    def apply_preset_zone(self, zone_type):
        """Apply the selected zone from the preset"""
        if not self.current_preset:
            print("No current preset")
            tk.messagebox.showinfo("No Preset", "Please select a preset first")
            return

        # Get the zone rectangle from the preset
        if zone_type == "image":
            print(f"Image zone checkbox state: {self.image_zone_var.get()}")
            if not self.image_zone_var.get():
                print("Image zone not selected")
                return
            rect = self.current_preset.image_rect
            tool = EditorTool.LOAD_IMAGE
        elif zone_type == "name":
            print(f"Name zone checkbox state: {self.name_zone_var.get()}")
            if not self.name_zone_var.get():
                print("Name zone not selected")
                return
            rect = self.current_preset.name_rect
            tool = EditorTool.ADD_TEXT
        elif zone_type == "type":
            print(f"Type zone checkbox state: {self.type_zone_var.get()}")
            if not self.type_zone_var.get():
                print("Type zone not selected")
                return
            rect = self.current_preset.type_rect
            tool = EditorTool.ADD_TEXT
        elif zone_type == "description":
            print(f"Description zone checkbox state: {self.description_zone_var.get()}")
            if not self.description_zone_var.get():
                print("Description zone not selected")
                return
            rect = self.current_preset.description_rect
            tool = EditorTool.ADD_TEXT

        print(f"Zone: {zone_type}, Rect: {rect}")

        # Convert percentage to pixel coordinates
        x1 = int(rect["x"] * self.img_width)
        y1 = int(rect["y"] * self.img_height)
        x2 = int((rect["x"] + rect["width"]) * self.img_width)
        y2 = int((rect["y"] + rect["height"]) * self.img_height)

        print(f"Selection coords (pixels): ({x1}, {y1}, {x2}, {y2})")

        # Set current tool first without modifying the selection
        current_button = self.selected_tool_button
        self.current_tool = tool

        # Update tool button highlight
        if self.selected_tool_button:
            self.selected_tool_button.config(borderwidth=1, relief="raised")

        if tool == EditorTool.SELECT:
            self.selected_tool_button = self.select_btn
        elif tool == EditorTool.PAN:
            self.selected_tool_button = self.pan_btn
        elif tool == EditorTool.CONTENT_AWARE_FILL:
            self.selected_tool_button = self.fill_btn
        elif tool == EditorTool.ADD_TEXT:
            self.selected_tool_button = self.text_btn
        elif tool == EditorTool.LOAD_IMAGE:
            self.selected_tool_button = self.image_btn

        # Set border on new button
        if self.selected_tool_button:
            self.selected_tool_button.config(borderwidth=2, relief="solid")

        # Update status
        self.status_label.config(text=f"Current tool: {tool.name}")

        # Now set the selection coordinates (after tool change)
        self.selection_coords = (x1, y1, x2, y2)

        # Draw selection rectangle
        self.draw_selection_rect()

        print(f"Before applying tool, self.selection_coords = {self.selection_coords}")
        print(f"Current tool: {self.current_tool}")

        # Apply the tool based on type
        if tool == EditorTool.LOAD_IMAGE:
            self.load_image_to_selection()
        elif tool == EditorTool.ADD_TEXT:
            self.add_text_to_selection()
        elif tool == EditorTool.CONTENT_AWARE_FILL:
            self.apply_content_aware_fill()

    def process_all_zones(self):
        """Process all selected zones in sequence"""
        if not self.current_preset:
            tk.messagebox.showinfo("No Preset", "Please select a preset first")
            return

        zones_to_process = []

        # Check which zones are selected
        if self.image_zone_var.get():
            zones_to_process.append(("image", EditorTool.LOAD_IMAGE))
        if self.name_zone_var.get():
            zones_to_process.append(("name", EditorTool.ADD_TEXT))
        if self.type_zone_var.get():
            zones_to_process.append(("type", EditorTool.ADD_TEXT))
        if self.description_zone_var.get():
            zones_to_process.append(("description", EditorTool.ADD_TEXT))

        if not zones_to_process:
            tk.messagebox.showinfo("No Zones Selected", "Please select at least one zone to process")
            return

        # Process each zone in sequence
        for zone_type, tool in zones_to_process:
            # Apply the zone
            self.apply_preset_zone(zone_type)

            # Small delay to allow for user interaction if needed
            self.root.update()

        self.status_label.config(text="All selected zones processed")

    def create_presets_panel(self):
        """Create the presets panel on the right side"""
        self.presets_panel = ttk.Frame(self.root, width=200)
        self.presets_panel.grid(row=0, column=2, sticky="ns", padx=5, pady=5)

        # Presets title
        presets_title = ttk.Label(self.presets_panel, text="Presets", font=("Arial", 12, "bold"))
        presets_title.pack(fill="x", pady=5)

        # Presets selection frame
        presets_frame = ttk.LabelFrame(self.presets_panel, text="Available Presets")
        presets_frame.pack(fill="x", padx=5, pady=5)

        # Presets listbox
        self.presets_list = tk.Listbox(presets_frame, height=6)
        self.presets_list.pack(fill="x", padx=5, pady=5)
        self.presets_list.bind("<<ListboxSelect>>", self.on_preset_selected)

        # Preset management buttons
        preset_buttons_frame = ttk.Frame(presets_frame)
        preset_buttons_frame.pack(fill="x", padx=5, pady=5)

        ttk.Button(preset_buttons_frame, text="Add", command=self.add_preset).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_buttons_frame, text="Remove", command=self.remove_preset).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_buttons_frame, text="Rename", command=self.rename_preset).pack(side=tk.LEFT, padx=2)

        # Separator
        ttk.Separator(self.presets_panel, orient=tk.HORIZONTAL).pack(fill="x", padx=5, pady=10)

        # Rectangle zones frame
        zones_frame = ttk.LabelFrame(self.presets_panel, text="Card Zones")
        zones_frame.pack(fill="x", padx=5, pady=5)

        # Image zone
        self.image_zone_var = tk.BooleanVar(value=False)
        self.image_zone_frame = ttk.Frame(zones_frame)
        self.image_zone_frame.pack(fill="x", padx=5, pady=5)

        ttk.Checkbutton(
            self.image_zone_frame, text="Image Zone", variable=self.image_zone_var, command=self.zone_checkbox_changed
        ).pack(anchor="w")

        self.image_zone_info = ttk.Label(self.image_zone_frame, text="Not configured")
        self.image_zone_info.pack(anchor="w", padx=20)

        ttk.Button(self.image_zone_frame, text="Set", command=lambda: self.set_preset_zone("image")).pack(
            anchor="w", padx=20
        )
        ttk.Button(self.image_zone_frame, text="Apply", command=lambda: self.apply_preset_zone("image")).pack(
            anchor="w", padx=20
        )

        # Name zone
        self.name_zone_var = tk.BooleanVar(value=False)
        self.name_zone_frame = ttk.Frame(zones_frame)
        self.name_zone_frame.pack(fill="x", padx=5, pady=5)

        ttk.Checkbutton(
            self.name_zone_frame, text="Name Zone", variable=self.name_zone_var, command=self.zone_checkbox_changed
        ).pack(anchor="w")

        self.name_zone_info = ttk.Label(self.name_zone_frame, text="Not configured")
        self.name_zone_info.pack(anchor="w", padx=20)

        ttk.Button(self.name_zone_frame, text="Set", command=lambda: self.set_preset_zone("name")).pack(
            anchor="w", padx=20
        )
        ttk.Button(self.name_zone_frame, text="Apply", command=lambda: self.apply_preset_zone("name")).pack(
            anchor="w", padx=20
        )

        # Type zone
        self.type_zone_var = tk.BooleanVar(value=False)
        self.type_zone_frame = ttk.Frame(zones_frame)
        self.type_zone_frame.pack(fill="x", padx=5, pady=5)

        ttk.Checkbutton(
            self.type_zone_frame, text="Type Zone", variable=self.type_zone_var, command=self.zone_checkbox_changed
        ).pack(anchor="w")

        self.type_zone_info = ttk.Label(self.type_zone_frame, text="Not configured")
        self.type_zone_info.pack(anchor="w", padx=20)

        ttk.Button(self.type_zone_frame, text="Set", command=lambda: self.set_preset_zone("type")).pack(
            anchor="w", padx=20
        )
        ttk.Button(self.type_zone_frame, text="Apply", command=lambda: self.apply_preset_zone("type")).pack(
            anchor="w", padx=20
        )

        # Description zone
        self.description_zone_var = tk.BooleanVar(value=False)
        self.description_zone_frame = ttk.Frame(zones_frame)
        self.description_zone_frame.pack(fill="x", padx=5, pady=5)

        ttk.Checkbutton(
            self.description_zone_frame,
            text="Description Zone",
            variable=self.description_zone_var,
            command=self.zone_checkbox_changed,
        ).pack(anchor="w")

        self.description_zone_info = ttk.Label(self.description_zone_frame, text="Not configured")
        self.description_zone_info.pack(anchor="w", padx=20)

        ttk.Button(self.description_zone_frame, text="Set", command=lambda: self.set_preset_zone("description")).pack(
            anchor="w", padx=20
        )
        ttk.Button(
            self.description_zone_frame, text="Apply", command=lambda: self.apply_preset_zone("description")
        ).pack(anchor="w", padx=20)

        # Batch process button
        ttk.Button(self.presets_panel, text="Process All Selected Zones", command=self.process_all_zones).pack(
            fill="x", padx=5, pady=10
        )

        # Save and load presets
        presets_file_frame = ttk.Frame(self.presets_panel)
        presets_file_frame.pack(fill="x", padx=5, pady=5)

        ttk.Button(presets_file_frame, text="Save Presets", command=self.save_presets).pack(side=tk.LEFT, padx=2)
        ttk.Button(presets_file_frame, text="Load Presets", command=self.load_presets_file).pack(side=tk.LEFT, padx=2)

    def create_toolbar(self):
        """Create the toolbar with editing tools"""
        self.toolbar = ttk.Frame(self.root, width=150)
        self.toolbar.grid(row=0, column=0, sticky="ns", padx=5, pady=5)

        # Zoom controls
        zoom_frame = ttk.LabelFrame(self.toolbar, text="Zoom")
        zoom_frame.pack(fill="x", padx=5, pady=5)

        self.zoom_in_btn = ttk.Button(zoom_frame, text="Zoom In", command=self.zoom_in)
        self.zoom_in_btn.pack(fill="x", pady=2)

        self.zoom_out_btn = ttk.Button(zoom_frame, text="Zoom Out", command=self.zoom_out)
        self.zoom_out_btn.pack(fill="x", pady=2)

        self.zoom_fit_btn = ttk.Button(zoom_frame, text="Fit to Window", command=self.zoom_fit)
        self.zoom_fit_btn.pack(fill="x", pady=2)

        self.zoom_actual_btn = ttk.Button(zoom_frame, text="Actual Size (100%)", command=self.zoom_actual)
        self.zoom_actual_btn.pack(fill="x", pady=2)

        # Fullscreen toggle
        self.fullscreen_btn = ttk.Button(self.toolbar, text="Toggle Fullscreen", command=self.toggle_fullscreen)
        self.fullscreen_btn.pack(fill="x", padx=5, pady=5)

        # Tools separator
        ttk.Separator(self.toolbar, orient=tk.HORIZONTAL).pack(fill="x", padx=5, pady=10)

        # Tool selection
        tools_frame = ttk.LabelFrame(self.toolbar, text="Tools")
        tools_frame.pack(fill="x", padx=5, pady=5)

        # Using tk.Button instead of ttk.Button for better border control
        self.select_btn = tk.Button(tools_frame, text="Select", command=lambda: self.set_tool(EditorTool.SELECT))
        self.select_btn.pack(fill="x", pady=2)

        self.pan_btn = tk.Button(tools_frame, text="Pan", command=lambda: self.set_tool(EditorTool.PAN))
        self.pan_btn.pack(fill="x", pady=2)

        self.fill_btn = tk.Button(
            tools_frame, text="Content-Aware Fill", command=lambda: self.set_tool(EditorTool.CONTENT_AWARE_FILL)
        )
        self.fill_btn.pack(fill="x", pady=2)

        # Auto Fill Text button
        self.AUTO_FILL_TEXT_btn = tk.Button(
            tools_frame, text="Auto Fill Text", command=lambda: self.set_tool(EditorTool.AUTO_FILL_TEXT)
        )
        self.AUTO_FILL_TEXT_btn.pack(fill="x", pady=2)

        # Auto Fill Text settings (collapsible)
        self.auto_fill_settings_visible = False
        self.auto_fill_settings_frame = ttk.Frame(tools_frame)

        # Initialize variables for Auto Fill Text settings
        self.text_color_var = tk.StringVar(value="#000000")  # Default black
        self.color_detect_mode = tk.StringVar(value="dark")  # Default to detect dark
        self.fill_tolerance_var = tk.IntVar(value=80)  # Default tolerance 80
        self.fill_border_var = tk.IntVar(value=3)  # Default border 3px
        self.advanced_detection_var = tk.BooleanVar(value=True)  # Advanced detection of text

        # Toggle button for expanding/collapsing the settings
        self.toggle_settings_btn = ttk.Button(
            tools_frame, text="▼ Auto Fill Settings", command=self.toggle_auto_fill_settings
        )
        self.toggle_settings_btn.pack(fill="x", pady=2)

        # Color detection mode frame
        detect_frame = ttk.LabelFrame(self.auto_fill_settings_frame, text="Detection Mode")
        detect_frame.pack(fill="x", pady=2, padx=5)

        ttk.Radiobutton(detect_frame, text="Detect Dark Colors", variable=self.color_detect_mode, value="dark").pack(
            anchor="w", padx=5, pady=2
        )

        ttk.Radiobutton(detect_frame, text="Detect Light Colors", variable=self.color_detect_mode, value="light").pack(
            anchor="w", padx=5, pady=2
        )

        ttk.Radiobutton(
            detect_frame, text="Select Specific Color", variable=self.color_detect_mode, value="custom"
        ).pack(anchor="w", padx=5, pady=2)

        # Custom text color selection
        color_frame = ttk.Frame(self.auto_fill_settings_frame)
        color_frame.pack(fill="x", pady=2, padx=5)

        ttk.Label(color_frame, text="Text Color:").pack(side=tk.LEFT, padx=(0, 5))

        self.color_button = tk.Button(color_frame, bg=self.text_color_var.get(), width=3, command=self.pick_text_color)
        self.color_button.pack(side=tk.LEFT, padx=5)

        # Add eyedropper button
        eyedropper_btn = ttk.Button(color_frame, text="🔍", width=3, command=self.activate_text_eyedropper)
        eyedropper_btn.pack(side=tk.LEFT, padx=5)

        # Detection options
        detection_frame = ttk.LabelFrame(self.auto_fill_settings_frame, text="Detection Options")
        detection_frame.pack(fill="x", pady=2, padx=5)

        # Advanced detection checkbox
        advanced_checkbox = ttk.Checkbutton(
            detection_frame,
            text="Advanced text detection",
            variable=self.advanced_detection_var,
        )
        advanced_checkbox.pack(anchor="w", padx=5, pady=2)

        # Add explanation text
        ttk.Label(
            detection_frame, text="Helps with thin text detection", font=("TkDefaultFont", 8), foreground="gray"
        ).pack(anchor="w", padx=20, pady=0)

        # Tolerance setting
        tolerance_frame = ttk.Frame(self.auto_fill_settings_frame)
        tolerance_frame.pack(fill="x", pady=2, padx=5)

        ttk.Label(tolerance_frame, text="Tolerance:").pack(side=tk.LEFT, padx=(0, 5))

        tolerance_spinbox = ttk.Spinbox(tolerance_frame, from_=1, to=255, textvariable=self.fill_tolerance_var, width=5)
        tolerance_spinbox.pack(side=tk.LEFT)

        # Border size setting
        border_frame = ttk.Frame(self.auto_fill_settings_frame)
        border_frame.pack(fill="x", pady=2, padx=5)

        ttk.Label(border_frame, text="Border Size:").pack(side=tk.LEFT, padx=(0, 5))

        border_spinbox = ttk.Spinbox(border_frame, from_=0, to=10, textvariable=self.fill_border_var, width=5)
        border_spinbox.pack(side=tk.LEFT)

        # Other tools continue below
        self.text_btn = tk.Button(tools_frame, text="Add Text", command=lambda: self.set_tool(EditorTool.ADD_TEXT))
        self.text_btn.pack(fill="x", pady=2)

        self.image_btn = tk.Button(tools_frame, text="Load Image", command=lambda: self.set_tool(EditorTool.LOAD_IMAGE))
        self.image_btn.pack(fill="x", pady=2)

        # Action buttons separator
        ttk.Separator(self.toolbar, orient=tk.HORIZONTAL).pack(fill="x", padx=5, pady=10)

        # Action buttons
        actions_frame = ttk.LabelFrame(self.toolbar, text="Actions")
        actions_frame.pack(fill="x", padx=5, pady=5)

        self.apply_btn = ttk.Button(actions_frame, text="Apply Changes", command=self.apply_tool)
        self.apply_btn.pack(fill="x", pady=2)

        self.reset_btn = ttk.Button(actions_frame, text="Reset Selection", command=self.reset_selection)
        self.reset_btn.pack(fill="x", pady=2)

        # File operations separator
        ttk.Separator(self.toolbar, orient=tk.HORIZONTAL).pack(fill="x", padx=5, pady=10)

        # File operations
        file_frame = ttk.LabelFrame(self.toolbar, text="File")
        file_frame.pack(fill="x", padx=5, pady=5)

        self.save_btn = ttk.Button(file_frame, text="Save", command=self.save_image)
        self.save_btn.pack(fill="x", pady=2)

        self.save_as_btn = ttk.Button(file_frame, text="Save As...", command=self.save_image_as)
        self.save_as_btn.pack(fill="x", pady=2)

        self.close_btn = ttk.Button(file_frame, text="Close", command=self.close_editor)
        self.close_btn.pack(fill="x", pady=2)

    def setup_bindings(self):
        """Set up mouse and keyboard bindings"""
        # Mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)

        # Mouse wheel for zooming
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)  # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)  # Linux scroll down

        # Keyboard shortcuts
        self.root.bind("<Escape>", lambda e: self.reset_selection())
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Control-s>", lambda e: self.save_image())
        self.root.bind("<Control-S>", lambda e: self.save_image_as())
        self.root.bind("<Control-z>", lambda e: self.undo())

    def set_tool(self, tool):
        """Set the current editing tool"""
        self.current_tool = tool
        self.status_label.config(text=f"Current tool: {tool.name}")
        self.reset_selection()

        # Remove border from previously selected button
        if self.selected_tool_button:
            self.selected_tool_button.config(borderwidth=1, relief="raised")

        # Add border to newly selected button
        if tool == EditorTool.SELECT:
            self.selected_tool_button = self.select_btn
        elif tool == EditorTool.PAN:
            self.selected_tool_button = self.pan_btn
        elif tool == EditorTool.CONTENT_AWARE_FILL:
            self.selected_tool_button = self.fill_btn
        elif tool == EditorTool.AUTO_FILL_TEXT:
            self.selected_tool_button = self.AUTO_FILL_TEXT_btn
        elif tool == EditorTool.ADD_TEXT:
            self.selected_tool_button = self.text_btn
        elif tool == EditorTool.LOAD_IMAGE:
            self.selected_tool_button = self.image_btn

        # Set border on new button
        if self.selected_tool_button:
            self.selected_tool_button.config(borderwidth=2, relief="solid")

    def update_display(self):
        """Update the canvas with the current image"""
        # Apply zoom
        new_size = (int(self.img_width * self.zoom_factor), int(self.img_height * self.zoom_factor))
        self.display_image = self.working_image.resize(new_size, Image.LANCZOS)

        # Convert to PhotoImage
        self.tk_image = ImageTk.PhotoImage(self.display_image)

        # Clear canvas and draw new image
        self.canvas.delete("all")
        self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        # Update canvas scroll region
        self.canvas.config(scrollregion=(0, 0, new_size[0], new_size[1]))

        # Redraw selection if exists
        if self.selection_coords:
            self.draw_selection_rect()

    def draw_selection_rect(self):
        """Draw the selection rectangle"""
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)

        if self.selection_coords:
            x1, y1, x2, y2 = self.selection_coords
            # Convert image coordinates to display coordinates
            x1 = int(x1 * self.zoom_factor)
            y1 = int(y1 * self.zoom_factor)
            x2 = int(x2 * self.zoom_factor)
            y2 = int(y2 * self.zoom_factor)

            self.selection_rect = self.canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=2, dash=(4, 4))

    def on_mouse_down(self, event):
        """Handle mouse button press"""
        # Get canvas coordinates
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

        if self.current_tool == EditorTool.PAN:
            self.pan_start_x = self.canvas.canvasx(event.x)
            self.pan_start_y = self.canvas.canvasy(event.y)
            self.canvas.config(cursor="fleur")

        elif self.current_tool in [
            EditorTool.SELECT,
            EditorTool.CONTENT_AWARE_FILL,
            EditorTool.AUTO_FILL_TEXT,
            EditorTool.LOAD_IMAGE,
            EditorTool.ADD_TEXT,
        ]:
            # Start a new selection
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)
            self.selection_rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2, dash=(4, 4)
            )

    def on_mouse_drag(self, event):
        """Handle mouse drag"""
        # Get current canvas coordinates
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)

        if self.current_tool == EditorTool.PAN:
            # Pan the canvas
            self.canvas.scan_dragto(event.x, event.y, gain=1)

        elif self.current_tool in [
            EditorTool.SELECT,
            EditorTool.CONTENT_AWARE_FILL,
            EditorTool.AUTO_FILL_TEXT,
            EditorTool.LOAD_IMAGE,
            EditorTool.ADD_TEXT,
        ]:
            # Update selection rectangle
            self.canvas.coords(self.selection_rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_mouse_up(self, event):
        """Handle mouse button release"""
        # Get current canvas coordinates
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)

        if self.current_tool == EditorTool.PAN:
            self.canvas.config(cursor="")

        elif self.current_tool in [
            EditorTool.SELECT,
            EditorTool.CONTENT_AWARE_FILL,
            EditorTool.AUTO_FILL_TEXT,
            EditorTool.LOAD_IMAGE,
            EditorTool.ADD_TEXT,
        ]:
            # Finalize selection rectangle
            # Convert display coordinates to image coordinates
            x1 = min(self.start_x, cur_x) / self.zoom_factor
            y1 = min(self.start_y, cur_y) / self.zoom_factor
            x2 = max(self.start_x, cur_x) / self.zoom_factor
            y2 = max(self.start_y, cur_y) / self.zoom_factor

            # Ensure selection is at least 5x5 pixels
            if (x2 - x1) >= 5 and (y2 - y1) >= 5:
                self.selection_coords = (int(x1), int(y1), int(x2), int(y2))

                # Automatically trigger appropriate action based on the selected tool
                if self.current_tool == EditorTool.CONTENT_AWARE_FILL:
                    self.apply_content_aware_fill()  # Auto-apply content-aware fill
                elif self.current_tool == EditorTool.AUTO_FILL_TEXT:  # Add this case
                    self.apply_auto_dark_fill()  # Auto-apply dark fill
                elif self.current_tool == EditorTool.ADD_TEXT:
                    self.add_text_to_selection()
                elif self.current_tool == EditorTool.LOAD_IMAGE:
                    self.load_image_to_selection()
            else:
                # Selection too small, reset
                self.reset_selection()

    def on_mouse_move(self, event):
        """Handle mouse movement"""
        # Update coordinates display
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        image_x = int(canvas_x / self.zoom_factor)
        image_y = int(canvas_y / self.zoom_factor)

        if 0 <= image_x < self.img_width and 0 <= image_y < self.img_height:
            # Get color at this position
            try:
                r, g, b = self.working_image.getpixel((image_x, image_y))[:3]
                self.coords_label.config(text=f"X: {image_x}, Y: {image_y} | RGB: ({r},{g},{b})")
            except:
                self.coords_label.config(text=f"X: {image_x}, Y: {image_y}")
        else:
            self.coords_label.config(text="")

    def on_mouse_wheel(self, event):
        """Handle mouse wheel for zooming"""
        # Determine zoom direction based on event
        if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
            # Zoom in
            self.zoom_in()
        elif event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
            # Zoom out
            self.zoom_out()

    def zoom_in(self):
        """Zoom in by 10%"""
        self.zoom_factor *= 1.1
        self.update_display()

    def zoom_out(self):
        """Zoom out by 10%"""
        self.zoom_factor = max(0.1, self.zoom_factor / 1.1)
        self.update_display()

    def zoom_fit(self):
        """Zoom to fit image in window"""
        # Get canvas size
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # Calculate zoom factor to fit
        width_ratio = canvas_width / self.img_width
        height_ratio = canvas_height / self.img_height

        # Use the smaller ratio to ensure entire image is visible
        self.zoom_factor = min(width_ratio, height_ratio) * 0.95  # 95% to ensure margins
        self.update_display()

    def zoom_actual(self):
        """Reset zoom to 100%"""
        self.zoom_factor = 1.0
        self.update_display()

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))

    def reset_selection(self):
        """Reset the current selection"""
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
            self.selection_rect = None
        self.selection_coords = None

    def apply_tool(self):
        """Apply the current tool to the selected area"""
        if not self.selection_coords:
            tk.messagebox.showinfo("No Selection", "Please select an area first")
            return

        if self.current_tool == EditorTool.CONTENT_AWARE_FILL:
            self.apply_content_aware_fill()
        elif self.current_tool == EditorTool.AUTO_FILL_TEXT:
            self.apply_auto_dark_fill()
        elif self.current_tool == EditorTool.ADD_TEXT:
            self.add_text_to_selection()
        elif self.current_tool == EditorTool.LOAD_IMAGE:
            self.load_image_to_selection()

    def apply_content_aware_fill(self):
        """Apply content-aware fill to the selected area"""
        if not self.selection_coords:
            return

        # Create the enhanced fill dialog
        fill_handler = EnhancedContentAwareFill(self, self.selection_coords)

    def toggle_auto_fill_settings(self):
        """Toggle the visibility of Auto Fill Text settings"""
        if self.auto_fill_settings_visible:
            # Hide settings
            self.auto_fill_settings_frame.pack_forget()
            self.toggle_settings_btn.config(text="▼ Auto Fill Settings")
        else:
            # Show settings
            self.auto_fill_settings_frame.pack(fill="x", pady=2, before=self.text_btn)
            self.toggle_settings_btn.config(text="▲ Auto Fill Settings")

        self.auto_fill_settings_visible = not self.auto_fill_settings_visible

    def pick_text_color(self):
        """Open color picker for text color"""
        color = colorchooser.askcolor(self.text_color_var.get())[1]
        if color:
            self.text_color_var.set(color)
            self.color_button.config(bg=color)

    def apply_auto_dark_fill(self, usegui=False):
        """Apply auto dark content-aware fill to the selected area"""
        if not self.selection_coords:
            return

        if usegui:
            # Create the enhanced fill dialog with explicit auto-apply
            fill_handler = EnhancedContentAwareFill(self, self.selection_coords)

            # Call the auto_apply_dark_fill method directly
            # We need to wait a bit for the dialog to initialize
            fill_handler.fill_dialog.after(100, fill_handler.auto_apply_dark_fill)
        else:
            # Use the windowless implementation
            self.apply_auto_dark_fill_windowless()

    def activate_text_eyedropper(self):
        """Activate the eyedropper tool to sample text color from the image"""
        self.eyedropper_active = True
        self.root.grab_release()  # Allow interaction with main window
        self.canvas.config(cursor="crosshair")
        self.status_label.config(text="Click on text in image to sample color")

        # Store original binding
        self.original_canvas_click = self.canvas.bind("<Button-1>")

        # Create a new binding for color sampling
        def sample_color(event):
            if not self.eyedropper_active:
                return

            # Calculate image coordinates from canvas coordinates
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            image_x = int(canvas_x / self.zoom_factor)
            image_y = int(canvas_y / self.zoom_factor)

            # Check if within image bounds
            if 0 <= image_x < self.img_width and 0 <= image_y < self.img_height:
                # Get color at this position
                try:
                    rgb = self.working_image.getpixel((image_x, image_y))[:3]
                    hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

                    # Update UI
                    self.text_color_var.set(hex_color)
                    self.color_button.config(bg=hex_color)

                    # Switch to custom color mode
                    self.color_detect_mode.set("custom")

                    # Reset cursor and binding
                    self.canvas.config(cursor="")
                    self.eyedropper_active = False

                    # Restore original binding
                    self.canvas.bind("<Button-1>", self.original_canvas_click)

                    self.status_label.config(text=f"Text color sampled: {hex_color}")
                except Exception as e:
                    print(f"Error sampling color: {e}")

        # Set temporary binding
        self.canvas.bind("<Button-1>", sample_color)

    def apply_auto_dark_fill_windowless(self, clear_selection=True):
        """Apply auto text fill without opening the UI"""
        if not self.selection_coords:
            return

        # Get the current selection coordinates
        x1, y1, x2, y2 = self.selection_coords

        try:
            # Show processing status
            self.status_label.config(text="Applying auto fill...")

            # Get selection area
            selection_area = self.working_image.crop((x1, y1, x2, y2))

            # Convert to numpy array for processing
            selection_np = np.array(selection_area)

            # Get color to match based on the selected detection mode
            detection_mode = self.color_detect_mode.get()

            if detection_mode == "dark":
                # Detect darkest pixel
                if len(selection_np.shape) == 3 and selection_np.shape[2] >= 3:
                    luminance = (
                        0.299 * selection_np[:, :, 0] + 0.587 * selection_np[:, :, 1] + 0.114 * selection_np[:, :, 2]
                    )
                    min_y, min_x = np.unravel_index(luminance.argmin(), luminance.shape)
                    target_color = selection_np[min_y, min_x][:3]
                else:
                    min_y, min_x = np.unravel_index(selection_np.argmin(), selection_np.shape)
                    dark_value = selection_np[min_y, min_x]
                    target_color = (dark_value, dark_value, dark_value)

            elif detection_mode == "light":
                # Detect lightest pixel
                if len(selection_np.shape) == 3 and selection_np.shape[2] >= 3:
                    luminance = (
                        0.299 * selection_np[:, :, 0] + 0.587 * selection_np[:, :, 1] + 0.114 * selection_np[:, :, 2]
                    )
                    max_y, max_x = np.unravel_index(luminance.argmax(), luminance.shape)
                    target_color = selection_np[max_y, max_x][:3]
                else:
                    max_y, max_x = np.unravel_index(selection_np.argmax(), selection_np.shape)
                    light_value = selection_np[max_y, max_x]
                    target_color = (light_value, light_value, light_value)

            else:  # custom
                # Use the color from the color picker
                color_hex = self.text_color_var.get()
                # Convert HEX to RGB
                target_color = (int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16))

            # Get the full image in numpy array format
            img_np = np.array(self.working_image)

            # Get settings from UI
            tolerance = self.fill_tolerance_var.get()
            border_size = self.fill_border_var.get()
            use_advanced = self.advanced_detection_var.get()

            # Create mask for inpainting
            mask = np.zeros((self.working_image.height, self.working_image.width), dtype=np.uint8)

            if use_advanced:
                # Advanced text detection approach
                # Extract selection area for processing
                selection_area = img_np[y1:y2, x1:x2]

                # Convert to grayscale for easier processing if it's RGB
                if len(selection_area.shape) == 3:
                    if detection_mode == "dark" or detection_mode == "custom":
                        # For dark text or custom color, convert to grayscale or calculate color distance
                        if detection_mode == "custom":
                            # Calculate distance from target color
                            target_color_np = np.array(target_color)
                            color_diffs = np.sum(np.abs(selection_area - target_color_np.reshape(1, 1, 3)), axis=2)
                            gray_selection = color_diffs.astype(np.uint8)
                        else:
                            # Convert RGB to grayscale using standard formula
                            gray_selection = np.dot(selection_area[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
                    else:  # light mode
                        # Invert to make light text appear dark
                        gray_selection = 255 - np.dot(selection_area[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
                else:
                    # Already grayscale
                    gray_selection = selection_area.copy()
                    if detection_mode == "light":
                        gray_selection = 255 - gray_selection  # Invert for light text

                # Apply adaptive thresholding to better separate text from background
                binary_selection = cv2.adaptiveThreshold(
                    gray_selection,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV,
                    11,  # Block size
                    2,  # Constant subtracted from mean
                )

                # Apply morphological operations to improve text detection
                # Create a small kernel for thin text
                kernel = np.ones((2, 2), np.uint8)

                # Open operation (erosion followed by dilation) to remove noise
                opened = cv2.morphologyEx(binary_selection, cv2.MORPH_OPEN, kernel)

                # Additional dilate to ensure thin text is fully covered
                selection_mask = cv2.dilate(opened, kernel, iterations=1)

                # Use tolerance as a threshold for final adjustment
                if tolerance > 100:  # If high tolerance, apply additional dilation
                    extra_kernel = np.ones((tolerance // 50 + 1, tolerance // 50 + 1), np.uint8)
                    selection_mask = cv2.dilate(selection_mask, extra_kernel, iterations=1)

                # Place selection mask into the full mask
                mask[y1:y2, x1:x2] = selection_mask

            else:
                # Simple color-based detection approach
                # Handle different image types
                if len(img_np.shape) == 2:  # Grayscale
                    img_rgb = np.stack([img_np, img_np, img_np], axis=2)
                elif len(img_np.shape) == 3:
                    if img_np.shape[2] == 4:  # RGBA
                        img_rgb = img_np[:, :, :3]
                    elif img_np.shape[2] == 3:  # RGB
                        img_rgb = img_np
                    else:
                        raise ValueError(f"Unexpected image format with {img_np.shape[2]} channels")
                else:
                    raise ValueError(f"Unexpected image shape: {img_np.shape}")

                # Calculate color differences ONLY in the selection area
                # Initialize the color mask with zeros
                color_mask = np.zeros((self.working_image.height, self.working_image.width), dtype=np.uint8)

                # Calculate color differences for the selection area
                selection_rgb = img_rgb[y1:y2, x1:x2]
                color_diffs = np.sum(np.abs(selection_rgb - np.array(target_color)), axis=2)
                selection_color_mask = (color_diffs <= tolerance).astype(np.uint8) * 255

                # Place the selection color mask into the full mask
                color_mask[y1:y2, x1:x2] = selection_color_mask

                # Set the mask
                mask = color_mask

            # Apply border expansion if needed
            if border_size > 0:
                kernel = np.ones((border_size * 2 + 1, border_size * 2 + 1), np.uint8)
                mask = cv2.dilate(mask, kernel, iterations=1)

            # Count pixels in mask for feedback
            pixel_count = np.sum(mask > 0)

            # Apply OpenCV inpainting (using Telea algorithm)
            img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            result = cv2.inpaint(img_cv, mask, 5, cv2.INPAINT_TELEA)

            # Convert back to RGB and PIL format
            result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
            result_img = Image.fromarray(result_rgb)

            # Update working image
            self.working_image = result_img

            # Update UI
            self.update_display()

            if clear_selection:
                self.reset_selection()

            # Update status with color info
            color_hex = f"#{target_color[0]:02x}{target_color[1]:02x}{target_color[2]:02x}"
            detection_type = "advanced" if use_advanced else "simple"
            self.status_label.config(
                text=f"Auto fill applied: {pixel_count} pixels matched (color: {color_hex}, tolerance: {tolerance}, border: {border_size}px, {detection_type} detection)"
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            self.status_label.config(text=f"Error in auto fill: {str(e)}")

    def add_text_to_selection(self):
        """Add text to the selected area with interactive controls"""
        if not self.selection_coords:
            return

        # Create font directory if it doesn't exist
        fonts_dir = Path("./fonts")
        fonts_dir.mkdir(exist_ok=True)

        # Check for fonts in the directory
        font_files = list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))

        # Combine custom and system fonts, use set to remove duplicates
        all_fonts = list(set([f.name for f in font_files]))
        all_fonts.sort()

        # If no fonts found, add a default
        if not all_fonts:
            all_fonts = ["default"]

        # Create a toplevel window for text entry
        text_window = tk.Toplevel(self.root)
        text_window.title("Add Text")
        text_window.geometry("500x500")
        text_window.transient(self.root)
        text_window.grab_set()

        # Get selection coordinates for initial position
        x1, y1, x2, y2 = self.selection_coords
        center_x = int((x1 + x2) / 2)
        center_y = int((y1 + y2) / 2)

        # Variables for text properties
        text_var = tk.StringVar(value="Enter text here")
        size_var = tk.IntVar(value=24)
        font_var = tk.StringVar(value=all_fonts[0] if all_fonts else "default")
        color_var = tk.StringVar(value="#FFFFFF")
        pos_x_var = tk.IntVar(value=center_x)
        pos_y_var = tk.IntVar(value=center_y)
        align_var = tk.StringVar(value="center")

        # Live preview variables
        preview_text = None
        preview_img = None

        # Function to update the text preview
        def update_preview(*args):
            nonlocal preview_text, preview_img

            # Clear previous preview
            if preview_text:
                self.canvas.delete(preview_text)

            # Get current text properties
            text = text_text.get("1.0", tk.END).strip()
            size = size_var.get()
            font_name = font_var.get()
            color_value = color_var.get()
            pos_x = pos_x_var.get()
            pos_y = pos_y_var.get()
            alignment = align_var.get()

            # Create a temporary image for preview
            temp_img = self.working_image.copy()
            draw = ImageDraw.Draw(temp_img)

            # Try to use the selected font
            font_obj = None
            try:
                # Check custom fonts directory first
                for font_path in fonts_dir.glob(f"{font_name}*"):
                    font_obj = ImageFont.truetype(str(font_path), size)
                    break

                # If not found in custom directory, check system paths
                if not font_obj:
                    for sys_font in system_fonts:
                        if font_name in sys_font.name:
                            font_obj = ImageFont.truetype(str(sys_font), size)
                            break
            except:
                pass

            # Fall back to default if needed
            if not font_obj:
                try:
                    # Try some common system fonts
                    for system_font in ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "times.ttf", "verdana.ttf"]:
                        try:
                            font_obj = ImageFont.truetype(system_font, size)
                            break
                        except:
                            pass
                except:
                    font_obj = ImageFont.load_default()

            # Handle multiline text
            lines = text.split("\n")
            y_offset = 0

            for line in lines:
                if not line.strip():  # Skip empty lines but add spacing
                    y_offset += size
                    continue

                # Get text size for this line
                try:
                    # For older Pillow versions
                    line_width, line_height = draw.textsize(line, font=font_obj)
                except:
                    # For newer Pillow versions
                    try:
                        text_bbox = font_obj.getbbox(line)
                        line_width, line_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
                    except:
                        # Fallback estimation
                        line_width, line_height = len(line) * size // 2, size

                # Calculate x position based on alignment
                if alignment == "left":
                    text_x = pos_x
                elif alignment == "right":
                    text_x = pos_x - line_width
                else:  # center
                    text_x = pos_x - (line_width // 2)

                # Draw text on image
                draw.text((text_x, pos_y + y_offset), line, fill=color_value, font=font_obj)
                y_offset += line_height

            # Update the display
            new_size = (int(self.img_width * self.zoom_factor), int(self.img_height * self.zoom_factor))
            display_img = temp_img.resize(new_size, Image.LANCZOS)
            preview_img = ImageTk.PhotoImage(display_img)

            # Update canvas
            self.canvas.itemconfig(self.image_id, image=preview_img)

        # Function to apply text and close
        def apply_text():
            # Get text properties
            text = text_text.get("1.0", tk.END).strip()
            size = size_var.get()
            font_name = font_var.get()
            color_value = color_var.get()
            pos_x = pos_x_var.get()
            pos_y = pos_y_var.get()
            alignment = align_var.get()

            if not text.strip():
                text_window.destroy()
                return

            # Create drawing context
            draw = ImageDraw.Draw(self.working_image)

            # Try to use the selected font
            font_obj = None
            try:
                # Check custom fonts directory first
                for font_path in fonts_dir.glob(f"{font_name}*"):
                    font_obj = ImageFont.truetype(str(font_path), size)
                    break

                # If not found in custom directory, check system paths
                if not font_obj:
                    for sys_font in system_fonts:
                        if font_name in sys_font.name:
                            font_obj = ImageFont.truetype(str(sys_font), size)
                            break
            except:
                pass

            # Fall back to default if needed
            if not font_obj:
                try:
                    # Try some common system fonts
                    for system_font in ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "times.ttf", "verdana.ttf"]:
                        try:
                            font_obj = ImageFont.truetype(system_font, size)
                            break
                        except:
                            pass
                except:
                    font_obj = ImageFont.load_default()

            # Handle multiline text
            lines = text.split("\n")
            y_offset = 0

            for line in lines:
                if not line.strip():  # Skip empty lines but add spacing
                    y_offset += size
                    continue

                # Get text size for this line
                try:
                    # For older Pillow versions
                    line_width, line_height = draw.textsize(line, font=font_obj)
                except:
                    # For newer Pillow versions
                    try:
                        text_bbox = font_obj.getbbox(line)
                        line_width, line_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
                    except:
                        # Fallback estimation
                        line_width, line_height = len(line) * size // 2, size

                # Calculate x position based on alignment
                if alignment == "left":
                    text_x = pos_x
                elif alignment == "right":
                    text_x = pos_x - line_width
                else:  # center
                    text_x = pos_x - (line_width // 2)

                # Draw text on image
                draw.text((text_x, pos_y + y_offset), line, fill=color_value, font=font_obj)
                y_offset += line_height

            # Update display and close window
            self.update_display()
            self.reset_selection()
            self.status_label.config(text="Text added")
            text_window.destroy()

        # Function to cancel
        def cancel_text():
            self.update_display()  # Reset to original image
            text_window.destroy()

        # Function to pick color
        def pick_color():
            color = colorchooser.askcolor(color_var.get())[1]
            if color:
                color_var.set(color)
                color_button.config(bg=color)
                update_preview()

        # Create the text entry UI
        frame = ttk.Frame(text_window, padding=10)
        frame.pack(fill="both", expand=True)

        # Add UI elements
        ttk.Label(frame, text="Text:").grid(row=0, column=0, sticky="nw", pady=5)
        text_frame = ttk.Frame(frame)
        text_frame.grid(row=0, column=1, columnspan=2, sticky="we", pady=5)
        text_text = tk.Text(text_frame, wrap="word", width=30, height=5)
        text_text.insert("1.0", "Enter text here")
        text_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scroll = ttk.Scrollbar(text_frame, command=text_text.yview)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text_text.config(yscrollcommand=text_scroll.set)

        ttk.Label(frame, text="Size:").grid(row=1, column=0, sticky="w", pady=5)
        size_scale = ttk.Scale(frame, from_=8, to=72, variable=size_var, orient="horizontal")
        size_scale.grid(row=1, column=1, sticky="we", pady=5)
        ttk.Label(frame, textvariable=size_var).grid(row=1, column=2, sticky="w", pady=5)

        ttk.Label(frame, text="Font:").grid(row=2, column=0, sticky="w", pady=5)
        font_combo = ttk.Combobox(frame, textvariable=font_var, values=all_fonts, state="readonly")
        font_combo.grid(row=2, column=1, columnspan=2, sticky="we", pady=5)

        ttk.Label(frame, text="Color:").grid(row=3, column=0, sticky="w", pady=5)
        color_frame = ttk.Frame(frame)
        color_frame.grid(row=3, column=1, sticky="w", pady=5)
        color_entry = ttk.Entry(color_frame, textvariable=color_var, width=10)
        color_entry.pack(side=tk.LEFT)
        color_button = tk.Button(color_frame, bg=color_var.get(), width=3, command=pick_color)
        color_button.pack(side=tk.LEFT, padx=5)

        # Text position controls
        pos_frame = ttk.LabelFrame(frame, text="Text Position")
        pos_frame.grid(row=4, column=0, columnspan=3, sticky="we", pady=10)

        ttk.Label(pos_frame, text="X:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        x_spinbox = ttk.Spinbox(pos_frame, from_=0, to=self.img_width, textvariable=pos_x_var, width=5, increment=1)
        x_spinbox.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(pos_frame, text="Y:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        y_spinbox = ttk.Spinbox(pos_frame, from_=0, to=self.img_height, textvariable=pos_y_var, width=5, increment=1)
        y_spinbox.grid(row=0, column=3, sticky="w", padx=5, pady=5)

        # Text alignment controls
        align_frame = ttk.LabelFrame(frame, text="Text Alignment")
        align_frame.grid(row=5, column=0, columnspan=3, sticky="we", pady=10)

        ttk.Radiobutton(align_frame, text="Left", variable=align_var, value="left").pack(side=tk.LEFT, padx=20)
        ttk.Radiobutton(align_frame, text="Center", variable=align_var, value="center").pack(side=tk.LEFT, padx=20)
        ttk.Radiobutton(align_frame, text="Right", variable=align_var, value="right").pack(side=tk.LEFT, padx=20)

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=6, column=0, columnspan=3, pady=10)
        ttk.Button(button_frame, text="Apply", command=apply_text).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel_text).pack(side=tk.LEFT, padx=5)

        # Bind events for live preview
        text_text.bind("<KeyRelease>", lambda e: update_preview())
        size_var.trace_add("write", update_preview)
        font_var.trace_add("write", update_preview)
        color_var.trace_add("write", update_preview)
        pos_x_var.trace_add("write", update_preview)
        pos_y_var.trace_add("write", update_preview)
        align_var.trace_add("write", update_preview)

        # Initial preview
        update_preview()

        # Focus on text entry
        text_text.focus_set()
        text_text.tag_add("sel", "1.0", "end")

    def load_image_to_selection(self):
        """Load an image into the selected area"""
        if not self.selection_coords:
            return

        # Open file dialog
        file_path = filedialog.askopenfilename(
            title="Select Image", filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif"), ("All files", "*.*")]
        )

        if not file_path:
            self.reset_selection()
            return

        try:
            # Load the image
            overlay_img = Image.open(file_path)

            # Get selection dimensions
            x1, y1, x2, y2 = self.selection_coords
            sel_width = x2 - x1
            sel_height = y2 - y1

            # Resize overlay image to fit selection
            overlay_img = overlay_img.resize((sel_width, sel_height), Image.LANCZOS)

            # Paste overlay image onto working image
            self.working_image.paste(overlay_img, (x1, y1))

            # Update display
            self.update_display()
            self.reset_selection()
            self.status_label.config(text=f"Image inserted from {Path(file_path).name}")
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to insert image: {str(e)}")

    def save_image(self):
        """Save the current image and close the editor"""
        try:
            self.working_image.save(self.image_path)
            self.status_label.config(text=f"Saved to {self.image_path}")

            # Call the callback if it exists
            if self.on_save_callback:
                self.on_save_callback(self.image_path)

            # Ask user if they want to close the editor
            if tk.messagebox.askyesno("Save Complete", "Image saved successfully. Close the editor?"):
                self.root.destroy()

        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to save image: {str(e)}")

    def save_image_as(self):
        """Save the current image with a new name"""
        file_path = filedialog.asksaveasfilename(
            title="Save Image As",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
        )

        if file_path:
            try:
                self.working_image.save(file_path)
                self.image_path = file_path
                self.root.title(f"Card Editor - {Path(file_path).name}")
                self.status_label.config(text=f"Saved to {file_path}")
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to save image: {str(e)}")

    def undo(self):
        """Undo the last operation (placeholder - would need to implement a history stack)"""
        tk.messagebox.showinfo("Undo", "Undo functionality not implemented yet")

    def close_editor(self):
        """Close the editor"""
        if tk.messagebox.askyesno("Close", "Close the editor? Unsaved changes will be lost."):
            self.root.destroy()


# Function to create and launch the editor
def launch_editor(image_path, on_save_callback=None):
    """
    Launch the card editor

    Args:
        image_path: Path to the image to edit
        on_save_callback: Function to call when save is complete (optional)
    """
    root = tk.Toplevel()
    editor = CardEditor(root, image_path)

    # Store the callback
    editor.on_save_callback = on_save_callback

    return editor


# Standalone test when run directly
if __name__ == "__main__":
    # Ask for an image to edit
    image_path = filedialog.askopenfilename(
        title="Select Image to Edit", filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
    )

    if image_path:
        root = tk.Tk()
        editor = CardEditor(root, image_path)
        root.mainloop()
