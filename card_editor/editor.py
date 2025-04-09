"""
Main CardEditor class implementation
"""

import math
import os
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from card_editor.history import HistoryManager
from card_editor.models import CardPreset, EditorTool
from card_editor.presets import (
    add_preset,
    load_preset_from_file,
    load_presets,
    remove_preset,
    rename_preset,
    save_all_presets,
    save_preset,
)
from card_editor.tools import add_text_to_selection, apply_auto_dark_fill_windowless, load_image_to_selection
from card_editor.ui import create_presets_panel, create_toolbar, display_image, draw_selection_rect


class CardEditor:
    """Main class for the card editor application"""

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

        self.fill_iterations_var = tk.IntVar(value=1)

        # Image metadata
        self.img_width, self.img_height = self.working_image.size

        # Initialize history manager
        self.history = HistoryManager(max_history=5)

        # Add initial state
        self.history.add_state(self.working_image, "Initial state")

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
        self.current_tool = EditorTool.AUTO_FILL_TEXT
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

        # Initialize variables for Auto Fill Text settings
        self.text_color_var = tk.StringVar(value="#000000")  # Default black
        self.color_detect_mode = tk.StringVar(value="dark")  # Default to detect dark
        self.advanced_detection_var = tk.BooleanVar(value=True)  # Advanced detection of text

        # Presets variables
        self.presets = []
        self.current_preset = None
        self.load_presets()  # Load presets from file if available

        # Set up event bindings
        self.setup_bindings()

        # Display the image
        self.update_display()

        # Initialize with AUTO_FILL_TEXT tool selected
        self.set_tool(EditorTool.AUTO_FILL_TEXT)

    def create_toolbar(self):
        """Create the toolbar with editing tools"""
        self.toolbar = create_toolbar(self)

    def create_presets_panel(self):
        """Create the presets panel on the right side"""
        self.presets_panel = create_presets_panel(self)

    def load_presets(self):
        """Load presets from presets folder"""
        try:
            self.presets = load_presets()
            self.update_presets_list()
            self.status_label.config(text="Presets loaded")
        except Exception as e:
            # Create default preset on error
            default_preset = CardPreset(name="Normal mtg card")
            self.presets = [default_preset]
            self.update_presets_list()
            messagebox.showwarning("Error", f"Failed to load presets: {str(e)}\nUsing default preset.")

    def load_presets_file(self):
        """Load a single preset from a user-selected file"""
        file_path = filedialog.askopenfilename(
            title="Load Preset", filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )

        if not file_path:
            return

        try:
            new_preset = load_preset_from_file(file_path)
            if not new_preset:
                return

            # Check if a preset with this name already exists
            existing_index = None
            for i, preset in enumerate(self.presets):
                if preset.name == new_preset.name:
                    existing_index = i
                    break

            if existing_index is not None:
                # Ask user if they want to replace the existing preset
                if messagebox.askyesno(
                    "Duplicate Name", f"A preset named '{new_preset.name}' already exists. Replace it?"
                ):
                    self.presets[existing_index] = new_preset
                    # Save the updated preset
                    save_preset(new_preset)
                else:
                    return
            else:
                # Add the new preset
                self.presets.append(new_preset)
                # Save the new preset
                save_preset(new_preset)

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
            messagebox.showerror("Error", f"Failed to load preset: {str(e)}")

    def save_presets(self):
        """Save all presets to files"""
        if not self.presets:
            messagebox.showinfo("No Presets", "No presets to save")
            return

        # Save all presets
        success_count = save_all_presets(self.presets)
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

    def add_preset(self):
        """Add a new preset"""
        new_preset = add_preset(self.presets, self.root)
        if new_preset:
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
            messagebox.showinfo("No Selection", "Please select a preset to remove")
            return

        index = selection[0]
        success = remove_preset(self.presets, index, self.root)

        if success:
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
            messagebox.showinfo("No Selection", "Please select a preset to rename")
            return

        index = selection[0]
        success = rename_preset(self.presets, index, self.root)

        if success:
            # Update UI
            self.update_presets_list()
            self.presets_list.selection_set(index)

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

    def zone_checkbox_changed(self):
        """Handle zone checkbox state changes"""
        # This function is called when any zone checkbox is toggled
        pass

    def set_preset_zone(self, zone_type):
        """Set the zone coordinates from the current selection"""
        if not self.current_preset:
            messagebox.showinfo("No Preset", "Please select or create a preset first")
            return

        if not self.selection_coords:
            messagebox.showinfo("No Selection", "Please make a selection on the image first")
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
        save_preset(self.current_preset)

    def apply_preset_zone(self, zone_type):
        """Apply the selected zone from the preset"""
        if not self.current_preset:
            print("No current preset")
            messagebox.showinfo("No Preset", "Please select a preset first")
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

        if tool == EditorTool.AUTO_FILL_TEXT:
            self.selected_tool_button = self.AUTO_FILL_TEXT_btn
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
        elif tool == EditorTool.AUTO_FILL_TEXT:
            self.apply_auto_dark_fill()

    def process_all_zones(self):
        """Process all selected zones in sequence"""
        if not self.current_preset:
            messagebox.showinfo("No Preset", "Please select a preset first")
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
            messagebox.showinfo("No Zones Selected", "Please select at least one zone to process")
            return

        # Process each zone in sequence
        for zone_type, tool in zones_to_process:
            # Apply the zone
            self.apply_preset_zone(zone_type)

            # Small delay to allow for user interaction if needed
            self.root.update()

        self.status_label.config(text="All selected zones processed")

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
        if tool == EditorTool.AUTO_FILL_TEXT:
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
        display_image(self)

    def draw_selection_rect(self):
        """Draw the selection rectangle"""
        draw_selection_rect(self)

    def on_mouse_down(self, event):
        """Handle mouse button press"""
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

        if self.current_tool == EditorTool.PAN:
            self.pan_start_x = self.start_x
            self.pan_start_y = self.start_y
            self.canvas.config(cursor="fleur")

        elif self.current_tool in [EditorTool.AUTO_FILL_TEXT, EditorTool.LOAD_IMAGE, EditorTool.ADD_TEXT]:
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)

            if self.current_tool == EditorTool.AUTO_FILL_TEXT and hasattr(self, "selection_mode_var"):
                selection_mode = self.selection_mode_var.get()

                if selection_mode == "spot_healing":
                    # Initialize brush tracking variables
                    self.brush_points = []
                    self.brush_strokes = []
                    self.last_brush_point = (self.start_x, self.start_y)
                    brush_radius = int(self.brush_size_var.get() * self.zoom_factor)

                    # Create initial brush stroke
                    initial_stroke = self.canvas.create_oval(
                        self.start_x - brush_radius,
                        self.start_y - brush_radius,
                        self.start_x + brush_radius,
                        self.start_y + brush_radius,
                        outline="red",
                        width=2,
                    )
                    self.brush_strokes.append(initial_stroke)
                    self.brush_points.append((self.start_x / self.zoom_factor, self.start_y / self.zoom_factor))
                    return

            # Default rectangle initialization
            self.selection_rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2, dash=(4, 4)
            )

    def on_mouse_drag(self, event):
        """Handle mouse drag"""
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)

        if self.current_tool == EditorTool.PAN:
            self.canvas.scan_dragto(event.x, event.y, gain=1)

        elif self.current_tool in [EditorTool.AUTO_FILL_TEXT, EditorTool.LOAD_IMAGE, EditorTool.ADD_TEXT]:
            if self.current_tool == EditorTool.AUTO_FILL_TEXT and hasattr(self, "selection_mode_var"):
                selection_mode = self.selection_mode_var.get()

                if selection_mode == "spot_healing":
                    brush_radius = int(self.brush_size_var.get() * self.zoom_factor)
                    stroke_width = brush_radius * 2

                    # Create connecting line between points
                    line = self.canvas.create_line(
                        self.last_brush_point[0],
                        self.last_brush_point[1],
                        cur_x,
                        cur_y,
                        fill="red",
                        width=stroke_width,
                        capstyle=tk.ROUND,
                        smooth=True,
                    )
                    self.brush_strokes.append(line)

                    # Create new brush circle
                    circle = self.canvas.create_oval(
                        cur_x - brush_radius,
                        cur_y - brush_radius,
                        cur_x + brush_radius,
                        cur_y + brush_radius,
                        outline="red",
                        width=2,
                    )
                    self.brush_strokes.append(circle)

                    # Update tracking variables
                    self.last_brush_point = (cur_x, cur_y)
                    self.brush_points.append((cur_x / self.zoom_factor, cur_y / self.zoom_factor))
                    return

            # Default rectangle update
            self.canvas.coords(self.selection_rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_mouse_up(self, event):
        """Handle mouse button release"""
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)

        if self.current_tool == EditorTool.PAN:
            self.canvas.config(cursor="")

        elif self.current_tool in [EditorTool.AUTO_FILL_TEXT, EditorTool.LOAD_IMAGE, EditorTool.ADD_TEXT]:
            # Check if spot healing mode is active for the Auto Fill Text tool
            is_spot_healing = False
            if self.current_tool == EditorTool.AUTO_FILL_TEXT and hasattr(self, "selection_mode_var"):
                selection_mode = self.selection_mode_var.get()
                if selection_mode == "spot_healing":
                    is_spot_healing = True

            # Handle Spot Healing selection finalization
            if is_spot_healing and hasattr(self, "brush_points") and self.brush_points:
                print("\n--- DEBUG: Spot Healing Mouse Up ---") # Add a clear marker

                # Clean up temporary visual brush strokes drawn on canvas
                for stroke in self.brush_strokes:
                    self.canvas.delete(stroke)
                self.brush_strokes = []

                # --- Calculate final selection area based on brush path ---

                # Get all center points of the brush path in IMAGE coordinates
                points_x = [p[0] for p in self.brush_points]
                points_y = [p[1] for p in self.brush_points]

                if not points_x or not points_y:
                    print("DEBUG: No brush points recorded.")
                    self.reset_selection() # Clear any partial selection
                    return # Exit if no points

                # Find the min/max extent of the brush path's center
                center_x1 = min(points_x)
                center_y1 = min(points_y)
                center_x2 = max(points_x)
                center_y2 = max(points_y)

                print(f"DEBUG: Center bounds (Image Coords): ({center_x1:.2f}, {center_y1:.2f}) to ({center_x2:.2f}, {center_y2:.2f})")
                print(f"DEBUG: Number of points: {len(self.brush_points)}")

                # Get base brush size (diameter) and radius in IMAGE coordinates
                # Assumes self.brush_size_var stores the diameter set in the UI
                brush_size_image = self.brush_size_var.get()
                brush_radius_image = brush_size_image

                # Account for the visual thickness of the preview outline
                # The width used in create_oval for the visual feedback circle
                preview_outline_width = 2
                # This width is in CANVAS pixels, find the extra radius it adds visually
                extra_canvas_radius = preview_outline_width / 2.0
                # Convert this extra visual radius to IMAGE space using the zoom factor
                extra_image_radius = extra_canvas_radius / self.zoom_factor
                # Calculate the effective radius needed to encompass the visual preview
                effective_radius_image = brush_radius_image + extra_image_radius

                print(f"DEBUG: Brush Size Var (UI Diameter?): {brush_size_image}")
                print(f"DEBUG: Calculated Image Radius: {brush_radius_image:.2f}")
                print(f"DEBUG: Extra Image Radius (for outline {preview_outline_width}px): {extra_image_radius:.2f}")
                print(f"DEBUG: Effective Image Radius for Expansion: {effective_radius_image:.2f}")

                # Expand the center bounds by the effective radius to get the full selection area
                x1_float = center_x1 - effective_radius_image
                y1_float = center_y1 - effective_radius_image
                x2_float = center_x2 + effective_radius_image
                y2_float = center_y2 + effective_radius_image

                print(f"DEBUG: Expanded bounds (float, Image Coords): ({x1_float:.2f}, {y1_float:.2f}) to ({x2_float:.2f}, {y2_float:.2f})")

                # Convert final coordinates to integers, ensuring coverage
                x1 = math.floor(x1_float)
                y1 = math.floor(y1_float)
                x2 = math.ceil(x2_float)
                y2 = math.ceil(y2_float)

                print(f"DEBUG: Final Selection Coords (int, Image Coords): ({x1}, {y1}, {x2}, {y2})")

                # Ensure coordinates are within the actual image dimensions
                img_w = self.working_image.width
                img_h = self.working_image.height
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(img_w, x2)
                y2 = min(img_h, y2)

                # Store the final selection coordinates (in IMAGE space)
                self.selection_coords = (x1, y1, x2, y2)
                print(f"DEBUG: Clamped Selection Coords (Image Coords): {self.selection_coords}")

                # --- Draw the final selection rectangle on the canvas ---
                if self.selection_rect:
                    self.canvas.delete(self.selection_rect) # Remove previous rectangle if any

                # Convert final IMAGE coordinates back to CANVAS coordinates for drawing
                canvas_x1 = x1 * self.zoom_factor
                canvas_y1 = y1 * self.zoom_factor
                canvas_x2 = x2 * self.zoom_factor
                canvas_y2 = y2 * self.zoom_factor

                print(f"DEBUG: Final Rectangle Draw Coords (Canvas Coords): ({canvas_x1:.2f}, {canvas_y1:.2f}) to ({canvas_x2:.2f}, {canvas_y2:.2f})")
                print("--- END DEBUG ---")

                # Create the visual rectangle on the canvas
                self.selection_rect = self.canvas.create_rectangle(
                    canvas_x1,
                    canvas_y1,
                    canvas_x2,
                    canvas_y2,
                    outline="red",
                    width=2,        # Visual width of the selection rectangle itself
                    dash=(4, 4),    # Make it dashed
                )

                # Update status bar
                self.status_label.config(
                    text="Selection created from brush strokes. Press 'Apply Changes' to fill."
                )

                # Reset brush tracking points for the next stroke
                self.brush_points = []
                self.last_brush_point = None

                # IMPORTANT: Return here to prevent falling through to default rectangle logic
                return

            # --- Default Rectangle Selection Logic ---
            # This part runs if the tool is not AutoFill+SpotHealing,
            # or if SpotHealing was selected but no points were drawn.
            print("DEBUG: Reached default rectangle finalization logic.")

            # Use the stored start and current mouse coordinates (already in canvas space)
            x1_canvas = min(self.start_x, cur_x)
            y1_canvas = min(self.start_y, cur_y)
            x2_canvas = max(self.start_x, cur_x)
            y2_canvas = max(self.start_y, cur_y)

            # Convert the final canvas rectangle coordinates to image coordinates
            x1_img = x1_canvas / self.zoom_factor
            y1_img = y1_canvas / self.zoom_factor
            x2_img = x2_canvas / self.zoom_factor
            y2_img = y2_canvas / self.zoom_factor

            # Check if the resulting rectangle is large enough
            min_selection_size = 5 # Minimum width/height in pixels
            if (x2_img - x1_img) >= min_selection_size and (y2_img - y1_img) >= min_selection_size:
                # Store the final selection coordinates (integer, image space)
                self.selection_coords = (int(x1_img), int(y1_img), int(x2_img), int(y2_img))
                print(f"DEBUG: Default Rectangle Selection Coords: {self.selection_coords}")

                # Update the visual rectangle on the canvas to match the final coordinates
                if self.selection_rect:
                     self.canvas.coords(self.selection_rect, canvas_x1, canvas_y1, canvas_x2, canvas_y2)
                else:
                    # This case should ideally not happen if on_mouse_down created it
                     self.selection_rect = self.canvas.create_rectangle(
                         canvas_x1, canvas_y1, canvas_x2, canvas_y2,
                         outline="red", width=2, dash=(4, 4)
                     )


                # Trigger actions or update status based on the current tool (if not Spot Healing)
                if self.current_tool == EditorTool.AUTO_FILL_TEXT and not is_spot_healing:
                    self.status_label.config(text="Rectangular selection made. Press 'Apply Changes' to fill.")
                    # Optionally auto-apply here if desired for rectangle mode:
                    # self.apply_auto_dark_fill()
                elif self.current_tool == EditorTool.ADD_TEXT:
                    self.add_text_to_selection() # Assume this function uses self.selection_coords
                elif self.current_tool == EditorTool.LOAD_IMAGE:
                    self.load_image_to_selection() # Assume this function uses self.selection_coords

            else:
                # If selection was too small or invalid, clear it
                print("DEBUG: Default rectangle selection too small, resetting.")
                self.reset_selection() # reset_selection should handle deleting the rect and coords


        # --- Reset states for tools that need it on mouse up ---
        if self.current_tool == EditorTool.PAN:
            pass # Cursor already reset at the start of the function

        # Reset start coordinates for the next action
        self.start_x = None
        self.start_y = None

    # Make sure you have a reset_selection method like this:
    def reset_selection(self):
        """Clears the current selection coordinates and removes the visual rectangle."""
        if hasattr(self, 'selection_rect') and self.selection_rect:
            self.canvas.delete(self.selection_rect)
        self.selection_rect = None
        self.selection_coords = None
        # Also clear brush points if they exist from an interrupted action
        if hasattr(self, 'brush_points'):
            self.brush_points = []
            self.last_brush_point = None
            # Delete any leftover visual strokes if necessary
            if hasattr(self, 'brush_strokes'):
                 for stroke in self.brush_strokes:
                      try:
                           self.canvas.delete(stroke)
                      except tk.TclError:
                           pass # Ignore if item already deleted
                 self.brush_strokes = []

        print("DEBUG: Selection Reset")


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

    def reset_selection(self):
        """Reset the current selection"""
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
            self.selection_rect = None
        self.selection_coords = None

    def apply_tool(self):
        """Apply the current tool to the selected area"""
        if not self.selection_coords:
            messagebox.showinfo("No Selection", "Please select an area first")
            return

        if self.current_tool == EditorTool.AUTO_FILL_TEXT:
            self.apply_auto_dark_fill()
        elif self.current_tool == EditorTool.ADD_TEXT:
            self.add_text_to_selection()
        elif self.current_tool == EditorTool.LOAD_IMAGE:
            self.load_image_to_selection()

    def apply_auto_dark_fill(self, use_gui=False):
        """
        Apply auto dark content-aware fill to the selected area

        Args:
            use_gui: Whether to use the GUI or the windowless implementation
        """
        if not self.selection_coords:
            return

        # Record state before applying auto fill
        if hasattr(self, "record_state"):
            self.record_state("Before auto fill text")

        # Use the windowless implementation with specified iterations
        iterations = self.fill_iterations_var.get()
        apply_auto_dark_fill_windowless(self, clear_selection=True, iterations=iterations)

    def add_text_to_selection(self):
        """Add text to the selected area with interactive controls"""
        add_text_to_selection(self)

    def load_image_to_selection(self):
        """Load an image into the selected area"""
        load_image_to_selection(self)

    def save_image(self):
        """Save the current image and close the editor"""
        try:
            self.working_image.save(self.image_path)
            self.status_label.config(text=f"Saved to {self.image_path}")

            # Call the callback if it exists
            if self.on_save_callback:
                self.on_save_callback(self.image_path)

            # Ask user if they want to close the editor
            if messagebox.askyesno("Save Complete", "Image saved successfully. Close the editor?"):
                self.root.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save image: {str(e)}")

    def close_editor(self):
        self.root.destroy()

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
                messagebox.showerror("Error", f"Failed to save image: {str(e)}")

    def undo(self, event=None):
        """Undo the last operation"""
        if not self.history.can_undo():
            self.status_label.config(text="Nothing to undo")
            return

        # Get the previous state
        previous_state, description = self.history.undo()

        # Restore the image
        self.working_image = previous_state
        self.img_width, self.img_height = self.working_image.size

        # Update the display
        self.update_display()
        self.status_label.config(text=f"Undone: {description}")

    def record_state(self, description):
        """
        Record the current state in history

        Args:
            description: Description of the operation
        """
        self.history.add_state(self.working_image, description)


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
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    image_path = filedialog.askopenfilename(
        title="Select Image to Edit", filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
    )

    if image_path:
        root.deiconify()  # Show the root window
        editor = CardEditor(root, image_path)
        root.mainloop()
    else:
        root.destroy()  # Close the application if no image selected
