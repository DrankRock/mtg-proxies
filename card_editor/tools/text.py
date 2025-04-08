"""
Text tool implementation
"""

import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk


def add_text_to_selection(editor):
    """
    Add text to the selected area with interactive controls

    Args:
        editor: CardEditor instance
    """
    if not editor.selection_coords:
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
    text_window = tk.Toplevel(editor.root)
    text_window.title("Add Text")
    text_window.geometry("500x500")
    text_window.transient(editor.root)
    text_window.grab_set()

    # Get selection coordinates
    x1, y1, x2, y2 = editor.selection_coords

    # Default position is center of selection
    center_x = int((x1 + x2) / 2)
    center_y = int((y1 + y2) / 2)

    # Variables for text properties
    text_var = tk.StringVar(value="Enter text here")
    size_var = tk.IntVar(value=24)
    font_var = tk.StringVar(value=all_fonts[0] if all_fonts else "default")
    color_var = tk.StringVar(value="#FFFFFF")
    pos_x_var = tk.IntVar(value=center_x)
    pos_y_var = tk.IntVar(value=center_y)
    h_align_var = tk.StringVar(value="left")  # Default horizontal alignment is left
    v_align_var = tk.StringVar(value="center")  # Default vertical alignment is center

    # Live preview variables
    preview_text = None
    preview_img = None

    # Function to calculate actual position based on alignment and text dimensions
    def calculate_position(text, font_obj, h_alignment, v_alignment):
        # Get text dimensions
        lines = text.split("\n")

        # Initialize dimensions
        total_height = 0
        max_width = 0
        line_heights = []

        for line in lines:
            if not line.strip():  # Handle empty lines
                line_height = size_var.get()
                line_heights.append(line_height)
                total_height += line_height
                continue

            try:
                # For newer Pillow versions
                text_bbox = font_obj.getbbox(line)
                line_width = text_bbox[2] - text_bbox[0]
                line_height = text_bbox[3] - text_bbox[1]
            except:
                try:
                    # For older Pillow versions
                    line_width, line_height = draw.textsize(line, font=font_obj)
                except:
                    # Fallback estimation
                    line_width = len(line) * size_var.get() // 2
                    line_height = size_var.get()

            max_width = max(max_width, line_width)
            line_heights.append(line_height)
            total_height += line_height

        # Calculate X position based on horizontal alignment
        if h_alignment == "left":
            x = x1  # Left edge of selection
        elif h_alignment == "center":
            x = center_x - (max_width // 2)  # Center of selection - half of text width
        else:  # right
            x = x2 - max_width  # Right edge of selection - text width

        # Calculate Y position based on vertical alignment
        if v_alignment == "top":
            y = y1  # Top edge of selection
        elif v_alignment == "center":
            y = center_y - (total_height // 2)  # Center of selection - half of text height
        else:  # bottom
            y = y2 - total_height  # Bottom edge of selection - text height

        return x, y, line_heights, total_height

    # Function to update the text preview
    def update_preview(*args):
        nonlocal preview_text, preview_img

        # Clear previous preview
        if preview_text:
            editor.canvas.delete(preview_text)

        # Get current text properties
        text = text_text.get("1.0", tk.END).strip()
        size = size_var.get()
        font_name = font_var.get()
        color_value = color_var.get()
        h_alignment = h_align_var.get()
        v_alignment = v_align_var.get()

        # Create a temporary image for preview
        temp_img = editor.working_image.copy()
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
                for sys_font in []:  # We don't have system_fonts defined here
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

        # Calculate position based on alignment
        text_x, text_y, line_heights, _ = calculate_position(text, font_obj, h_alignment, v_alignment)

        # Update position spinboxes to reflect the calculated alignment position
        pos_x_var.set(text_x)
        pos_y_var.set(text_y)

        # Handle multiline text
        lines = text.split("\n")
        y_offset = 0

        for i, line in enumerate(lines):
            if not line.strip():  # Skip empty lines but add spacing
                y_offset += line_heights[i]
                continue

            # Draw text on image
            draw.text((text_x, text_y + y_offset), line, fill=color_value, font=font_obj)
            y_offset += line_heights[i]

        # Update the display
        new_size = (int(editor.img_width * editor.zoom_factor), int(editor.img_height * editor.zoom_factor))
        display_img = temp_img.resize(new_size, Image.LANCZOS)
        preview_img = ImageTk.PhotoImage(display_img)

        # Update canvas
        editor.canvas.itemconfig(editor.image_id, image=preview_img)

    # Function to apply text and close
    def apply_text():
        # Get text properties
        text = text_text.get("1.0", tk.END).strip()
        size = size_var.get()
        font_name = font_var.get()
        color_value = color_var.get()
        h_alignment = h_align_var.get()
        v_alignment = v_align_var.get()

        if not text.strip():
            text_window.destroy()
            return

        # Record state before adding text
        if hasattr(editor, "record_state"):
            editor.record_state("Before adding text")

        # Create drawing context
        draw = ImageDraw.Draw(editor.working_image)

        # Try to use the selected font
        font_obj = None
        try:
            # Check custom fonts directory first
            for font_path in fonts_dir.glob(f"{font_name}*"):
                font_obj = ImageFont.truetype(str(font_path), size)
                break

            # If not found in custom directory, check system paths
            if not font_obj:
                for sys_font in []:  # We don't have system_fonts defined here
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

        # Calculate position based on alignment
        text_x, text_y, line_heights, _ = calculate_position(text, font_obj, h_alignment, v_alignment)

        # Handle multiline text
        lines = text.split("\n")
        y_offset = 0

        for i, line in enumerate(lines):
            if not line.strip():  # Skip empty lines but add spacing
                y_offset += line_heights[i]
                continue

            # Draw text on image
            draw.text((text_x, text_y + y_offset), line, fill=color_value, font=font_obj)
            y_offset += line_heights[i]

        # Record state after adding text
        if hasattr(editor, "record_state"):
            editor.record_state(f"Added text: {text[:20]}" + ("..." if len(text) > 20 else ""))

        # Update display and close window
        editor.update_display()
        editor.reset_selection()
        editor.status_label.config(text="Text added")
        text_window.destroy()

    # Function to cancel
    def cancel_text():
        editor.update_display()  # Reset to original image
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
    pos_frame = ttk.LabelFrame(frame, text="Text Position (updated by alignment)")
    pos_frame.grid(row=4, column=0, columnspan=3, sticky="we", pady=10)

    ttk.Label(pos_frame, text="X:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    x_spinbox = ttk.Spinbox(pos_frame, from_=0, to=editor.img_width, textvariable=pos_x_var, width=5, increment=1)
    x_spinbox.grid(row=0, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(pos_frame, text="Y:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
    y_spinbox = ttk.Spinbox(pos_frame, from_=0, to=editor.img_height, textvariable=pos_y_var, width=5, increment=1)
    y_spinbox.grid(row=0, column=3, sticky="w", padx=5, pady=5)

    # Text alignment controls
    align_frame = ttk.LabelFrame(frame, text="Text Alignment")
    align_frame.grid(row=5, column=0, columnspan=3, sticky="we", pady=10)

    # Horizontal alignment
    h_align_frame = ttk.LabelFrame(align_frame, text="Horizontal Alignment")
    h_align_frame.pack(fill="x", padx=5, pady=5)
    ttk.Radiobutton(h_align_frame, text="Left", variable=h_align_var, value="left").pack(side=tk.LEFT, padx=20)
    ttk.Radiobutton(h_align_frame, text="Center", variable=h_align_var, value="center").pack(side=tk.LEFT, padx=20)
    ttk.Radiobutton(h_align_frame, text="Right", variable=h_align_var, value="right").pack(side=tk.LEFT, padx=20)

    # Vertical alignment
    v_align_frame = ttk.LabelFrame(align_frame, text="Vertical Alignment")
    v_align_frame.pack(fill="x", padx=5, pady=5)
    ttk.Radiobutton(v_align_frame, text="Top", variable=v_align_var, value="top").pack(side=tk.LEFT, padx=20)
    ttk.Radiobutton(v_align_frame, text="Center", variable=v_align_var, value="center").pack(side=tk.LEFT, padx=20)
    ttk.Radiobutton(v_align_frame, text="Bottom", variable=v_align_var, value="bottom").pack(side=tk.LEFT, padx=20)

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
    h_align_var.trace_add("write", update_preview)
    v_align_var.trace_add("write", update_preview)

    # Initial preview
    update_preview()

    # Focus on text entry
    text_text.focus_set()
    text_text.tag_add("sel", "1.0", "end")
