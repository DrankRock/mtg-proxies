import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import threading
import queue
import time
from pathlib import Path
import sys
import numpy as np

# Add parent directory to path to ensure imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import mtgproxies functions
from mtgproxies import fetch_scans_scryfall, print_cards_fpdf
from mtgproxies.cli import parse_decklist_spec


class CardWorker:
    def __init__(self, callback_queue):
        self.callback_queue = callback_queue
        self.running = False
        self.thread = None
        self.decklist = None
        self.images = []
    
    def load_decklist(self, decklist_path):
        """Parse decklist and start the worker thread"""
        self.running = True
        self.thread = threading.Thread(target=self._process_cards, args=(decklist_path,))
        self.thread.daemon = True
        self.thread.start()
    
    def _process_cards(self, decklist_path):
        """Background thread that processes cards"""
        try:
            # Parse the decklist
            self.decklist = parse_decklist_spec(decklist_path)
            total_cards = self.decklist.total_count
            self.callback_queue.put(("total", total_cards))
            
            # Fetch scans, this is where the actual Scryfall API calls happen
            self.images = fetch_scans_scryfall(self.decklist, faces="all")
            
            # Signal completion
            self.callback_queue.put(("done", self.images))
        except Exception as e:
            self.callback_queue.put(("error", str(e)))
        finally:
            self.running = False
    
    def save_to_pdf(self, output_path):
        """Save the current cards to PDF"""
        if not self.images:
            return False
            
        try:
            # Using A4 paper as default
            print_cards_fpdf(
                self.images,
                output_path,
                papersize=np.array([21, 29.7]),  # A4 in cm
                cardsize=np.array([2.5, 3.5]) * 25.4,  # Standard MTG card size in mm
                cropmarks=True
            )
            return True
        except Exception as e:
            print(f"Error saving to PDF: {e}")
            return False


class MTGProxyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MTG Proxy Tool")
        self.root.geometry("800x700")
        
        # Set up callback queue for worker thread
        self.callback_queue = queue.Queue()
        self.worker = CardWorker(self.callback_queue)
        
        # State variables
        self.current_index = 0
        self.total_cards = 0
        self.images = []
        
        # Configure grid weights
        self.root.grid_columnconfigure(0, weight=1)  # Main column takes all horizontal space
        self.root.grid_rowconfigure(2, weight=1)     # Image row takes all vertical space
        
        # Row 1: AI token input (3-column subgrid)
        self.token_frame = ttk.Frame(root)
        self.token_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Configure the token frame's grid
        self.token_frame.columnconfigure(0, weight=0)  # Auto
        self.token_frame.columnconfigure(1, weight=1)  # 100%
        self.token_frame.columnconfigure(2, weight=0)  # Auto
        
        # Token label, entry and save button
        self.token_label = ttk.Label(self.token_frame, text="AI token")
        self.token_label.grid(row=0, column=0, padx=(0, 5))
        
        self.token_entry = ttk.Entry(self.token_frame)
        self.token_entry.grid(row=0, column=1, sticky="ew")
        
        self.save_token_btn = ttk.Button(self.token_frame, text="Save", command=self.save_token)
        self.save_token_btn.grid(row=0, column=2, padx=(5, 0))
        
        # Row 1.5: Load deck button and counter
        self.control_frame = ttk.Frame(root)
        self.control_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.control_frame.columnconfigure(0, weight=0)
        self.control_frame.columnconfigure(1, weight=1)
        
        self.load_deck_btn = ttk.Button(self.control_frame, text="Load Decklist", command=self.load_decklist)
        self.load_deck_btn.grid(row=0, column=0, sticky="w")
        
        self.counter_label = ttk.Label(self.control_frame, text="0/0")
        self.counter_label.grid(row=0, column=1, sticky="e")
        
        # Row 2: Image display
        self.image_frame = ttk.Frame(root, borderwidth=1, relief="solid")
        self.image_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        
        # Placeholder for image
        self.image_label = ttk.Label(self.image_frame, text="Load a decklist to start")
        self.image_label.pack(expand=True, fill="both")
        self.current_image = None
        
        # Progress bar (initially hidden)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.image_frame, variable=self.progress_var, maximum=100)
        self.progress_text = ttk.Label(self.image_frame, text="Loading cards...")
        
        # Row 3: Navigation buttons
        self.nav_frame = ttk.Frame(root)
        self.nav_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        self.nav_frame.columnconfigure(0, weight=1)
        self.nav_frame.columnconfigure(1, weight=1)
        self.nav_frame.columnconfigure(2, weight=1)
        
        self.prev_btn = ttk.Button(self.nav_frame, text="Previous", command=self.previous_card, state=tk.DISABLED)
        self.prev_btn.grid(row=0, column=0, sticky="ew", padx=2)
        
        self.edit_btn = ttk.Button(self.nav_frame, text="Edit Card", command=self.edit_card, state=tk.DISABLED)
        self.edit_btn.grid(row=0, column=1, sticky="ew", padx=2)
        
        self.next_btn = ttk.Button(self.nav_frame, text="Next", command=self.next_card, state=tk.DISABLED)
        self.next_btn.grid(row=0, column=2, sticky="ew", padx=2)
        
        # Row 4: Save to PDF button
        self.save_pdf_btn = ttk.Button(root, text="Save to PDF", command=self.save_to_pdf, state=tk.DISABLED)
        self.save_pdf_btn.grid(row=4, column=0, sticky="ew", padx=5, pady=5)
        
        # Create card_images directory if it doesn't exist
        os.makedirs("./card_images", exist_ok=True)
        
        # Start polling the callback queue
        self.poll_queue()
        
        # Bind closing event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def poll_queue(self):
        """Check for messages from the worker thread"""
        try:
            while True:
                message, data = self.callback_queue.get_nowait()
                if message == "total":
                    self.total_cards = data
                    self.counter_label.config(text=f"0/{self.total_cards}")
                    self.progress_var.set(0)
                    # Show progress bar
                    self.image_label.pack_forget()
                    self.progress_text.pack(pady=(100, 10))
                    self.progress_bar.pack(fill="x", padx=50, pady=10)
                    
                elif message == "progress":
                    percentage = (data / self.total_cards) * 100
                    self.progress_var.set(percentage)
                    self.progress_text.config(text=f"Loading cards... {data}/{self.total_cards}")
                    
                elif message == "done":
                    self.images = data
                    # Hide progress and show first image
                    self.progress_bar.pack_forget()
                    self.progress_text.pack_forget()
                    self.image_label.pack(expand=True, fill="both")
                    
                    # Enable buttons
                    self.next_btn.config(state=tk.NORMAL)
                    self.edit_btn.config(state=tk.NORMAL)
                    self.save_pdf_btn.config(state=tk.NORMAL)
                    self.load_deck_btn.config(state=tk.NORMAL)
                    if len(self.images) > 0:
                        self.display_current_card()
                        
                elif message == "error":
                    # Hide progress and show error
                    self.progress_bar.pack_forget()
                    self.progress_text.pack_forget()
                    self.image_label.pack(expand=True, fill="both")
                    self.image_label.config(text=f"Error: {data}")
                    messagebox.showerror("Error", f"An error occurred: {data}")
                    self.load_deck_btn.config(state=tk.NORMAL)
                    
                self.callback_queue.task_done()
        except queue.Empty:
            pass
        
        # Check again after 100ms
        self.root.after(100, self.poll_queue)

    def load_decklist(self):
        """Open a file dialog to select a decklist"""
        file_path = filedialog.askopenfilename(
            title="Select Decklist",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            # Disable buttons during loading
            self.load_deck_btn.config(state=tk.DISABLED)
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)
            self.edit_btn.config(state=tk.DISABLED)
            self.save_pdf_btn.config(state=tk.DISABLED)
            
            # Reset state
            self.current_index = 0
            self.total_cards = 0
            self.images = []
            
            # Start the worker
            self.worker.load_decklist(file_path)

    def display_current_card(self):
        """Display the current card image"""
        if not self.images or self.current_index >= len(self.images):
            return
            
        image_path = self.images[self.current_index]
        self.counter_label.config(text=f"{self.current_index + 1}/{len(self.images)}")
        
        try:
            # Use a new PIL Image object to ensure we're loading the latest version
            # (avoiding any potential caching issues)
            with open(image_path, 'rb') as f:
                img = Image.open(f).copy()
            self.display_image(img)
            
            # Update navigation buttons
            self.prev_btn.config(state=tk.NORMAL if self.current_index > 0 else tk.DISABLED)
            self.next_btn.config(state=tk.NORMAL if self.current_index < len(self.images) - 1 else tk.DISABLED)
        except Exception as e:
            self.image_label.config(text=f"Failed to load image: {e}", image="")
            
    def display_image(self, img):
        """Resize and display an image in the image label"""
        # Resize image to fit the frame while maintaining aspect ratio
        img_width, img_height = img.size
        frame_width = self.image_frame.winfo_width()
        frame_height = self.image_frame.winfo_height()
        
        # If frame hasn't been drawn yet, use reasonable defaults
        if frame_width <= 1:
            frame_width = 600
        if frame_height <= 1:
            frame_height = 400
            
        # Calculate scaling factor
        width_ratio = frame_width / img_width
        height_ratio = frame_height / img_height
        scale_factor = min(width_ratio, height_ratio)
        
        new_width = int(img_width * scale_factor * 0.9)  # 90% of available space
        new_height = int(img_height * scale_factor * 0.9)
        
        resized_img = img.resize((new_width, new_height), Image.LANCZOS)
        self.current_image = ImageTk.PhotoImage(resized_img)
        
        # Update the image in the label
        self.image_label.config(image=self.current_image, text="")

    def previous_card(self):
        """Go to the previous card"""
        if self.current_index > 0:
            self.current_index -= 1
            self.display_current_card()

    def next_card(self):
        """Go to the next card"""
        if self.images and self.current_index < len(self.images) - 1:
            self.current_index += 1
            self.display_current_card()

    def edit_card(self):
        """Open the card editor for the current card"""
        if not self.images or self.current_index >= len(self.images):
            return
        
        # Import the card editor module
        import card_editor
        
        # Define callback for when an image is saved
        def on_image_saved(saved_path):
            print(f"Image saved: {saved_path}")
            # Refresh the display to show the updated image
            self.display_current_card()
        
        # Launch the editor with the current image and callback
        image_path = self.images[self.current_index]
        self.editor = card_editor.launch_editor(image_path, on_save_callback=on_image_saved)

    def save_to_pdf(self):
        """Save the current cards to PDF"""
        if not self.images:
            messagebox.showwarning("No Cards", "No cards available to save")
            return
            
        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if save_path:
            # Disable the button during saving
            self.save_pdf_btn.config(state=tk.DISABLED)
            
            # Run in a separate thread to avoid freezing the UI
            def save_thread():
                success = self.worker.save_to_pdf(save_path)
                
                # Update UI from main thread
                self.root.after(0, lambda: self._save_complete(success, save_path))
                
            threading.Thread(target=save_thread, daemon=True).start()
    
    def _save_complete(self, success, path):
        """Called when save is complete"""
        self.save_pdf_btn.config(state=tk.NORMAL)
        if success:
            messagebox.showinfo("Success", f"Successfully saved to {path}")
        else:
            messagebox.showerror("Error", f"Failed to save to {path}")

    def save_token(self):
        """Save the Scryfall API token (if needed)"""
        token = self.token_entry.get()
        if token:
            # Save token to a config file
            with open("token.txt", "w") as f:
                f.write(token)
            messagebox.showinfo("Token Saved", "API token has been saved successfully")
        else:
            messagebox.showwarning("Empty Token", "Please enter a token before saving")
    
    def on_closing(self):
        """Handle window close event"""
        if self.worker.running:
            if messagebox.askyesno("Quit", "Card processing is still running. Are you sure you want to quit?"):
                self.root.destroy()
        else:
            self.root.destroy()