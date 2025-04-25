import tkinter as tk
from tkinter import ttk
import json
import time
import threading
import os
from PIL import Image, ImageTk

# Global variables to track UI state
last_classification = None
bin_statuses = {"paper": False, "plastic": False, "metal": False, "trash": False}
last_image_time = 0
last_temp = 0
last_humidity = 0

def load_classification():
    """Load the latest classification result from file"""
    try:
        if os.path.exists("classification_result.txt"):
            with open("classification_result.txt", "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return None

def load_bin_status():
    """Load the latest bin status from file"""
    try:
        if os.path.exists("bin_status.txt"):
            with open("bin_status.txt", "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"paper": False, "plastic": False, "metal": False, "trash": False}

def load_sensor_data():
    """Load temperature and humidity data"""
    try:
        if os.path.exists("sensor_data.txt"):
            with open("sensor_data.txt", "r") as f:
                data = json.load(f)
                return data.get("temperature", 0), data.get("humidity", 0)
    except Exception:
        pass
    return 0, 0

class RecyclingUI:
    def __init__(self, root):
        self.root = root
        root.title("Smart Recycling System")
        root.geometry("800x600")
        root.configure(bg="#f0f0f0")
        
        # Set application style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('TLabel', background='#f0f0f0', font=('Helvetica', 11))
        self.style.configure('Header.TLabel', font=('Helvetica', 16, 'bold'))
        self.style.configure('Result.TLabel', font=('Helvetica', 14), padding=10)
        self.style.configure('Full.TLabel', background='#ff6b6b', foreground='white', font=('Helvetica', 11, 'bold'))
        self.style.configure('Empty.TLabel', background='#51cf66', foreground='white', font=('Helvetica', 11, 'bold'))
        
        # Create main container
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header section
        self.header_frame = ttk.Frame(self.main_frame)
        self.header_frame.pack(fill=tk.X, pady=10)
        
        self.header_label = ttk.Label(self.header_frame, text="Smart Recycling System", style='Header.TLabel')
        self.header_label.pack(side=tk.LEFT)
        
        self.sensor_frame = ttk.Frame(self.header_frame)
        self.sensor_frame.pack(side=tk.RIGHT)
        
        self.temp_label = ttk.Label(self.sensor_frame, text="Temperature: -- °C")
        self.temp_label.pack(side=tk.TOP, anchor=tk.E)
        
        self.humidity_label = ttk.Label(self.sensor_frame, text="Humidity: -- %")
        self.humidity_label.pack(side=tk.TOP, anchor=tk.E)
        
        # Separator
        ttk.Separator(self.main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Content section with two columns
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left column: Image and classification result
        self.left_frame = ttk.Frame(self.content_frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.image_frame = ttk.Frame(self.left_frame, borderwidth=2, relief=tk.GROOVE, padding=5)
        self.image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.image_label = ttk.Label(self.image_frame, text="No image captured yet")
        self.image_label.pack(fill=tk.BOTH, expand=True)
        
        self.result_frame = ttk.Frame(self.left_frame)
        self.result_frame.pack(fill=tk.X)
        
        self.result_label = ttk.Label(self.result_frame, text="Waiting for classification...",
                                     style='Result.TLabel', anchor=tk.CENTER)
        self.result_label.pack(fill=tk.X)
        
        # Right column: Bin status
        self.right_frame = ttk.Frame(self.content_frame)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        self.bin_label = ttk.Label(self.right_frame, text="Bin Status", style='Header.TLabel')
        self.bin_label.pack(fill=tk.X, pady=(0, 10))
        
        self.bins_frame = ttk.Frame(self.right_frame)
        self.bins_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create bin status indicators
        self.bin_indicators = {}
        bin_types = [("Paper", "#4dabf7"), ("Plastic", "#ffd43b"), ("Metal", "#868e96"), ("Trash", "#495057")]
        
        for idx, (bin_type, color) in enumerate(bin_types):
            bin_frame = ttk.Frame(self.bins_frame, padding=10)
            bin_frame.pack(fill=tk.X, pady=5)
            bin_frame.configure(style='TFrame')
            
            icon_canvas = tk.Canvas(bin_frame, width=40, height=40, bg=color, highlightthickness=0)
            icon_canvas.pack(side=tk.LEFT, padx=(0, 10))
            
            # Create bin icon
            icon_canvas.create_rectangle(5, 10, 35, 40, outline=color, fill=color, width=2)
            icon_canvas.create_rectangle(5, 5, 35, 10, outline=color, fill=color, width=2)
            
            bin_info_frame = ttk.Frame(bin_frame)
            bin_info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            bin_name_label = ttk.Label(bin_info_frame, text=f"{bin_type} Bin")
            bin_name_label.pack(anchor=tk.W)
            
            bin_status_label = ttk.Label(bin_info_frame, text="Empty", style='Empty.TLabel', padding=3)
            bin_status_label.pack(anchor=tk.W, pady=(5, 0))
            
            self.bin_indicators[bin_type.lower()] = bin_status_label
        
        # Footer
        self.footer_frame = ttk.Frame(self.main_frame)
        self.footer_frame.pack(fill=tk.X, pady=10)
        
        self.status_label = ttk.Label(self.footer_frame, text="System Ready")
        self.status_label.pack(side=tk.LEFT)
        
        # Start update thread
        self.update_thread = threading.Thread(target=self.update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
    
    def update_classification(self, classification):
        """Update the classification result display"""
        if classification:
            result_text = f"Classification: {classification.upper()}"
            self.result_label.configure(text=result_text)
            
            # Update status message
            self.status_label.configure(text=f"Last classification: {classification} - {time.strftime('%H:%M:%S')}")
    
    def update_bin_status(self, bin_status):
        """Update bin status indicators"""
        for bin_type, is_full in bin_status.items():
            if bin_type in self.bin_indicators:
                if is_full:
                    self.bin_indicators[bin_type].configure(text="FULL", style='Full.TLabel')
                else:
                    self.bin_indicators[bin_type].configure(text="Empty", style='Empty.TLabel')
    
    def update_sensor_data(self, temperature, humidity):
        """Update temperature and humidity display"""
        self.temp_label.configure(text=f"Temperature: {temperature} °C")
        self.humidity_label.configure(text=f"Humidity: {humidity} %")
    
    def update_image(self):
        """Update the displayed image if available"""
        global last_image_time  # Moved to the beginning of the method
        
        if os.path.exists("cropped.jpg") and os.path.getmtime("cropped.jpg") > last_image_time:
            try:
                # Load and resize image
                img = Image.open("cropped.jpg")
                img = img.resize((300, 300), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                
                # Update image
                self.image_label.configure(image=photo)
                self.image_label.image = photo  # Keep a reference
                
                last_image_time = os.path.getmtime("cropped.jpg")
            except Exception as e:
                print(f"Error updating image: {e}")  
                  
    def update_loop(self):
        """Background loop to update UI data"""
        global last_classification, bin_statuses, last_temp, last_humidity
  
        while True:
            # Check for new classification
            classification = load_classification()
            if classification != last_classification:
                last_classification = classification
                self.root.after(0, lambda: self.update_classification(classification))
            
            # Check for bin status updates
            bin_status = load_bin_status()
            if bin_status != bin_statuses:
                bin_statuses = bin_status
                self.root.after(0, lambda: self.update_bin_status(bin_status))
            
            # Check for sensor data
            temp, humidity = load_sensor_data()
            if temp != last_temp or humidity != last_humidity:
                last_temp, last_humidity = temp, humidity
                self.root.after(0, lambda: self.update_sensor_data(temp, humidity))
            
            # Update image if changed
            self.root.after(0, self.update_image)
            
            # Sleep to prevent high CPU usage
            time.sleep(0.5)

def start_ui():
    """Start the UI application"""
    root = tk.Tk()
    app = RecyclingUI(root)
    
    # Add window icon if available
    try:
        root.iconphoto(True, tk.PhotoImage(file="icon.png"))
    except:
        pass
    
    root.mainloop()

if __name__ == "__main__":
    start_ui()