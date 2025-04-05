"""Fill operation methods for the Enhanced Content-Aware Fill dialog"""

import threading


class FillOperationsMixin:
    """Mixin class for fill operation methods"""

    def apply_fill(self):
        """Apply the selected fill algorithm to the image"""
        if self.is_processing:
            return

        self.is_processing = True
        self.progress.start(10)
        self.status_label.config(text="Applying fill...")
        self.apply_button.config(state="disabled")
        self.cancel_button.config(state="disabled")

        # Process in a thread to keep UI responsive
        def process_fill():
            try:
                algorithm = self.algorithm_var.get()

                # Apply the selected algorithm
                if algorithm in ["opencv_telea", "opencv_ns"]:
                    result = self.apply_opencv_inpainting(self.editor.working_image)
                elif algorithm == "patch_based":
                    result = self.apply_patch_based(self.editor.working_image)
                elif algorithm == "lama_pytorch":
                    result = self.apply_lama_pytorch(self.editor.working_image)
                elif algorithm == "deepfill_tf":
                    result = self.apply_deepfill_tf(self.editor.working_image)
                else:
                    result = self.editor.working_image  # Default fallback

                # Apply color influence if set
                influence = self.influence_var.get()
                if influence > 0:
                    result = self.apply_color_influence(result)

                # Update the working image
                self.editor.working_image = result

                # Update UI in main thread
                self.fill_dialog.after(0, self.finalize_fill)
            except Exception as e:
                print(f"Fill error: {e}")
                self.fill_dialog.after(0, lambda: self.status_label.config(text=f"Error: {str(e)}"))
                self.fill_dialog.after(0, lambda: self.apply_button.config(state="normal"))
                self.fill_dialog.after(0, lambda: self.cancel_button.config(state="normal"))
            finally:
                self.is_processing = False
                self.fill_dialog.after(0, self.progress.stop)

        # Start processing thread
        self.process_thread = threading.Thread(target=process_fill)
        self.process_thread.daemon = True
        self.process_thread.start()

    def finalize_fill(self):
        """Finalize the fill operation and close the dialog"""
        # Update display and reset selection
        self.editor.update_display()
        self.editor.reset_selection()
        self.editor.status_label.config(text=f"Content-aware fill applied using {self.algorithm_var.get()}")

        # Close dialog
        self.fill_dialog.destroy()

    def cancel_fill(self):
        """Cancel the fill operation and close the dialog"""
        # Stop processing if active
        self.is_processing = False
        if self.process_thread and self.process_thread.is_alive():
            # Can't really stop a thread, but we'll set the flag to abort processing
            pass

        # Reset eyedropper if active
        if self.eyedropper_active:
            self.editor.canvas.config(cursor="")
            self.eyedropper_active = False

        # Close dialog
        self.fill_dialog.destroy()
