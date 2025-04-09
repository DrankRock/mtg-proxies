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
# Ensure this path adjustment is correct for your project structure
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import mtgproxies functions - Handle potential ImportError
try:
    from mtgproxies import fetch_scans_scryfall, print_cards_fpdf
    from mtgproxies.decklists import Decklist, Card
    from mtgproxies.cli import parse_decklist_spec
    MTGPROXIES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Failed to import mtgproxies modules: {e}")
    print("Decklist loading and PDF generation might not work.")
    MTGPROXIES_AVAILABLE = False
    # Define dummy classes/functions if needed for basic operation
    class Decklist:
        def __init__(self): self.cards = []
        @property
        def total_count(self): return 0
    class Card: pass
    def parse_decklist_spec(path): return Decklist()
    def fetch_scans_scryfall(decklist, faces): return []
    def print_cards_fpdf(*args, **kwargs): raise NotImplementedError("mtgproxies not found")


class CardWorker:
    def __init__(self, callback_queue):
        self.callback_queue = callback_queue
        self.running = False
        self.thread = None
        self.decklist = None
        self.images = [] # This will store paths

    def load_decklist(self, decklist_path):
        """Parse decklist and start the worker thread"""
        if not MTGPROXIES_AVAILABLE:
             self.callback_queue.put(("error", "mtgproxies library not found"))
             return
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
            self.images = fetch_scans_scryfall(self.decklist, faces="all") # Returns list of paths

            # Signal completion
            self.callback_queue.put(("done", self.images))
        except Exception as e:
            import traceback
            print(f"Error in _process_cards: {e}")
            traceback.print_exc()
            self.callback_queue.put(("error", str(e)))
        finally:
            self.running = False

    def save_to_pdf(self, image_paths, output_path):
        """Save the current cards (image paths) to PDF"""
        if not MTGPROXIES_AVAILABLE:
             self.callback_queue.put(("error", "mtgproxies library not found"))
             return False
        if not image_paths:
            return False

        try:
            # Using A4 paper as default - FIXED: Use correct units (mm)
            print_cards_fpdf(
                image_paths, # Pass the list of paths
                output_path,
                papersize=np.array([210, 297]),  # A4 in mm
                cardsize=np.array([2.5, 3.5]) * 25.4,  # Standard MTG card size in mm
                cropmarks=True
            )
            return True
        except Exception as e:
            print(f"Error saving to PDF: {e}")
            import traceback
            traceback.print_exc()
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
        # self.total_cards = 0 # We'll use len(self.images) directly
        self.images = [] # List to hold image file paths

        # Configure grid weights
        self.root.grid_columnconfigure(0, weight=1)  # Main column takes all horizontal space
        self.root.grid_rowconfigure(2, weight=1)   # Image row takes all vertical space

        # Row 0: AI token input (remains the same)
        self.token_frame = ttk.Frame(root)
        self.token_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.token_frame.columnconfigure(0, weight=0)
        self.token_frame.columnconfigure(1, weight=1)
        self.token_frame.columnconfigure(2, weight=0)
        self.token_label = ttk.Label(self.token_frame, text="AI token")
        self.token_label.grid(row=0, column=0, padx=(0, 5))
        self.token_entry = ttk.Entry(self.token_frame)
        self.token_entry.grid(row=0, column=1, sticky="ew")
        self.save_token_btn = ttk.Button(self.token_frame, text="Save", command=self.save_token)
        self.save_token_btn.grid(row=0, column=2, padx=(5, 0))

        # Row 1: Control buttons and counter
        self.control_frame = ttk.Frame(root)
        self.control_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        # Configure grid for control frame (Load, Add Custom, Add New, Spacer, Counter)
        self.control_frame.columnconfigure(0, weight=0) # Load Deck
        self.control_frame.columnconfigure(1, weight=0) # Add Custom
        self.control_frame.columnconfigure(2, weight=0) # Add New Card
        self.control_frame.columnconfigure(3, weight=1) # Spacer to push counter right
        self.control_frame.columnconfigure(4, weight=0) # Counter

        self.load_deck_btn = ttk.Button(self.control_frame, text="Load Decklist", command=self.load_decklist)
        self.load_deck_btn.grid(row=0, column=0, sticky="w", padx=(0, 5))
        if not MTGPROXIES_AVAILABLE:
            self.load_deck_btn.config(state=tk.DISABLED) # Disable if lib not found

        # --- NEW BUTTONS ---
        self.add_custom_btn = ttk.Button(self.control_frame, text="Add Custom Image", command=self.add_custom_image)
        self.add_custom_btn.grid(row=0, column=1, sticky="w", padx=(0, 5))
        # self.add_custom_btn.config(state=tk.DISABLED) # Enable by default, disable only during load?

        self.add_new_card_btn = ttk.Button(self.control_frame, text="Add New Card", command=self.add_new_card)
        self.add_new_card_btn.grid(row=0, column=2, sticky="w", padx=(0, 5))
        # self.add_new_card_btn.config(state=tk.DISABLED) # Enable by default?
        # --- END NEW BUTTONS ---

        self.counter_label = ttk.Label(self.control_frame, text="0/0")
        self.counter_label.grid(row=0, column=4, sticky="e") # Place counter in the last column

        # Row 2: Image display
        self.image_frame = ttk.Frame(root, borderwidth=1, relief="solid")
        self.image_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        # Placeholder for image
        self.image_label = ttk.Label(self.image_frame, text="Load a decklist or add a custom image to start")
        self.image_label.pack(expand=True, fill="both")
        self.current_image = None # Holds the PhotoImage object

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
        if not MTGPROXIES_AVAILABLE:
            self.save_pdf_btn.config(state=tk.DISABLED) # Disable if lib not found

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
                    # self.total_cards = data # Use len(self.images) instead
                    self.counter_label.config(text=f"Loading.../{data}") # Initial count display
                    self.progress_var.set(0)
                    # Show progress bar
                    self.image_label.pack_forget()
                    self.progress_text.pack(pady=(100, 10))
                    self.progress_bar.pack(fill="x", padx=50, pady=10)

                elif message == "progress":
                    # This might not be sent by the default fetch_scans_scryfall
                    pass
                    # percentage = (data / self.total_cards) * 100
                    # self.progress_var.set(percentage)
                    # self.progress_text.config(text=f"Loading cards... {data}/{self.total_cards}")

                elif message == "done":
                    self.images = list(data) # Ensure it's a mutable list of paths
                    # Hide progress and show first image
                    self.progress_bar.pack_forget()
                    self.progress_text.pack_forget()
                    self.image_label.pack(expand=True, fill="both")

                    # Enable buttons
                    if self.images:
                         self.update_button_states() # Use a helper function
                         self.current_index = 0
                         self.display_current_card()
                    else:
                         self.image_label.config(text="No cards found in decklist.")
                         self.update_button_states() # Update even if empty

                    # Re-enable load/add buttons
                    if MTGPROXIES_AVAILABLE: self.load_deck_btn.config(state=tk.NORMAL)
                    self.add_custom_btn.config(state=tk.NORMAL)
                    self.add_new_card_btn.config(state=tk.NORMAL)


                elif message == "error":
                    # Hide progress and show error
                    self.progress_bar.pack_forget()
                    self.progress_text.pack_forget()
                    self.image_label.pack(expand=True, fill="both")
                    self.image_label.config(text=f"Error: {data}", image="") # Clear any previous image
                    messagebox.showerror("Error", f"An error occurred: {data}")
                    # Re-enable load/add buttons
                    if MTGPROXIES_AVAILABLE: self.load_deck_btn.config(state=tk.NORMAL)
                    self.add_custom_btn.config(state=tk.NORMAL)
                    self.add_new_card_btn.config(state=tk.NORMAL)
                    # Disable other buttons
                    self.update_button_states()


                self.callback_queue.task_done()
        except queue.Empty:
            pass

        # Check again after 100ms
        self.root.after(100, self.poll_queue)

    def load_decklist(self):
        """Open a file dialog to select a decklist"""
        if not MTGPROXIES_AVAILABLE:
            messagebox.showerror("Error", "mtgproxies library not found. Cannot load decklist.")
            return

        file_path = filedialog.askopenfilename(
            title="Select Decklist",
            filetypes=[("Text files", "*.txt"), ("Deck files", "*.dec"), ("All files", "*.*")]
        )
        if file_path:
            # Disable buttons during loading
            self.load_deck_btn.config(state=tk.DISABLED)
            self.add_custom_btn.config(state=tk.DISABLED)
            self.add_new_card_btn.config(state=tk.DISABLED)
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)
            self.edit_btn.config(state=tk.DISABLED)
            self.save_pdf_btn.config(state=tk.DISABLED)
            self.image_label.config(text="Loading...", image="") # Clear image

            # Reset state
            self.current_index = 0
            self.images = []
            self.counter_label.config(text="Loading...")

            # Start the worker
            self.worker.load_decklist(file_path)

    # --- NEW METHOD ---
    def add_custom_image(self):
        """Opens a dialog to add a custom image to the list"""
        file_path = filedialog.askopenfilename(
            title="Select Custom Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*")]
        )
        if file_path:
            if not os.path.exists(file_path):
                 messagebox.showerror("Error", f"File not found: {file_path}")
                 return
            try:
                # Check if it's a valid image
                with Image.open(file_path) as img:
                    img.verify() # Verify headers
                # Add the path to the list
                self.images.append(file_path)
                self.current_index = len(self.images) - 1 # Go to the new image
                self.display_current_card()
                self.update_button_states() # Update nav/edit/save buttons
            except FileNotFoundError:
                 messagebox.showerror("Error", f"File not found: {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load or invalid image file: {file_path}\n{e}")


    # --- NEW PLACEHOLDER METHOD ---
    def add_new_card(self):
        """Placeholder for adding a new blank card or template"""
        print("Add New Card - Not implemented yet")
        messagebox.showinfo("Not Implemented", "Functionality to add a new card is not yet implemented.")
        # Future: Could add a placeholder path or generate a blank image and add its path


    def display_current_card(self):
        """Display the current card image"""
        if not self.images or not (0 <= self.current_index < len(self.images)):
             self.image_label.config(text="No card to display.", image="")
             self.counter_label.config(text="0/0")
             return

        image_path = self.images[self.current_index]
        self.counter_label.config(text=f"{self.current_index + 1}/{len(self.images)}")

        if not os.path.exists(image_path):
            self.image_label.config(text=f"Image file not found:\n{image_path}", image="")
            messagebox.showwarning("File Not Found", f"The image file for card {self.current_index + 1} was not found:\n{image_path}")
            self.update_button_states() # Still update buttons
            return

        try:
            # Use a new PIL Image object to ensure we're loading the latest version
            with open(image_path, 'rb') as f:
                img = Image.open(f).copy() # Load fresh copy
            self.display_image(img) # Resize and show

        except Exception as e:
            self.image_label.config(text=f"Failed to load image:\n{image_path}\n{e}", image="")
            messagebox.showerror("Image Load Error", f"Failed to load image:\n{image_path}\n{e}")
        finally:
            # Update navigation buttons AFTER trying to load
            self.update_button_states()


    def display_image(self, img):
        """Resize and display a PIL image in the image label"""
        try:
            # Resize image to fit the frame while maintaining aspect ratio
            img_width, img_height = img.size
            # Crucial: Update geometry manager to get actual frame size
            self.image_frame.update_idletasks()
            frame_width = self.image_frame.winfo_width()
            frame_height = self.image_frame.winfo_height()

            # If frame hasn't been drawn yet or is tiny, use reasonable defaults
            if frame_width <= 10: frame_width = 600
            if frame_height <= 10: frame_height = 400

            # Calculate scaling factor
            width_ratio = frame_width / img_width
            height_ratio = frame_height / img_height
            scale_factor = min(width_ratio, height_ratio, 1.0) # Don't scale up beyond 1.0 implicitly

            new_width = max(1, int(img_width * scale_factor * 0.95))  # 95% of available space, min 1 pixel
            new_height = max(1, int(img_height * scale_factor * 0.95))

            resized_img = img.resize((new_width, new_height), Image.LANCZOS)
            self.current_image = ImageTk.PhotoImage(resized_img) # Store reference

            # Update the image in the label
            self.image_label.config(image=self.current_image, text="")
        except Exception as e:
             print(f"Error displaying image: {e}")
             self.image_label.config(image="", text=f"Error displaying image: {e}")
             self.current_image = None


    def update_button_states(self):
        """Centralized function to update button states based on current state"""
        has_images = bool(self.images)
        num_images = len(self.images)

        # Navigation buttons
        self.prev_btn.config(state=tk.NORMAL if has_images and self.current_index > 0 else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if has_images and self.current_index < num_images - 1 else tk.DISABLED)

        # Edit and Save buttons (require images and potentially the library for saving)
        self.edit_btn.config(state=tk.NORMAL if has_images else tk.DISABLED)
        can_save = has_images and MTGPROXIES_AVAILABLE
        self.save_pdf_btn.config(state=tk.NORMAL if can_save else tk.DISABLED)

        # Add buttons are generally always enabled unless during load
        is_loading = self.load_deck_btn['state'] == tk.DISABLED # Check if loading is active
        self.add_custom_btn.config(state=tk.DISABLED if is_loading else tk.NORMAL)
        self.add_new_card_btn.config(state=tk.DISABLED if is_loading else tk.NORMAL)


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
        if not self.images or not (0 <= self.current_index < len(self.images)):
            return

        # Check if path exists before editing
        image_path = self.images[self.current_index]
        if not os.path.exists(image_path):
            messagebox.showerror("Error", f"Cannot edit. Image file not found:\n{image_path}")
            return

        try:
            # Dynamically import here to avoid circular dependencies if editor imports this
            import card_editor # Assuming card_editor.py is in the right place relative to this script

            # Define callback for when an image is saved in the editor
            def on_image_saved(saved_path):
                print(f"Editor saved image: {saved_path}")
                # Update the path in our list if it changed (e.g., "Save As")
                # This assumes the editor saves back to the original path by default
                # or the callback provides the *new* path if "Save As" was used.
                # If editor always saves to original path, no list update needed.
                # If editor might use "Save As", this needs more robust handling.
                # For now, assume it overwrites or we just reload current index.
                # self.images[self.current_index] = saved_path # Uncomment if editor returns new path

                # Refresh the display to show the potentially updated image
                # Schedule the refresh in the main loop
                self.root.after(50, self.display_current_card)

            # Launch the editor with the current image path and callback
            print(f"Launching editor for: {image_path}")
            self.editor_window = card_editor.launch_editor(image_path, on_save_callback=on_image_saved)

        except ImportError:
            messagebox.showerror("Error", "Could not import the Card Editor module.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Card Editor: {e}")
            import traceback
            traceback.print_exc()


    def save_to_pdf(self):
        """Save the current list of image paths to PDF"""
        if not self.images:
            messagebox.showwarning("No Cards", "No cards available to save")
            return
        if not MTGPROXIES_AVAILABLE:
            messagebox.showerror("Error", "mtgproxies library not found. Cannot save PDF.")
            return

        # Verify all image paths exist before attempting to save
        missing_files = [p for p in self.images if not os.path.exists(p)]
        if missing_files:
             messagebox.showerror("Missing Files", "Cannot save PDF. The following image files are missing:\n\n" + "\n".join(missing_files))
             return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            title="Save Proxies as PDF"
        )
        if save_path:
            # Disable the button during saving
            self.save_pdf_btn.config(state=tk.DISABLED)
            # Pass the current list of image paths
            paths_to_save = list(self.images)

            # Run in a separate thread to avoid freezing the UI
            def save_thread():
                success = self.worker.save_to_pdf(paths_to_save, save_path)
                # Update UI from main thread using lambda to capture current state
                self.root.after(0, lambda s=success, p=save_path: self._save_complete(s, p))

            threading.Thread(target=save_thread, daemon=True).start()

    def _save_complete(self, success, path):
        """Called when save is complete"""
        # Re-enable button only if conditions are still met
        self.update_button_states()
        if success:
            messagebox.showinfo("Success", f"Successfully saved to {path}")
        else:
            messagebox.showerror("Error", f"Failed to save to {path}")

    def save_token(self):
        """Save the Scryfall API token (if needed)"""
        # This function likely isn't needed if mtgproxies handles auth internally
        # Keeping it as placeholder based on original code
        token = self.token_entry.get()
        if token:
            try:
                # Save token to a config file (consider a more robust config method)
                with open("token.txt", "w") as f:
                    f.write(token)
                messagebox.showinfo("Token Saved", "API token has been saved (token.txt)")
            except Exception as e:
                 messagebox.showerror("Error", f"Failed to save token: {e}")
        else:
            messagebox.showwarning("Empty Token", "Please enter a token before saving")

    def on_closing(self):
        """Handle window close event"""
        if self.worker.running:
            if messagebox.askyesno("Quit", "Card processing might still be running. Are you sure you want to quit?"):
                # Optionally, try to signal the worker to stop cleanly here
                self.root.destroy()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MTGProxyGUI(root)
    # Handle resizing events to update the displayed image
    def on_resize(event):
        # Add a small delay to avoid excessive updates during resize drag
        if hasattr(app, '_resize_job'):
             root.after_cancel(app._resize_job)
        app._resize_job = root.after(250, app.display_current_card) # Call display_current which calls display_image

    # Bind configure only to the image frame as that's the relevant size
    app.image_frame.bind("<Configure>", on_resize)

    root.mainloop()