#!/usr/bin/env python3
import time
from picamera2 import Picamera2
from datetime import datetime
import os
import subprocess
from PIL import Image

def kill_existing_camera_processes():
    """Kill any existing camera processes that might be running"""
    try:
        # Try to kill any existing python processes that might be using the camera
        subprocess.run(["pkill", "-f", "python.*picamera"], stderr=subprocess.DEVNULL)
        time.sleep(1)  # Give processes time to terminate
        return True
    except Exception as e:
        print(f"Warning: Failed to kill existing camera processes: {e}")
        return False

def take_photo_force(filename=None, crop_center=True):
    """
    Take a photo using Picamera2, first making sure no other process is using the camera.
    
    Args:
        filename: Optional filename for the saved image (default: timestamp-based name)
        crop_center: Whether to crop the image to the middle 75% (default: True)
    
    Returns:
        The filename of the saved image
    """
    # Create default filename based on timestamp if none provided
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"photo_{timestamp}.jpg"
    
    # Make sure no other process is using the camera
    kill_existing_camera_processes()
    
    picam2 = None
    try:
        # Force device selection - helpful if multiple cameras are available
        picam2 = Picamera2(0)  # Explicitly select the first camera
        
        # Use a simple configuration
        config = picam2.create_still_configuration()
        picam2.configure(config)
        
        # Start without preview to avoid event loop issues
        picam2.start(show_preview=False)
        
        # Wait for camera to initialize
        time.sleep(2)
        
        # Capture the image
        picam2.capture_file(filename)
        print(f"Photo saved as {filename}")
        
        # Clean up
        picam2.stop()
        picam2.close()
        
        # Crop the image if requested
        if crop_center:
            crop_center_of_image(filename)
        
        return filename
        
    except Exception as e:
        print(f"Error taking photo: {e}")
        # Try to clean up if an error occurred
        if picam2:
            try:
                picam2.stop()
                picam2.close()
            except:
                pass
        return None

def crop_center_of_image(image_path):
    """
    Crop the image to just the middle 75% of the original.
    
    Args:
        image_path: Path to the image file to crop
    """
    try:
        # Open the image
        with Image.open(image_path) as img:
            # Get dimensions
            width, height = img.size
            
            # Calculate crop box (middle 75%)
            crop_width = int(width * 0.65)
            crop_height = int(height * 0.65)
            
            # Calculate coordinates for centering
            left = (width - crop_width) // 2
            top = (height - crop_height) // 2
            right = left + crop_width
            bottom = top + crop_height
            
            # Crop the image
            cropped_img = img.crop((left, top, right, bottom))
            
            # Save the cropped image (overwrite original)
            cropped_img.save(image_path)
            
            print(f"Image cropped to middle 75%: {width}x{height} → {crop_width}x{crop_height}")
    except Exception as e:
        print(f"Error cropping image: {e}")

if __name__ == "__main__":
    photo = take_photo_force(crop_center=True)
    if photo and os.path.exists(photo):
        print(f"Successfully captured and cropped: {photo}")
        # Optionally display the image if running on a system with display
        try:
            subprocess.run(["xdg-open", photo], stderr=subprocess.DEVNULL)
        except:
            pass
    else:
        print("Failed to capture photo")
