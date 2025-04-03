import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import numpy as np
import cv2
import os
from pathlib import Path
from enum import Enum, auto


class EditorTool(Enum):
    SELECT = auto()
    CONTENT_AWARE_FILL = auto()
    ADD_TEXT = auto()
    LOAD_IMAGE = auto()
    PAN = auto()


class CardEditor:
    def __init__(self, root, image_path):
        self.root = root
        self.image_path = image_path
        self.on_save_callback = None  # Will be set by launch_editor if needed
        
        # Set up window
        self.root.title(f"Card Editor - {Path(image_path).name}")
        self.root.geometry("1000x800")
        
        # Configure main grid
        self.root.grid_columnconfigure(0, weight=0)  # Toolbar
        self.root.grid_columnconfigure(1, weight=1)  # Canvas
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
        
        # Status bar
        self.status_frame = ttk.Frame(root)
        self.status_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        self.status_label = ttk.Label(self.status_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        self.coords_label = ttk.Label(self.status_frame, text="")
        self.coords_label.pack(side=tk.RIGHT, padx=5)
        
        # Set initial tool
        self.current_tool = EditorTool.PAN
        
        # Drawing state
        self.start_x = None
        self.start_y = None
        self.selection_rect = None
        self.selection_coords = None  # Format: (x1, y1, x2, y2) in image coordinates
        
        # Zoom and pan
        self.zoom_factor = 1.0
        self.pan_start_x = 0
        self.pan_start_y = 0
        
        # Set up event bindings
        self.setup_bindings()
        
        # Display the image
        self.update_display()
        
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
        
        self.select_btn = ttk.Button(tools_frame, text="Select", command=lambda: self.set_tool(EditorTool.SELECT))
        self.select_btn.pack(fill="x", pady=2)
        
        self.pan_btn = ttk.Button(tools_frame, text="Pan", command=lambda: self.set_tool(EditorTool.PAN))
        self.pan_btn.pack(fill="x", pady=2)
        
        self.fill_btn = ttk.Button(tools_frame, text="Content-Aware Fill", 
                                   command=lambda: self.set_tool(EditorTool.CONTENT_AWARE_FILL))
        self.fill_btn.pack(fill="x", pady=2)
        
        self.text_btn = ttk.Button(tools_frame, text="Add Text", 
                                  command=lambda: self.set_tool(EditorTool.ADD_TEXT))
        self.text_btn.pack(fill="x", pady=2)
        
        self.image_btn = ttk.Button(tools_frame, text="Load Image", 
                                   command=lambda: self.set_tool(EditorTool.LOAD_IMAGE))
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
            
            self.selection_rect = self.canvas.create_rectangle(
                x1, y1, x2, y2, outline="red", width=2, dash=(4, 4)
            )
    
    def on_mouse_down(self, event):
        """Handle mouse button press"""
        # Get canvas coordinates
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        
        if self.current_tool == EditorTool.PAN:
            self.pan_start_x = self.canvas.canvasx(event.x)
            self.pan_start_y = self.canvas.canvasy(event.y)
            self.canvas.config(cursor="fleur")
            
        elif self.current_tool in [EditorTool.SELECT, EditorTool.CONTENT_AWARE_FILL, EditorTool.LOAD_IMAGE, EditorTool.ADD_TEXT]:
            # Start a new selection
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)
            self.selection_rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y,
                outline="red", width=2, dash=(4, 4)
            )
    
    def on_mouse_drag(self, event):
        """Handle mouse drag"""
        # Get current canvas coordinates
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        
        if self.current_tool == EditorTool.PAN:
            # Pan the canvas
            self.canvas.scan_dragto(event.x, event.y, gain=1)
            
        elif self.current_tool in [EditorTool.SELECT, EditorTool.CONTENT_AWARE_FILL, EditorTool.LOAD_IMAGE, EditorTool.ADD_TEXT]:
            # Update selection rectangle
            self.canvas.coords(self.selection_rect, self.start_x, self.start_y, cur_x, cur_y)
    
    def on_mouse_up(self, event):
        """Handle mouse button release"""
        # Get current canvas coordinates
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        
        if self.current_tool == EditorTool.PAN:
            self.canvas.config(cursor="")
            
        elif self.current_tool in [EditorTool.SELECT, EditorTool.CONTENT_AWARE_FILL, EditorTool.LOAD_IMAGE, EditorTool.ADD_TEXT]:
            # Finalize selection rectangle
            # Convert display coordinates to image coordinates
            x1 = min(self.start_x, cur_x) / self.zoom_factor
            y1 = min(self.start_y, cur_y) / self.zoom_factor
            x2 = max(self.start_x, cur_x) / self.zoom_factor
            y2 = max(self.start_y, cur_y) / self.zoom_factor
            
            # Ensure selection is at least 5x5 pixels
            if (x2 - x1) >= 5 and (y2 - y1) >= 5:
                self.selection_coords = (int(x1), int(y1), int(x2), int(y2))
                
                # If tool is add text, show text dialog right away
                if self.current_tool == EditorTool.ADD_TEXT:
                    self.add_text_to_selection()
                
                # If tool is load image, show file dialog right away
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
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            # Zoom in
            self.zoom_in()
        elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
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
        self.root.attributes('-fullscreen', not self.root.attributes('-fullscreen'))
    
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
        elif self.current_tool == EditorTool.ADD_TEXT:
            self.add_text_to_selection()
        elif self.current_tool == EditorTool.LOAD_IMAGE:
            self.load_image_to_selection()
    
    def apply_content_aware_fill(self):
        """Apply content-aware fill to the selected area"""
        if not self.selection_coords:
            return
            
        # Debug info
        print(f"Applying content-aware fill to selection: {self.selection_coords}")
        
        try:
            # Convert PIL image to OpenCV format
            img_cv = np.array(self.working_image)
            # Convert RGB to BGR (OpenCV uses BGR)
            img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2BGR)
            
            # Create mask for inpainting (white in the selected area)
            mask = np.zeros(img_cv.shape[:2], dtype=np.uint8)
            x1, y1, x2, y2 = self.selection_coords
            
            # Ensure coordinates are within bounds
            x1 = max(0, min(x1, self.img_width-1))
            y1 = max(0, min(y1, self.img_height-1))
            x2 = max(0, min(x2, self.img_width))
            y2 = max(0, min(y2, self.img_height))
            
            # Create the mask (make selected area white)
            mask[y1:y2, x1:x2] = 255
            
            print(f"Mask created with shape: {mask.shape}, white area: {x1},{y1} to {x2},{y2}")
            
            # Set inpainting radius (larger is smoother but slower)
            inpaint_radius = 5
            
            # Apply inpainting - we'll use both methods for better results
            # First TELEA (faster)
            result = cv2.inpaint(img_cv, mask, inpaint_radius, cv2.INPAINT_TELEA)
            print("TELEA inpainting applied")
            
            # Then NS (better quality but slower) if available
            try:
                ns_result = cv2.inpaint(img_cv, mask, inpaint_radius, cv2.INPAINT_NS)
                print("NS inpainting applied")
                result = ns_result  # Use NS result if it worked
            except:
                print("NS inpainting not available, using TELEA result")
            
            # Convert back to RGB and PIL format
            result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
            self.working_image = Image.fromarray(result_rgb)
            
            print("Inpainting successful, updating display")
            
            # Update display
            self.update_display()
            self.reset_selection()
            self.status_label.config(text="Content-aware fill applied")
            
        except Exception as e:
            import traceback
            print(f"Error in content-aware fill: {str(e)}")
            print(traceback.format_exc())
            tk.messagebox.showerror("Error", f"Inpainting failed: {str(e)}")
            return
    
    def add_text_to_selection(self):
        """Add text to the selected area with interactive controls"""
        if not self.selection_coords:
            return
            
        # Create font directory if it doesn't exist
        fonts_dir = Path("./fonts")
        fonts_dir.mkdir(exist_ok=True)
        
        # Check for fonts in the directory
        font_files = list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))
        
        # Also include system fonts if possible
        system_fonts = []
        try:
            # Try different common system font locations
            for font_path in [
                "/usr/share/fonts",  # Linux
                "/Library/Fonts",  # macOS
                "C:/Windows/Fonts"  # Windows
            ]:
                if os.path.exists(font_path):
                    system_fonts.extend(Path(font_path).glob("*.ttf"))
                    system_fonts.extend(Path(font_path).glob("*.otf"))
                    break
        except:
            pass
        
        # Combine custom and system fonts, use set to remove duplicates
        all_fonts = list(set([f.name for f in font_files] + [f.name for f in system_fonts]))
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
            lines = text.split('\n')
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
            lines = text.split('\n')
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
        frame.pack(fill='both', expand=True)
        
        # Add UI elements
        ttk.Label(frame, text="Text:").grid(row=0, column=0, sticky='nw', pady=5)
        text_frame = ttk.Frame(frame)
        text_frame.grid(row=0, column=1, columnspan=2, sticky='we', pady=5)
        text_text = tk.Text(text_frame, wrap="word", width=30, height=5)
        text_text.insert("1.0", "Enter text here")
        text_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scroll = ttk.Scrollbar(text_frame, command=text_text.yview)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text_text.config(yscrollcommand=text_scroll.set)
        
        ttk.Label(frame, text="Size:").grid(row=1, column=0, sticky='w', pady=5)
        size_scale = ttk.Scale(frame, from_=8, to=72, variable=size_var, orient='horizontal')
        size_scale.grid(row=1, column=1, sticky='we', pady=5)
        ttk.Label(frame, textvariable=size_var).grid(row=1, column=2, sticky='w', pady=5)
        
        ttk.Label(frame, text="Font:").grid(row=2, column=0, sticky='w', pady=5)
        font_combo = ttk.Combobox(frame, textvariable=font_var, values=all_fonts, state="readonly")
        font_combo.grid(row=2, column=1, columnspan=2, sticky='we', pady=5)
        
        ttk.Label(frame, text="Color:").grid(row=3, column=0, sticky='w', pady=5)
        color_frame = ttk.Frame(frame)
        color_frame.grid(row=3, column=1, sticky='w', pady=5)
        color_entry = ttk.Entry(color_frame, textvariable=color_var, width=10)
        color_entry.pack(side=tk.LEFT)
        color_button = tk.Button(color_frame, bg=color_var.get(), width=3, command=pick_color)
        color_button.pack(side=tk.LEFT, padx=5)
        
        # Text position controls
        pos_frame = ttk.LabelFrame(frame, text="Text Position")
        pos_frame.grid(row=4, column=0, columnspan=3, sticky='we', pady=10)
        
        ttk.Label(pos_frame, text="X:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        x_spinbox = ttk.Spinbox(pos_frame, from_=0, to=self.img_width, textvariable=pos_x_var, width=5, increment=1)
        x_spinbox.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        
        ttk.Label(pos_frame, text="Y:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
        y_spinbox = ttk.Spinbox(pos_frame, from_=0, to=self.img_height, textvariable=pos_y_var, width=5, increment=1)
        y_spinbox.grid(row=0, column=3, sticky='w', padx=5, pady=5)
        
        # Text alignment controls
        align_frame = ttk.LabelFrame(frame, text="Text Alignment")
        align_frame.grid(row=5, column=0, columnspan=3, sticky='we', pady=10)
        
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
            title="Select Image",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.gif"),
                ("All files", "*.*")
            ]
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
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg"),
                ("All files", "*.*")
            ]
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
        title="Select Image to Edit",
        filetypes=[
            ("Image files", "*.jpg *.jpeg *.png *.bmp"),
            ("All files", "*.*")
        ]
    )
    
    if image_path:
        root = tk.Tk()
        editor = CardEditor(root, image_path)
        root.mainloop()