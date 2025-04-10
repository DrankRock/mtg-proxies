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
from PIL import Image, ImageDraw, ImageOps, ImageTk  # Added ImageOps

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

# Make sure load_image_to_selection is not imported directly if we modify it here
# from card_editor.tools import add_text_to_selection, apply_auto_dark_fill_windowless, load_image_to_selection
from card_editor.tools import add_text_to_selection, apply_auto_dark_fill_windowless
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
        self.original_image = Image.open(image_path).convert("RGBA")  # Ensure RGBA
        self.working_image = self.original_image.copy()
        self.display_image = None  # For zoomed/transformed image
        self.tk_image = None  # Hold reference to PhotoImage

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
        self.image_id = None  # Store canvas image item id

        # Scrollbars
        self.h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")

        self.v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")

        self.canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)

        self.create_presets_panel()

        # Status bar
        self.status_frame = ttk.Frame(root)
        self.status_frame.grid(row=1, column=0, columnspan=3, sticky="ew")  # Span all 3 columns

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

        # --- New state variables for image placement ---
        self.is_placing_image = False
        self.placement_image_orig = None  # The originally loaded image (PIL)
        self.placement_image_tk = None  # The PhotoImage for canvas display
        self.placement_rect = None  # The (x1, y1, x2, y2) of the selection area in *image* coords
        self.placement_zoom = 1.0  # Zoom factor relative to initial fit
        self.placement_offset = [0, 0]  # Current drag offset (x, y) in *image* coords
        self.placement_img_id = None  # Canvas ID for the temporary placement image
        self.placement_drag_start_pos = None  # Canvas coords where drag started
        self.placement_drag_start_offset = None  # Offset when drag started
        # --- End of new state variables ---

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
        self.image_zone_var.set(bool(self.current_preset.image_rect))
        self.name_zone_var.set(bool(self.current_preset.name_rect))
        self.type_zone_var.set(bool(self.current_preset.type_rect))
        self.description_zone_var.set(bool(self.current_preset.description_rect))

    def update_zone_info(self):
        """Update zone information labels based on current preset"""
        if not self.current_preset:
            return

        def format_rect(rect):
            if not rect:
                return "Not configured"
            return (
                f"X: {rect['x']*100:.1f}%, Y: {rect['y']*100:.1f}%\n"
                f"W: {rect['width']*100:.1f}%, H: {rect['height']*100:.1f}%"
            )

        # Image zone
        self.image_zone_info.config(text=format_rect(self.current_preset.image_rect))
        # Name zone
        self.name_zone_info.config(text=format_rect(self.current_preset.name_rect))
        # Type zone
        self.type_zone_info.config(text=format_rect(self.current_preset.type_rect))
        # Description zone
        self.description_zone_info.config(text=format_rect(self.current_preset.description_rect))

    def zone_checkbox_changed(self):
        """Handle zone checkbox state changes"""
        # This function is called when any zone checkbox is toggled
        pass

    def set_preset_zone(self, zone_type):
        """Set the zone coordinates from the current selection"""
        if self.is_placing_image:
            messagebox.showinfo("Action Denied", "Please apply or cancel image placement first.")
            return
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

        zone_rect = {
            "x": round(x_percent, 4),
            "y": round(y_percent, 4),
            "width": round(width_percent, 4),
            "height": round(height_percent, 4),
        }

        # Update the appropriate zone in the current preset
        if zone_type == "image":
            self.current_preset.image_rect = zone_rect
            self.image_zone_var.set(True)
        elif zone_type == "name":
            self.current_preset.name_rect = zone_rect
            self.name_zone_var.set(True)
        elif zone_type == "type":
            self.current_preset.type_rect = zone_rect
            self.type_zone_var.set(True)
        elif zone_type == "description":
            self.current_preset.description_rect = zone_rect
            self.description_zone_var.set(True)

        # Update zone info display
        self.update_zone_info()

        # Reset selection rectangle on canvas, keep coords for potential immediate use
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
            self.selection_rect = None
        # self.selection_coords = None # Keep coords temporarily? Or clear? Let's clear.
        # self.reset_selection() # This clears coords too

        self.status_label.config(text=f"{zone_type.capitalize()} zone set")

        # Save preset after updating
        save_preset(self.current_preset)
        self.reset_selection()  # Clear selection visually and internally

    def apply_preset_zone(self, zone_type):
        """Apply the selected zone from the preset"""
        if self.is_placing_image:
            messagebox.showinfo("Action Denied", "Please apply or cancel image placement first.")
            return
        if not self.current_preset:
            print("No current preset")
            messagebox.showinfo("No Preset", "Please select a preset first")
            return

        # Get the zone rectangle from the preset and determine the tool
        rect = None
        tool = None
        zone_var = None

        if zone_type == "image":
            zone_var = self.image_zone_var
            rect = self.current_preset.image_rect
            tool = EditorTool.LOAD_IMAGE
        elif zone_type == "name":
            zone_var = self.name_zone_var
            rect = self.current_preset.name_rect
            tool = EditorTool.ADD_TEXT
        elif zone_type == "type":
            zone_var = self.type_zone_var
            rect = self.current_preset.type_rect
            tool = EditorTool.ADD_TEXT
        elif zone_type == "description":
            zone_var = self.description_zone_var
            rect = self.current_preset.description_rect
            tool = EditorTool.ADD_TEXT

        print(f"Applying zone: {zone_type}, Checkbox state: {zone_var.get() if zone_var else 'N/A'}")

        if not zone_var or not zone_var.get():
            print(f"{zone_type.capitalize()} zone not selected or checkbox unchecked.")
            # Optionally show a message? Or just do nothing silently?
            # messagebox.showinfo("Zone Not Selected", f"The '{zone_type}' zone is not checked.")
            return

        if not rect:
            messagebox.showinfo("Zone Not Configured", f"The '{zone_type}' zone is not configured in the preset.")
            return

        print(f"Zone: {zone_type}, Rect: {rect}")

        # Convert percentage to pixel coordinates
        x1 = int(rect["x"] * self.img_width)
        y1 = int(rect["y"] * self.img_height)
        x2 = int((rect["x"] + rect["width"]) * self.img_width)
        y2 = int((rect["y"] + rect["height"]) * self.img_height)

        # Ensure coordinates are valid
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(self.img_width, x2)
        y2 = min(self.img_height, y2)

        if x1 >= x2 or y1 >= y2:
            messagebox.showerror(
                "Invalid Zone", f"The calculated pixel coordinates for the '{zone_type}' zone are invalid."
            )
            return

        print(f"Selection coords (pixels): ({x1}, {y1}, {x2}, {y2})")

        # Set the selection coordinates *first*
        self.selection_coords = (x1, y1, x2, y2)

        # Set current tool *after* setting coordinates
        self.set_tool(tool)  # This also calls reset_selection internally, clearing the visual rect

        # Now draw the selection rectangle based on the set coords
        self.draw_selection_rect()

        print(f"Before applying tool, self.selection_coords = {self.selection_coords}")
        print(f"Current tool: {self.current_tool}")

        # Apply the tool associated with the zone
        # Note: apply_tool() requires a button press, so we call the specific tool functions directly
        if tool == EditorTool.LOAD_IMAGE:
            self.load_image_to_selection()  # This will now initiate placement mode
        elif tool == EditorTool.ADD_TEXT:
            self.add_text_to_selection()
        elif tool == EditorTool.AUTO_FILL_TEXT:
            # This case shouldn't happen based on current logic, but for completeness:
            self.apply_auto_dark_fill()

    def process_all_zones(self):
        """Process all selected zones in sequence"""
        if self.is_placing_image:
            messagebox.showinfo("Action Denied", "Please apply or cancel image placement first.")
            return
        if not self.current_preset:
            messagebox.showinfo("No Preset", "Please select a preset first")
            return

        zones_to_process = []

        # Check which zones are selected and configured
        if self.image_zone_var.get() and self.current_preset.image_rect:
            zones_to_process.append("image")
        if self.name_zone_var.get() and self.current_preset.name_rect:
            zones_to_process.append("name")
        if self.type_zone_var.get() and self.current_preset.type_rect:
            zones_to_process.append("type")
        if self.description_zone_var.get() and self.current_preset.description_rect:
            zones_to_process.append("description")

        if not zones_to_process:
            messagebox.showinfo("No Zones Selected", "Please select at least one configured zone to process")
            return

        # Process each zone in sequence
        for zone_type in zones_to_process:
            print(f"Processing zone: {zone_type}")
            # Apply the zone - this might start interactive modes like text entry or image placement
            self.apply_preset_zone(zone_type)

            # If image placement was started, we need to wait for the user to finish it.
            # This sequential processing might not work well with interactive steps.
            # A better approach might be needed if multiple interactive steps are required.
            # For now, we assume only one interactive step (like text or image placement)
            # will be active at a time. If apply_preset_zone starts placement,
            # subsequent calls in this loop might be blocked or behave unexpectedly.
            if self.is_placing_image:
                messagebox.showinfo(
                    "Placement Mode Active",
                    f"Image placement for '{zone_type}' zone started. "
                    "Please position the image and click 'Apply Changes'. "
                    "Processing of other zones is paused.",
                )
                return  # Stop processing further zones until placement is done

            # Small delay/update might be needed for UI changes like text dialogs
            self.root.update_idletasks()  # Process pending UI events

        self.status_label.config(text="Selected zones processed (or initiated)")

    def setup_bindings(self):
        """Set up mouse and keyboard bindings"""
        # Mouse events
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)

        # Mouse wheel for zooming (canvas and placement image)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)  # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)  # Linux scroll down

        # Keyboard shortcuts
        self.root.bind("<Escape>", lambda e: self.reset_selection())  # Also cancels placement
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Control-s>", lambda e: self.save_image())
        self.root.bind("<Control-S>", lambda e: self.save_image_as())  # Shift+Ctrl+S
        self.root.bind("<Control-z>", lambda e: self.undo())

    def set_tool(self, tool):
        """Set the current editing tool"""
        if self.is_placing_image:
            messagebox.showinfo("Action Denied", "Cannot change tool during image placement. Apply or cancel first.")
            return

        self.current_tool = tool
        self.status_label.config(text=f"Current tool: {tool.name}")
        self.reset_selection()  # Clear any previous selection when changing tool

        # Remove border from previously selected button
        if self.selected_tool_button:
            self.selected_tool_button.config(borderwidth=1, relief="raised")

        # Add border to newly selected button
        new_button = None
        if tool == EditorTool.AUTO_FILL_TEXT:
            new_button = self.AUTO_FILL_TEXT_btn
        elif tool == EditorTool.ADD_TEXT:
            new_button = self.text_btn
        elif tool == EditorTool.LOAD_IMAGE:
            new_button = self.image_btn
        # Add other tools if necessary
        # elif tool == EditorTool.PAN: ...

        self.selected_tool_button = new_button

        # Set border on new button
        if self.selected_tool_button:
            self.selected_tool_button.config(borderwidth=2, relief="solid")

    def update_display(self):
        """Update the canvas with the current image and any overlays"""
        # Base image update
        display_image(self)  # This handles zoom and draws self.working_image

        # --- Draw placement overlay if active ---
        if self.is_placing_image and self.placement_image_orig and self.placement_rect:
            self._draw_placement_overlay()
        # --- End placement overlay ---

        # Redraw selection rectangle if it exists (and not in placement mode)
        if self.selection_coords and not self.is_placing_image:
            self.draw_selection_rect()
        elif self.is_placing_image and self.placement_rect:
            # Draw the placement boundary rectangle
            self.draw_placement_boundary()

    def _draw_placement_overlay(self):
        """Helper function to draw the temporary placement image"""
        if not self.is_placing_image or not self.placement_image_orig or not self.placement_rect:
            return

        # 1. Get placement area details (in image coordinates)
        px1, py1, px2, py2 = self.placement_rect
        p_width = px2 - px1
        p_height = py2 - py1

        # 2. Get the overlay image and its original size
        overlay = self.placement_image_orig
        overlay_w, overlay_h = overlay.size

        # 3. Calculate the scaled size based on placement_zoom
        # The initial fit determined the base size, placement_zoom scales that.
        # We need the size it *would* be if pasted directly without zoom first.
        aspect_ratio_overlay = overlay_w / overlay_h
        aspect_ratio_rect = p_width / p_height

        if aspect_ratio_overlay > aspect_ratio_rect:  # Overlay wider than rect -> fit width
            initial_fit_w = p_width
            initial_fit_h = int(p_width / aspect_ratio_overlay)
        else:  # Overlay taller than rect (or same aspect) -> fit height
            initial_fit_h = p_height
            initial_fit_w = int(p_height * aspect_ratio_overlay)

        scaled_w = int(initial_fit_w * self.placement_zoom)
        scaled_h = int(initial_fit_h * self.placement_zoom)

        # Ensure minimum size
        scaled_w = max(1, scaled_w)
        scaled_h = max(1, scaled_h)

        # 4. Resize the original overlay image
        resized_overlay = overlay.resize((scaled_w, scaled_h), Image.LANCZOS)

        # 5. Calculate the top-left position for pasting this resized overlay
        # The offset is relative to the top-left of the placement_rect
        # We also need to center the initial placement if the aspect ratios didn't match
        initial_offset_x = (p_width - initial_fit_w) // 2
        initial_offset_y = (p_height - initial_fit_h) // 2

        # The final offset includes initial centering, drag offset, and zoom effect
        # Zoom effect needs to keep the center point stable relative to the placement rect center
        center_x_rect = p_width / 2
        center_y_rect = p_height / 2
        center_x_scaled = scaled_w / 2
        center_y_scaled = scaled_h / 2

        # Position adjustment due to zoom (relative to center)
        zoom_offset_x = center_x_rect - center_x_scaled
        zoom_offset_y = center_y_rect - center_y_scaled

        # Combine offsets: placement rect corner + initial centering + zoom centering + drag offset
        paste_x_img = px1 + initial_offset_x + zoom_offset_x + self.placement_offset[0]
        paste_y_img = py1 + initial_offset_y + zoom_offset_y + self.placement_offset[1]

        # 6. Create a temporary transparent canvas matching the working_image size
        temp_canvas_pil = Image.new("RGBA", (self.img_width, self.img_height), (0, 0, 0, 0))

        # 7. Paste the resized overlay onto the temporary canvas at the calculated position
        temp_canvas_pil.paste(resized_overlay, (int(paste_x_img), int(paste_y_img)))

        # 8. Create a mask based on the placement rectangle
        mask = Image.new("L", (self.img_width, self.img_height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rectangle((px1, py1, px2, py2), fill=255)

        # 9. Apply the mask to the temporary canvas (cropping the overlay to the rect)
        temp_canvas_pil.putalpha(mask)

        # 10. Convert the masked temporary canvas to Tkinter PhotoImage
        # Apply the main canvas zoom factor
        display_size = (int(self.img_width * self.zoom_factor), int(self.img_height * self.zoom_factor))
        display_overlay_pil = temp_canvas_pil.resize(display_size, Image.LANCZOS)
        self.placement_image_tk = ImageTk.PhotoImage(display_overlay_pil)  # Store reference

        # 11. Draw this PhotoImage on the main Tkinter canvas
        if self.placement_img_id:
            self.canvas.delete(self.placement_img_id)
        self.placement_img_id = self.canvas.create_image(0, 0, anchor="nw", image=self.placement_image_tk)
        self.canvas.lift(self.placement_img_id)  # Ensure it's on top

    def draw_placement_boundary(self):
        """Draws a distinct boundary for the placement area"""
        if not self.placement_rect:
            return
        x1, y1, x2, y2 = self.placement_rect
        # Convert image coordinates to display coordinates
        cx1 = int(x1 * self.zoom_factor)
        cy1 = int(y1 * self.zoom_factor)
        cx2 = int(x2 * self.zoom_factor)
        cy2 = int(y2 * self.zoom_factor)

        # Use a different color/dash for placement boundary
        if self.selection_rect:  # Reuse if possible
            self.canvas.coords(self.selection_rect, cx1, cy1, cx2, cy2)
            self.canvas.itemconfig(self.selection_rect, outline="blue", width=2, dash=(5, 3))
        else:
            self.selection_rect = self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline="blue", width=2, dash=(5, 3))
        self.canvas.lift(self.selection_rect)  # Ensure boundary is visible

    def draw_selection_rect(self):
        """Draw the selection rectangle (only when not placing image)"""
        if self.is_placing_image:
            # If we are placing an image, the boundary is drawn by draw_placement_boundary
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)
                self.selection_rect = None
            return

        # Original logic for drawing red dashed rectangle
        draw_selection_rect(self)

    def on_mouse_down(self, event):
        """Handle mouse button press"""
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        image_x = canvas_x / self.zoom_factor
        image_y = canvas_y / self.zoom_factor

        # --- Placement Mode Logic ---
        if self.is_placing_image and self.placement_rect:
            px1, py1, px2, py2 = self.placement_rect
            if px1 <= image_x < px2 and py1 <= image_y < py2:
                # Clicked inside placement area, start drag
                self.placement_drag_start_pos = (canvas_x, canvas_y)
                self.placement_drag_start_offset = list(self.placement_offset)  # Copy current offset
                self.canvas.config(cursor="fleur")
                return  # Don't process other tools
            else:
                # Clicked outside placement area - maybe cancel? Or do nothing?
                # Let's do nothing for now, require Apply/Reset/Esc
                pass
        # --- End Placement Mode Logic ---

        # Original logic for other tools
        self.start_x = canvas_x
        self.start_y = canvas_y

        if self.current_tool == EditorTool.PAN:
            # Pan logic remains the same
            self.pan_start_x = self.start_x
            self.pan_start_y = self.start_y
            self.canvas.config(cursor="fleur")

        elif self.current_tool in [EditorTool.AUTO_FILL_TEXT, EditorTool.LOAD_IMAGE, EditorTool.ADD_TEXT]:
            # Standard selection drawing logic
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)
                self.selection_rect = None
            self.selection_coords = None  # Clear previous coords

            if self.current_tool == EditorTool.AUTO_FILL_TEXT and hasattr(self, "selection_mode_var"):
                selection_mode = self.selection_mode_var.get()
                if selection_mode == "spot_healing":
                    # Spot healing logic remains the same
                    self.brush_points = []
                    self.brush_strokes = []
                    self.last_brush_point = (self.start_x, self.start_y)
                    brush_radius = int(self.brush_size_var.get() * self.zoom_factor)
                    initial_stroke = self.canvas.create_oval(
                        self.start_x - brush_radius,
                        self.start_y - brush_radius,
                        self.start_x + brush_radius,
                        self.start_y + brush_radius,
                        outline="red",
                        width=2,
                    )
                    self.brush_strokes.append(initial_stroke)
                    self.brush_points.append((image_x, image_y))
                    return

            # Default rectangle initialization
            self.selection_rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2, dash=(4, 4)
            )

    def on_mouse_drag(self, event):
        """Handle mouse drag"""
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)

        # --- Placement Mode Logic ---
        if self.is_placing_image and self.placement_drag_start_pos:
            # Calculate drag delta in *canvas* coordinates
            delta_x = cur_x - self.placement_drag_start_pos[0]
            delta_y = cur_y - self.placement_drag_start_pos[1]

            # Convert delta to *image* coordinates
            delta_image_x = delta_x / self.zoom_factor
            delta_image_y = delta_y / self.zoom_factor

            # Update placement offset based on the initial offset + delta
            new_offset_x = self.placement_drag_start_offset[0] + delta_image_x
            new_offset_y = self.placement_drag_start_offset[1] + delta_image_y

            # TODO: Add boundary checks if needed - prevent dragging too far?
            # For now, allow free dragging. Clamping might be complex with zoom.

            self.placement_offset[0] = new_offset_x
            self.placement_offset[1] = new_offset_y

            # Redraw the overlay
            self._draw_placement_overlay()
            return  # Don't process other tools
        # --- End Placement Mode Logic ---

        # Original logic for other tools
        if self.current_tool == EditorTool.PAN:
            # Pan logic remains the same
            self.canvas.scan_dragto(event.x, event.y, gain=1)

        elif self.current_tool in [EditorTool.AUTO_FILL_TEXT, EditorTool.LOAD_IMAGE, EditorTool.ADD_TEXT]:
            # Spot healing drag logic remains the same
            if self.current_tool == EditorTool.AUTO_FILL_TEXT and hasattr(self, "selection_mode_var"):
                selection_mode = self.selection_mode_var.get()
                if selection_mode == "spot_healing" and hasattr(self, "last_brush_point"):
                    brush_radius = int(self.brush_size_var.get() * self.zoom_factor)
                    stroke_width = brush_radius * 2
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
                    circle = self.canvas.create_oval(
                        cur_x - brush_radius,
                        cur_y - brush_radius,
                        cur_x + brush_radius,
                        cur_y + brush_radius,
                        outline="red",
                        width=2,
                    )
                    self.brush_strokes.append(circle)
                    self.last_brush_point = (cur_x, cur_y)
                    self.brush_points.append((cur_x / self.zoom_factor, cur_y / self.zoom_factor))
                    return

            # Default rectangle update
            if self.selection_rect:
                self.canvas.coords(self.selection_rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_mouse_up(self, event):
        """Handle mouse button release"""
        # --- Placement Mode Logic ---
        if self.is_placing_image and self.placement_drag_start_pos:
            # End drag
            self.placement_drag_start_pos = None
            self.placement_drag_start_offset = None
            self.canvas.config(cursor="")
            # Keep placement mode active, waiting for Apply/Reset
            self.status_label.config(text="Image placement: Drag to move, Wheel to zoom, Apply/Reset when done.")
            return  # Don't process other tools
        # --- End Placement Mode Logic ---

        # Original logic for other tools
        if self.current_tool == EditorTool.PAN:
            self.canvas.config(cursor="")
            return  # Pan finished

        # Finalize selection for other tools
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)

        if self.current_tool in [EditorTool.AUTO_FILL_TEXT, EditorTool.LOAD_IMAGE, EditorTool.ADD_TEXT]:
            # Spot healing finalization remains the same
            if self.current_tool == EditorTool.AUTO_FILL_TEXT and hasattr(self, "selection_mode_var"):
                selection_mode = self.selection_mode_var.get()
                if selection_mode == "spot_healing" and hasattr(self, "brush_points") and self.brush_points:
                    # ... (spot healing finalization logic - unchanged) ...
                    for stroke in self.brush_strokes:
                        self.canvas.delete(stroke)
                    self.brush_strokes = []
                    points_x = [p[0] for p in self.brush_points]
                    points_y = [p[1] for p in self.brush_points]
                    center_x1, center_y1 = min(points_x), min(points_y)
                    center_x2, center_y2 = max(points_x), max(points_y)
                    brush_size = self.brush_size_var.get()
                    brush_radius = brush_size / 2
                    x1 = max(0, int(center_x1 - brush_radius))
                    y1 = max(0, int(center_y1 - brush_radius))
                    x2 = min(self.img_width, int(center_x2 + brush_radius))
                    y2 = min(self.img_height, int(center_y2 + brush_radius))
                    self.selection_coords = (x1, y1, x2, y2)
                    if self.selection_rect:
                        self.canvas.delete(self.selection_rect)
                    self.selection_rect = self.canvas.create_rectangle(
                        x1 * self.zoom_factor,
                        y1 * self.zoom_factor,
                        x2 * self.zoom_factor,
                        y2 * self.zoom_factor,
                        outline="red",
                        width=2,
                        dash=(4, 4),
                    )
                    self.status_label.config(text="Selection created from brush strokes. Press 'Apply Changes'.")
                    # Don't auto-apply here, wait for Apply button
                    return

            # Default rectangle finalization
            if self.start_x is not None and self.start_y is not None:  # Check if selection started
                x1 = min(self.start_x, cur_x) / self.zoom_factor
                y1 = min(self.start_y, cur_y) / self.zoom_factor
                x2 = max(self.start_x, cur_x) / self.zoom_factor
                y2 = max(self.start_y, cur_y) / self.zoom_factor

                # Check for minimal size
                if (x2 - x1) >= 5 and (y2 - y1) >= 5:
                    self.selection_coords = (int(x1), int(y1), int(x2), int(y2))
                    # Don't apply immediately, wait for Apply button or specific action
                    if self.current_tool == EditorTool.LOAD_IMAGE:
                        # Initiate load image process which will start placement mode
                        self.load_image_to_selection()
                    elif self.current_tool == EditorTool.ADD_TEXT:
                        # Open text dialog
                        self.add_text_to_selection()
                    elif self.current_tool == EditorTool.AUTO_FILL_TEXT:
                        # Wait for Apply button for auto-fill as well
                        self.status_label.config(text="Selection made. Press 'Apply Changes' to fill.")
                        # Keep selection rect visible
                        if self.selection_rect:
                            self.canvas.coords(
                                self.selection_rect,
                                x1 * self.zoom_factor,
                                y1 * self.zoom_factor,
                                x2 * self.zoom_factor,
                                y2 * self.zoom_factor,
                            )
                        else:
                            self.draw_selection_rect()  # Should draw it based on coords
                else:
                    # Selection too small, reset
                    self.reset_selection()
            else:
                # No selection was started (e.g., just a click)
                self.reset_selection()

        # Reset start points
        self.start_x = None
        self.start_y = None

    def on_mouse_move(self, event):
        """Handle mouse movement"""
        # Update coordinates display (remains the same)
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        image_x = int(canvas_x / self.zoom_factor)
        image_y = int(canvas_y / self.zoom_factor)

        # Set cursor based on mode
        cursor = ""
        if self.is_placing_image and self.placement_rect:
            px1, py1, px2, py2 = self.placement_rect
            if px1 <= image_x < px2 and py1 <= image_y < py2:
                cursor = "fleur"  # Movable area
            else:
                cursor = ""  # Outside placement area
        elif self.current_tool == EditorTool.PAN:
            cursor = "fleur"
        # Add other cursor logic if needed

        self.canvas.config(cursor=cursor)

        if 0 <= image_x < self.img_width and 0 <= image_y < self.img_height:
            try:
                # Get pixel data safely
                pixel = self.working_image.getpixel((image_x, image_y))
                if isinstance(pixel, (tuple, list)):
                    r, g, b = pixel[:3]
                    self.coords_label.config(text=f"X: {image_x}, Y: {image_y} | RGB: ({r},{g},{b})")
                else:  # Grayscale
                    self.coords_label.config(text=f"X: {image_x}, Y: {image_y} | Gray: {pixel}")
            except IndexError:
                self.coords_label.config(text=f"X: {image_x}, Y: {image_y} (Out of bounds?)")
            except Exception as e:
                # print(f"Error getting pixel: {e}")
                self.coords_label.config(text=f"X: {image_x}, Y: {image_y}")
        else:
            self.coords_label.config(text="")

    def on_mouse_wheel(self, event):
        """Handle mouse wheel for zooming (canvas or placement image)"""
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        image_x = canvas_x / self.zoom_factor
        image_y = canvas_y / self.zoom_factor

        # --- Placement Mode Zoom ---
        if self.is_placing_image and self.placement_rect:
            px1, py1, px2, py2 = self.placement_rect
            if px1 <= image_x < px2 and py1 <= image_y < py2:
                # Zoom placement image
                zoom_delta = 1.1 if (event.num == 4 or event.delta > 0) else 1 / 1.1
                new_zoom = self.placement_zoom * zoom_delta

                # Add zoom limits if desired (e.g., min 10%, max 500%)
                new_zoom = max(0.1, min(new_zoom, 5.0))

                # TODO: Implement zoom towards cursor?
                # This is complex. For now, zoom relative to center.
                # If implementing zoom towards cursor:
                # 1. Get cursor pos relative to placement rect (image coords).
                # 2. Calculate how much the image 'grows'/'shrinks'.
                # 3. Adjust self.placement_offset to keep the point under the cursor stationary.

                self.placement_zoom = new_zoom
                self._draw_placement_overlay()
                self.status_label.config(text=f"Image placement: Zoom {self.placement_zoom:.1f}x")
                return  # Don't zoom main canvas
        # --- End Placement Mode Zoom ---

        # Default: Zoom main canvas
        if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
            self.zoom_in()
        elif event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
            self.zoom_out()

    def zoom_in(self):
        """Zoom in main canvas by 10%"""
        if self.is_placing_image:
            return  # Don't zoom canvas during placement
        self.zoom_factor *= 1.1
        self.update_display()

    def zoom_out(self):
        """Zoom out main canvas by 10%"""
        if self.is_placing_image:
            return  # Don't zoom canvas during placement
        self.zoom_factor = max(0.1, self.zoom_factor / 1.1)
        self.update_display()

    def zoom_fit(self):
        """Zoom main canvas to fit image in window"""
        if self.is_placing_image:
            return
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            return  # Avoid division by zero if window not ready

        width_ratio = canvas_width / self.img_width
        height_ratio = canvas_height / self.img_height
        self.zoom_factor = min(width_ratio, height_ratio) * 0.98  # Slightly smaller margin
        self.update_display()

    def zoom_actual(self):
        """Reset main canvas zoom to 100%"""
        if self.is_placing_image:
            return
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
            # Ensure correct placement relative to other buttons if needed
            self.auto_fill_settings_frame.pack(fill="x", pady=2, before=self.text_btn)  # Example placement
            self.toggle_settings_btn.config(text="▲ Auto Fill Settings")

        self.auto_fill_settings_visible = not self.auto_fill_settings_visible

    def reset_selection(self, event=None):
        """Reset the current selection OR cancel image placement"""
        # --- Cancel Placement Mode ---
        if self.is_placing_image:
            self.is_placing_image = False
            if self.placement_img_id:
                self.canvas.delete(self.placement_img_id)
            self.placement_image_orig = None
            self.placement_image_tk = None
            self.placement_rect = None
            self.placement_zoom = 1.0
            self.placement_offset = [0, 0]
            self.placement_img_id = None
            self.placement_drag_start_pos = None
            self.placement_drag_start_offset = None
            self.canvas.config(cursor="")
            self.status_label.config(text="Image placement cancelled.")
            # Also clear the visual selection rectangle
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)
                self.selection_rect = None
            self.selection_coords = None  # Clear the coords that defined the placement area
            self.update_display()  # Redraw without overlay
            return
        # --- End Cancel Placement Mode ---

        # Original reset logic
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
            self.selection_rect = None
        self.selection_coords = None
        # Reset brush strokes if any
        if hasattr(self, "brush_strokes"):
            for stroke in self.brush_strokes:
                self.canvas.delete(stroke)
            self.brush_strokes = []
            self.brush_points = []
        self.status_label.config(text="Selection reset.")

    def apply_tool(self):
        """Apply the current tool OR finalize image placement"""
        # --- Finalize Placement Mode ---
        if self.is_placing_image:
            self._finalize_image_placement()
            return
        # --- End Finalize Placement Mode ---

        # Original apply logic
        if not self.selection_coords:
            messagebox.showinfo("No Selection", "Please select an area first")
            return

        if self.current_tool == EditorTool.AUTO_FILL_TEXT:
            # Record state before applying auto fill
            self.record_state("Before auto fill text")
            # Use the windowless implementation with specified iterations
            iterations = self.fill_iterations_var.get()
            apply_auto_dark_fill_windowless(self, clear_selection=True, iterations=iterations)
            # Note: apply_auto_dark_fill_windowless now handles its own history recording and display update
        elif self.current_tool == EditorTool.ADD_TEXT:
            # Text is added via its own dialog's Apply button, not here.
            # This button shouldn't do anything for Add Text tool unless a selection is made *first*.
            # If selection exists, open the dialog.
            self.add_text_to_selection()
        elif self.current_tool == EditorTool.LOAD_IMAGE:
            # Image is loaded via load_image_to_selection, which starts placement.
            # This button shouldn't do anything for Load Image tool unless a selection is made *first*.
            # If selection exists, start the loading process.
            self.load_image_to_selection()
        else:
            messagebox.showinfo(
                "Not Applicable",
                f"Apply Changes is not applicable for the current tool ({self.current_tool.name}) without an active placement or specific action.",
            )

    def _finalize_image_placement(self):
        """Pastes the placed image onto the working image"""
        if not self.is_placing_image or not self.placement_image_orig or not self.placement_rect:
            return

        print("Finalizing image placement...")
        self.status_label.config(text="Applying placed image...")
        self.root.update_idletasks()

        # Record state before applying
        self.record_state("Before image placement")

        # --- Replicate the drawing logic used in _draw_placement_overlay ---
        # --- but this time, paste onto the actual working_image ---

        # 1. Get placement area details (in image coordinates)
        px1, py1, px2, py2 = self.placement_rect
        p_width = px2 - px1
        p_height = py2 - py1

        # 2. Get the overlay image and its original size
        overlay = self.placement_image_orig
        overlay_w, overlay_h = overlay.size

        # 3. Calculate the scaled size based on placement_zoom
        aspect_ratio_overlay = overlay_w / overlay_h
        aspect_ratio_rect = p_width / p_height
        if aspect_ratio_overlay > aspect_ratio_rect:
            initial_fit_w = p_width
            initial_fit_h = int(p_width / aspect_ratio_overlay)
        else:
            initial_fit_h = p_height
            initial_fit_w = int(p_height * aspect_ratio_overlay)
        scaled_w = max(1, int(initial_fit_w * self.placement_zoom))
        scaled_h = max(1, int(initial_fit_h * self.placement_zoom))

        # 4. Resize the original overlay image
        resized_overlay = overlay.resize((scaled_w, scaled_h), Image.LANCZOS)

        # 5. Calculate the top-left position for pasting
        initial_offset_x = (p_width - initial_fit_w) // 2
        initial_offset_y = (p_height - initial_fit_h) // 2
        center_x_rect = p_width / 2
        center_y_rect = p_height / 2
        center_x_scaled = scaled_w / 2
        center_y_scaled = scaled_h / 2
        zoom_offset_x = center_x_rect - center_x_scaled
        zoom_offset_y = center_y_rect - center_y_scaled
        paste_x_img = px1 + initial_offset_x + zoom_offset_x + self.placement_offset[0]
        paste_y_img = py1 + initial_offset_y + zoom_offset_y + self.placement_offset[1]

        # 6. Create a mask for the placement rectangle area
        mask = Image.new("L", (scaled_w, scaled_h), 0)  # Mask size matches resized overlay
        # We need to determine which part of the resized_overlay falls *inside* the placement_rect
        # Calculate intersection of overlay bounds and placement rect bounds
        overlay_left = paste_x_img
        overlay_top = paste_y_img
        overlay_right = paste_x_img + scaled_w
        overlay_bottom = paste_y_img + scaled_h

        intersect_left = max(px1, overlay_left)
        intersect_top = max(py1, overlay_top)
        intersect_right = min(px2, overlay_right)
        intersect_bottom = min(py2, overlay_bottom)

        if intersect_left < intersect_right and intersect_top < intersect_bottom:
            # Calculate the coordinates *within the resized_overlay* that correspond to the intersection
            mask_x1 = int(intersect_left - overlay_left)
            mask_y1 = int(intersect_top - overlay_top)
            mask_x2 = int(intersect_right - overlay_left)
            mask_y2 = int(intersect_bottom - overlay_top)

            # Draw the valid area onto the mask
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rectangle((mask_x1, mask_y1, mask_x2, mask_y2), fill=255)

            # 7. Paste onto the working image using the mask
            # Ensure working_image is RGBA for proper alpha blending if overlay has alpha
            if self.working_image.mode != "RGBA":
                self.working_image = self.working_image.convert("RGBA")
            # Ensure overlay is RGBA if it wasn't already
            if resized_overlay.mode != "RGBA":
                resized_overlay = resized_overlay.convert("RGBA")

            # Paste using the calculated mask
            self.working_image.paste(resized_overlay, (int(paste_x_img), int(paste_y_img)), mask)

            print(f"Pasted image at ({int(paste_x_img)}, {int(paste_y_img)}) with size {resized_overlay.size}")
        else:
            print("No intersection between placed image and selection rectangle. Nothing pasted.")

        # 8. Clean up placement state
        self.is_placing_image = False
        if self.placement_img_id:
            self.canvas.delete(self.placement_img_id)
        self.placement_image_orig = None
        self.placement_image_tk = None
        self.placement_rect = None
        self.placement_zoom = 1.0
        self.placement_offset = [0, 0]
        self.placement_img_id = None
        self.placement_drag_start_pos = None
        self.placement_drag_start_offset = None
        self.canvas.config(cursor="")

        # Also clear the visual selection rectangle used for the boundary
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
            self.selection_rect = None
        self.selection_coords = None  # Placement finished, clear coords

        # Record state after applying
        self.record_state("Applied image placement")

        # Update display
        self.update_display()
        self.status_label.config(text="Image placement applied.")

    def apply_auto_dark_fill(self, use_gui=False):
        """
        Apply auto dark content-aware fill to the selected area

        Args:
            use_gui: Whether to use the GUI or the windowless implementation (Not used here)
        """
        if not self.selection_coords:
            messagebox.showinfo("No Selection", "Please make a selection first.")
            return
        if self.is_placing_image:
            messagebox.showinfo("Action Denied", "Please apply or cancel image placement first.")
            return

        # Record state before applying auto fill
        self.record_state("Before auto fill text")

        # Use the windowless implementation with specified iterations
        iterations = self.fill_iterations_var.get()
        apply_auto_dark_fill_windowless(self, clear_selection=True, iterations=iterations)

    def add_text_to_selection(self):
        """Add text to the selected area with interactive controls"""
        if not self.selection_coords:
            messagebox.showinfo("No Selection", "Please make a selection first.")
            return
        if self.is_placing_image:
            messagebox.showinfo("Action Denied", "Please apply or cancel image placement first.")
            return
        add_text_to_selection(self)

    def load_image_to_selection(self):
        """Load an image and initiate placement mode"""
        if not self.selection_coords:
            messagebox.showinfo("No Selection", "Please make a selection first (using Load Image tool or preset).")
            return
        if self.is_placing_image:
            messagebox.showinfo("Action Denied", "Already placing an image. Apply or cancel first.")
            return

        # Open file dialog
        file_path = filedialog.askopenfilename(
            title="Select Image to Load",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif"), ("All files", "*.*")],
        )

        if not file_path:
            # User cancelled dialog, reset selection? Or just do nothing?
            # Let's reset the selection rectangle visually but keep coords
            # if self.selection_rect:
            #     self.canvas.delete(self.selection_rect)
            #     self.selection_rect = None
            # Keep self.selection_coords in case they want to try again
            return

        try:
            # Load the image using PIL, ensure RGBA
            loaded_img = Image.open(file_path).convert("RGBA")

            # Store necessary info for placement mode
            self.placement_image_orig = loaded_img
            self.placement_rect = self.selection_coords  # Use current selection as placement boundary
            self.placement_zoom = 1.0  # Start at 1x zoom relative to initial fit
            self.placement_offset = [0, 0]  # Start with no drag offset

            # Enter placement mode
            self.is_placing_image = True

            # Clear the standard selection rectangle, placement boundary will be drawn
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)
                self.selection_rect = None
            # Keep selection_coords as they define the placement_rect

            # Update display to show the overlay
            self.update_display()
            self.status_label.config(text="Image loaded. Drag to move, Wheel to zoom. Apply/Reset when done.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {str(e)}")
            self.reset_selection()  # Reset if loading failed

    def save_image(self):
        """Save the current image"""
        if self.is_placing_image:
            messagebox.showinfo("Action Denied", "Please apply or cancel image placement first.")
            return
        try:
            # Ensure image is saved in a common format like PNG or RGB JPEG
            save_image = self.working_image
            if save_image.mode == "RGBA" and self.image_path.lower().endswith((".jpg", ".jpeg")):
                # Warn user about potential transparency loss or convert
                if messagebox.askyesno(
                    "Format Warning",
                    "Image has transparency (RGBA). Saving as JPEG will lose transparency. Convert to RGB? (Choosing 'No' might cause errors)",
                ):
                    save_image = save_image.convert("RGB")
                else:
                    # Try saving RGBA as JPEG anyway, might error or work depending on PIL/libjpeg
                    pass

            save_image.save(self.image_path)
            self.status_label.config(text=f"Saved to {self.image_path}")

            # Call the callback if it exists
            if self.on_save_callback:
                self.on_save_callback(self.image_path)

            # Ask user if they want to close the editor
            # if messagebox.askyesno("Save Complete", "Image saved successfully. Close the editor?"):
            #     self.root.destroy() # Let's not close automatically

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save image: {str(e)}")

    def close_editor(self):
        if self.is_placing_image:
            if not messagebox.askyesno("Confirm Close", "Image placement is active. Close without applying?"):
                return
        # TODO: Check for unsaved changes?
        self.root.destroy()

    def save_image_as(self):
        """Save the current image with a new name"""
        if self.is_placing_image:
            messagebox.showinfo("Action Denied", "Please apply or cancel image placement first.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Image As",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
            initialfile=Path(self.image_path).name,  # Suggest current name
        )

        if file_path:
            try:
                # Handle format conversion like in save_image
                save_image = self.working_image
                file_ext = Path(file_path).suffix.lower()
                if save_image.mode == "RGBA" and file_ext in (".jpg", ".jpeg"):
                    if messagebox.askyesno(
                        "Format Warning",
                        "Image has transparency (RGBA). Saving as JPEG will lose transparency. Convert to RGB?",
                    ):
                        save_image = save_image.convert("RGB")

                save_image.save(file_path)
                self.image_path = file_path  # Update current path
                self.root.title(f"Card Editor - {Path(file_path).name}")
                self.status_label.config(text=f"Saved to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {str(e)}")

    def undo(self, event=None):
        """Undo the last operation"""
        if self.is_placing_image:
            messagebox.showinfo("Action Denied", "Cannot undo during image placement. Apply or cancel first.")
            return

        if not self.history.can_undo():
            self.status_label.config(text="Nothing to undo")
            return

        # Get the previous state
        previous_state, description = self.history.undo()

        # Restore the image
        self.working_image = previous_state.copy()  # Use copy to avoid issues if state is reused
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
        # Ensure we don't record during placement, only before/after
        if self.is_placing_image:
            print("Warning: Attempted to record history during image placement.")
            return
        self.history.add_state(self.working_image, description)


# Function to create and launch the editor
def launch_editor(image_path, on_save_callback=None):
    """
    Launch the card editor

    Args:
        image_path: Path to the image to edit
        on_save_callback: Function to call when save is complete (optional)
    """
    # Ensure Tk root exists for Toplevel
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the main Tk window if not already done
    except tk.TclError:
        # If a root already exists (e.g., running within another Tk app)
        pass  # Use the existing root implicitly

    editor_window = tk.Toplevel()  # Create editor in a new window
    editor = CardEditor(editor_window, image_path)

    # Store the callback
    editor.on_save_callback = on_save_callback

    # Make sure the editor window closes properly
    editor_window.protocol("WM_DELETE_WINDOW", editor.close_editor)

    return editor  # Return the editor instance


# Standalone test when run directly
if __name__ == "__main__":
    # Ask for an image to edit
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    image_path = filedialog.askopenfilename(
        title="Select Image to Edit", filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
    )

    if image_path:
        # Don't need to deiconify the hidden root, launch_editor creates Toplevel
        editor_instance = launch_editor(image_path)
        editor_instance.root.mainloop()  # Start the main loop for the editor window
    else:
        root.destroy()  # Close the hidden root if no image selected
