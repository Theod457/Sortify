import RPi.GPIO as GPIO
import time
import libcamera
import json
import paho.mqtt.client as mqtt
import numpy as np
import threading
import os
from picamera2 import Picamera2
from PIL import Image
from classification import classify_image

# Pin configuration
CAMERA_IR_SENSOR_PIN = 14  # GPIO pin connected to the camera-use IR sensor's OUT pin
BIN_PAPER_IR_SENSOR_PIN = 20  # GPIO pin connected to the paper bin IR sensor
BIN_PLASTIC_IR_SENSOR_PIN = 16  # GPIO pin connected to the plastic bin IR sensor
BIN_METAL_IR_SENSOR_PIN = 17  # GPIO pin connected to the metal bin IR sensor
BIN_TRASH_IR_SENSOR_PIN = 27  # GPIO pin connected to the trash bin IR sensor
DHT_SENSOR_PIN = 15  # GPIO pin connected to the DHT11 sensor
SERVO_PIN_PAPER = 12  # GPIO pin connected to the servo signal
SERVO_PIN_PLASTIC = 13  # GPIO pin connected to the servo signal
SERVO_PIN_METAL = 18  # GPIO pin connected to the servo signal
SERVO_PIN_TRASH = 21  # GPIO pin connected to the servo signal

# Servo angle constants
SERVO_CLOSE = 80  # Neutral position for servos
SERVO_OPEN = 0  # Open position for bins

# ThingsBoard configuration
THINGSBOARD_HOST = "demo.thingsboard.io"
ACCESS_TOKEN = "dR9THgVKZUAOpnOpgKxp"

# UI configuration
UI_ENABLED = True
classification_result = None
last_classification_time = 0

# Initialize MQTT client
client = mqtt.Client()
client.username_pw_set(ACCESS_TOKEN)
client.connect(THINGSBOARD_HOST, 1883, 60)
client.loop_start()

# Initialize Picamera2
camera = Picamera2()
camera.start()

# Set up GPIO
GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
GPIO.setup(CAMERA_IR_SENSOR_PIN, GPIO.IN)
GPIO.setup(BIN_PAPER_IR_SENSOR_PIN, GPIO.IN)
GPIO.setup(BIN_PLASTIC_IR_SENSOR_PIN, GPIO.IN)
GPIO.setup(BIN_METAL_IR_SENSOR_PIN, GPIO.IN)
GPIO.setup(BIN_TRASH_IR_SENSOR_PIN, GPIO.IN)
GPIO.setup(SERVO_PIN_PAPER, GPIO.OUT)
GPIO.setup(SERVO_PIN_PLASTIC, GPIO.OUT)
GPIO.setup(SERVO_PIN_METAL, GPIO.OUT)
GPIO.setup(SERVO_PIN_TRASH, GPIO.OUT)

# Servo setup
servo_paper_pwm = GPIO.PWM(SERVO_PIN_PAPER, 50)  # Set servo frequency
servo_plastic_pwm = GPIO.PWM(SERVO_PIN_PLASTIC, 50)
servo_metal_pwm = GPIO.PWM(SERVO_PIN_METAL, 50)
servo_trash_pwm = GPIO.PWM(SERVO_PIN_TRASH, 50)

# Start all servos with 0% duty cycle
servo_paper_pwm.start(0)
servo_plastic_pwm.start(0)
servo_metal_pwm.start(0)
servo_trash_pwm.start(0)

# Variables for timing
last_capture_time = 0  # Tracks the last capture time for the object
detection_start_time = None  # Tracks when detection starts for the object
paper_bin_detection_start_time = None  # Tracks when the paper bin IR sensor detects full
plastic_bin_detection_start_time = None  # Tracks when the plastic bin IR sensor detects full
metal_bin_detection_start_time = None  # Tracks when the metal bin IR sensor detects full
trash_bin_detection_start_time = None  # Tracks when the trash bin IR sensor detects full
DETECTION_DURATION = 1  # Time (seconds) the object must be detected
COOLDOWN_PERIOD = 5  # Time (seconds) to wait before next capture
BIN_FULL_THRESHOLD = 5  # Time (seconds) the bin-use IR sensor must be active to consider the bin full

# Variables for bin full/not full status
paper_bin_full_sent = None  # Tracks the last sent paper bin full status
plastic_bin_full_sent = None  # Tracks the last sent plastic bin full status
metal_bin_full_sent = None  # Tracks the last sent metal bin full status
trash_bin_full_sent = None  # Tracks the last sent trash bin full status

# Averaging parameters for Temp/Humidity data processing 
num_readings = 10 
temperature_readings = []
humidity_readings = []

def get_average_reading(readings, new_reading):
    if len(readings) >= num_readings:
        readings.pop(0)  # Remove the oldest reading
    readings.append(new_reading)
    return round(np.mean(readings), 2)

# 80 degree close, 0 degree open
def set_servo_angle(servo_pwm, pin, angle):
    duty_cycle = 2.5 + (angle / 18)  # Convert angle (0-180) to duty cycle (2-12)
    servo_pwm.ChangeDutyCycle(duty_cycle)
    time.sleep(1.0)
    servo_pwm.ChangeDutyCycle(0)

# Close all bins
set_servo_angle(servo_metal_pwm, SERVO_PIN_METAL, SERVO_CLOSE)
time.sleep(3)
set_servo_angle(servo_plastic_pwm, SERVO_PIN_PLASTIC, SERVO_CLOSE)
time.sleep(3)
set_servo_angle(servo_paper_pwm, SERVO_PIN_PAPER, SERVO_CLOSE)
time.sleep(3)
set_servo_angle(servo_trash_pwm, SERVO_PIN_TRASH, SERVO_CLOSE)
time.sleep(3)

def read_bus(path):
    """Read a value from the IIO bus"""
    try:
        with open(path, 'r') as f:
            return float(f.read().strip())
    except Exception as e:
        print(f"Error reading sensor: {e}")
        return None

def read_dht11():
    try:
        temperature = round(read_bus("/sys/bus/iio/devices/iio:device0/in_temp_input")/1000, 2)
        humidity = round(read_bus("/sys/bus/iio/devices/iio:device0/in_humidityrelative_input")/1000, 2)
        return humidity, temperature
    except Exception:
        return None, None

def update_ui_files(current_classification=None, bin_status=None):
    """Update files for UI communication"""
    
    # Update classification result
    if current_classification is not None:
        try:
            with open("classification_result.txt", "w") as f:
                f.write(current_classification)
        except Exception as e:
            print(f"Error updating classification file: {e}")
    
    # Update bin status
    if bin_status is not None:
        try:
            with open("bin_status.txt", "w") as f:
                json.dump(bin_status, f)
        except Exception as e:
            print(f"Error updating bin status file: {e}")

def handle_bin_detection(current_time):
    global paper_bin_detection_start_time, plastic_bin_detection_start_time, metal_bin_detection_start_time, trash_bin_detection_start_time
    global paper_bin_full_sent, plastic_bin_full_sent, metal_bin_full_sent, trash_bin_full_sent
    
    # Read bin IR sensors
    # paper_bin_sensor = GPIO.input(BIN_PAPER_IR_SENSOR_PIN)
    # plastic_bin_sensor = GPIO.input(BIN_PLASTIC_IR_SENSOR_PIN)
    metal_bin_sensor = GPIO.input(BIN_METAL_IR_SENSOR_PIN)
    # trash_bin_sensor = GPIO.input(BIN_TRASH_IR_SENSOR_PIN)
    
    # Handle paper bin detection
    # if paper_bin_sensor == 0:  # Bin full detected
    #     if paper_bin_detection_start_time is None:
    #         paper_bin_detection_start_time = current_time
    #     elif current_time - paper_bin_detection_start_time >= BIN_FULL_THRESHOLD:
    #         if paper_bin_full_sent != 1:  # Send telemetry if not already sent
    #             client.publish("v1/devices/me/telemetry", json.dumps({"paperFull": 1}), qos=1)
    #             print("Paper bin is full! Sent telemetry: paperFull: 1")
    #             paper_bin_full_sent = 1
    # else:  # Bin not full
    #     if paper_bin_detection_start_time is not None:
    #         if current_time - paper_bin_detection_start_time >= BIN_FULL_THRESHOLD and paper_bin_full_sent != 0:
    #             client.publish("v1/devices/me/telemetry", json.dumps({"paperFull": 0}), qos=1)
    #             print("Paper bin is not full! Sent telemetry: paperFull: 0")
    #             paper_bin_full_sent = 0
    #     paper_bin_detection_start_time = None  # Reset detection start time
    
    # # Handle plastic bin detection
    # if plastic_bin_sensor == 0:  # Bin full detected
    #     if plastic_bin_detection_start_time is None:
    #         plastic_bin_detection_start_time = current_time
    #     elif current_time - plastic_bin_detection_start_time >= BIN_FULL_THRESHOLD:
    #         if plastic_bin_full_sent != 1:  # Send telemetry if not already sent
    #             client.publish("v1/devices/me/telemetry", json.dumps({"plasticFull": 1}), qos=1)
    #             print("Plastic bin is full! Sent telemetry: plasticFull: 1")
    #             plastic_bin_full_sent = 1
    # else:  # Bin not full
    #     if plastic_bin_detection_start_time is not None:
    #         if current_time - plastic_bin_detection_start_time >= BIN_FULL_THRESHOLD and plastic_bin_full_sent != 0:
    #             client.publish("v1/devices/me/telemetry", json.dumps({"plasticFull": 0}), qos=1)
    #             print("Plastic bin is not full! Sent telemetry: plasticFull: 0")
    #             plastic_bin_full_sent = 0
    #     plastic_bin_detection_start_time = None  # Reset detection start time
    
    # Handle metal bin detection
    if metal_bin_sensor == 0:  # Bin full detected
        if metal_bin_detection_start_time is None:
            metal_bin_detection_start_time = current_time
        elif current_time - metal_bin_detection_start_time >= BIN_FULL_THRESHOLD:
            if metal_bin_full_sent != 1:  # Send telemetry if not already sent
                client.publish("v1/devices/me/telemetry", json.dumps({"metalFull": 1}), qos=1)
                print("Metal bin is full! Sent telemetry: metalFull: 1")
                metal_bin_full_sent = 1
    else:  # Bin not full
        if metal_bin_detection_start_time is not None:
            if current_time - metal_bin_detection_start_time >= BIN_FULL_THRESHOLD and metal_bin_full_sent != 0:
                client.publish("v1/devices/me/telemetry", json.dumps({"metalFull": 0}), qos=1)
                print("Metal bin is not full! Sent telemetry: metalFull: 0")
                metal_bin_full_sent = 0
        metal_bin_detection_start_time = None  # Reset detection start time
    
    # # Handle trash bin detection
    # if trash_bin_sensor == 0:  # Bin full detected
    #     if trash_bin_detection_start_time is None:
    #         trash_bin_detection_start_time = current_time
    #     elif current_time - trash_bin_detection_start_time >= BIN_FULL_THRESHOLD:
    #         if trash_bin_full_sent != 1:  # Send telemetry if not already sent
    #             client.publish("v1/devices/me/telemetry", json.dumps({"trashFull": 1}), qos=1)
    #             print("Trash bin is full! Sent telemetry: trashFull: 1")
    #             trash_bin_full_sent = 1
    # else:  # Bin not full
    #     if trash_bin_detection_start_time is not None:
    #         if current_time - trash_bin_detection_start_time >= BIN_FULL_THRESHOLD and trash_bin_full_sent != 0:
    #             client.publish("v1/devices/me/telemetry", json.dumps({"trashFull": 0}), qos=1)
    #             print("Trash bin is not full! Sent telemetry: trashFull: 0")
    #             trash_bin_full_sent = 0
    #     trash_bin_detection_start_time = None  # Reset detection start time
    
    # Update UI with bin status if enabled
    if UI_ENABLED:
        bin_status = {
            "paper": paper_bin_full_sent == 1,
            "plastic": plastic_bin_full_sent == 1,
            "metal": metal_bin_full_sent == 1,
            "trash": trash_bin_full_sent == 1
        }
        update_ui_files(bin_status=bin_status)


def handle_object_detection(camera_sensor_value, current_time):
    """Handles object detection logic."""
    global detection_start_time, last_capture_time
    if camera_sensor_value == 0:  # Object detected
        if detection_start_time is None:
            detection_start_time = current_time  
        elif current_time - detection_start_time >= DETECTION_DURATION:
            if current_time - last_capture_time >= COOLDOWN_PERIOD:
                capture_and_classify_object(current_time)
                detection_start_time = None  # Reset detection timer
    else:
        detection_start_time = None  # Reset detection if no object is detected


def capture_and_classify_object(current_time):
    global last_capture_time, classification_result
    
    filename = f"object.jpg"
    print(f"Object detected! Capturing image: {filename}")
    camera.capture_file(filename)
    original_img = Image.open(filename)
    oriented_img = original_img.transpose(method=Image.FLIP_TOP_BOTTOM).transpose(method=Image.FLIP_LEFT_RIGHT) # orient the image correctly
    oriented_img.save(filename)

    classification_result = classify_image(filename)
    print(f"Classification result: {classification_result}")
    
    # Update UI if enabled
    if UI_ENABLED:
        update_ui_files(current_classification=classification_result)

    # Send telemetry data
    telemetry_data = {
        "paper": 1 if classification_result == "paper" else 0,
        "plastic": 1 if classification_result == "plastic" else 0,
        "metal": 1 if classification_result == "metal" else 0,
        "trash": 1 if classification_result == "trash" else 0
    }
    client.publish("v1/devices/me/telemetry", json.dumps(telemetry_data), qos=1)
    print(f"Classification data sent to ThingsBoard: {telemetry_data}")

    # Control servos based on classification result
    if classification_result == "paper":
        print("Moving servo to position for paper")
        set_servo_angle(servo_paper_pwm, SERVO_PIN_PAPER, SERVO_OPEN)
        time.sleep(2)
        set_servo_angle(servo_trash_pwm, SERVO_PIN_TRASH, 160)
        time.sleep(2)
        set_servo_angle(servo_paper_pwm, SERVO_PIN_PAPER, SERVO_CLOSE)
        set_servo_angle(servo_trash_pwm, SERVO_PIN_TRASH, SERVO_CLOSE)
    elif classification_result == "plastic":
        print("Moving servo to position for plastic")
        set_servo_angle(servo_plastic_pwm, SERVO_PIN_PLASTIC, SERVO_OPEN)
        time.sleep(2)
        set_servo_angle(servo_trash_pwm, SERVO_PIN_TRASH, 160)
        time.sleep(2)
        set_servo_angle(servo_plastic_pwm, SERVO_PIN_PLASTIC, SERVO_CLOSE)
        set_servo_angle(servo_trash_pwm, SERVO_PIN_TRASH, SERVO_CLOSE)
    elif classification_result == "metal":
        print("Moving servo to position for metal")
        set_servo_angle(servo_metal_pwm, SERVO_PIN_METAL, SERVO_OPEN)
        time.sleep(2)
        set_servo_angle(servo_trash_pwm, SERVO_PIN_TRASH, 160)
        time.sleep(2)
        set_servo_angle(servo_metal_pwm, SERVO_PIN_METAL, SERVO_CLOSE)
        set_servo_angle(servo_trash_pwm, SERVO_PIN_TRASH, SERVO_CLOSE)
    else:  # Assume trash
        print("Moving servo to position for trash")
        set_servo_angle(servo_trash_pwm, SERVO_PIN_TRASH, 0)
        time.sleep(2)
        set_servo_angle(servo_trash_pwm, SERVO_PIN_TRASH, SERVO_CLOSE)

    last_capture_time = current_time

# Import the UI code
try:
    from ui_integration import start_ui
    ui_import_success = True
except ImportError:
    print("UI integration module not found. Running without UI.")
    ui_import_success = False

def main():
    print("Setup ready")
    print("Monitoring IR sensors and DHT11 sensor...")
    
    # Start UI in a separate thread if enabled and import was successful
    if UI_ENABLED and ui_import_success:
        ui_thread = threading.Thread(target=start_ui)
        ui_thread.daemon = True
        ui_thread.start()
        print("UI started in background")
    
    while True:
        camera_sensor_value = GPIO.input(CAMERA_IR_SENSOR_PIN)
        current_time = time.time()

        handle_bin_detection(current_time)
        handle_object_detection(camera_sensor_value, current_time)
        
        # Read DHT11 sensor
        humidity, temperature = read_dht11()
        if humidity is not None and temperature is not None:
            avg_humidity = get_average_reading(humidity_readings, humidity)
            avg_temperature = get_average_reading(temperature_readings, temperature)
            telemetry_data = {
                "temperature": avg_temperature,
                "humidity": avg_humidity,
            }
            # Send data to ThingsBoard
            client.publish("v1/devices/me/telemetry", json.dumps(telemetry_data), qos=1)
            print(f"Temp/Humidity data sent to ThingsBoard: {telemetry_data}")
            try:
                with open("sensor_data.txt", "w") as f:
                        json.dump({"temperature": avg_temperature, "humidity": avg_humidity}, f)
            except Exception as e:
                print(f"Error updating sensor data file: {e}")
        else:
            print("Failed to read DHT11 sensor")
        
        time.sleep(1)  # Adjust as needed

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Exiting program...")

    finally:
        client.loop_stop()
        client.disconnect()
        set_servo_angle(servo_metal_pwm, SERVO_PIN_METAL, SERVO_CLOSE)
        time.sleep(3)
        set_servo_angle(servo_plastic_pwm, SERVO_PIN_PLASTIC, SERVO_CLOSE)
        time.sleep(3)
        set_servo_angle(servo_paper_pwm, SERVO_PIN_PAPER, SERVO_CLOSE)
        time.sleep(3)
        set_servo_angle(servo_trash_pwm, SERVO_PIN_TRASH, SERVO_CLOSE)
        time.sleep(3)
        servo_paper_pwm.stop()  # Stop PWM
        servo_plastic_pwm.stop()
        servo_metal_pwm.stop()
        servo_trash_pwm.stop()
        camera.stop_preview()  # Stop preview if used
        camera.close()  # Clean up the camera
        GPIO.cleanup()  # Clean up GPIO settings