import RPi.GPIO as GPIO
import time
import argparse

# Parse command line arguments
parser = argparse.ArgumentParser(description='Control servos to open or close positions.')
parser.add_argument('position', choices=['open', 'close'], help='Position to set servos: "open" or "close"')
args = parser.parse_args()

# Pin configuration
SERVO_PIN_PAPER = 12  # GPIO pin connected to the paper servo
SERVO_PIN_PLASTIC = 13  # GPIO pin connected to the plastic servo
SERVO_PIN_METAL = 18  # GPIO pin connected to the metal servo
SERVO_PIN_TRASH = 21  # GPIO pin connected to the trash servo

# Define servo positions
OPEN_ANGLE = 0   # Angle for "open" position
CLOSED_ANGLE = 80  # Angle for "closed" position
OPEN_ANGLE_TRASH = 170  # Angle for trash servo when "open"

# Set up GPIO
GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
GPIO.setup(SERVO_PIN_PAPER, GPIO.OUT)
GPIO.setup(SERVO_PIN_PLASTIC, GPIO.OUT)
GPIO.setup(SERVO_PIN_METAL, GPIO.OUT)
GPIO.setup(SERVO_PIN_TRASH, GPIO.OUT)

# Servo setup
servo_paper_pwm = GPIO.PWM(SERVO_PIN_PAPER, 50)  # Set servo frequency to 50Hz
servo_plastic_pwm = GPIO.PWM(SERVO_PIN_PLASTIC, 50)
servo_metal_pwm = GPIO.PWM(SERVO_PIN_METAL, 50)
servo_trash_pwm = GPIO.PWM(SERVO_PIN_TRASH, 50)

# Start all servos with 0% duty cycle
servo_paper_pwm.start(0)
servo_plastic_pwm.start(0)
servo_metal_pwm.start(0)
servo_trash_pwm.start(0)

def set_servo_angle(servo_pwm, pin, angle):
    """Set servo angle using PWM."""
    duty_cycle = 2.5 + (angle / 18.0)  # Convert angle (0-180) to duty cycle (2-12)
    servo_pwm.ChangeDutyCycle(duty_cycle)
    time.sleep(0.7)
    servo_pwm.ChangeDutyCycle(0)

def set_all_servos(position):
    """
    Set all servos to either open or closed position
    
    Args:
        position: 'open' or 'close'
    """
    angle = OPEN_ANGLE if position == 'open' else CLOSED_ANGLE
    trash_angle = OPEN_ANGLE_TRASH if position == 'open' else CLOSED_ANGLE
    action_word = "Opening" if position == 'open' else "Closing"
    
    print(f"{action_word} all servos...")
    
    # Set metal servo
    set_servo_angle(servo_metal_pwm, SERVO_PIN_METAL, angle)
    print(f"Metal servo {position}ed")
    time.sleep(2)
    
    # Set plastic servo
    set_servo_angle(servo_plastic_pwm, SERVO_PIN_PLASTIC, angle)
    print(f"Plastic servo {position}ed")
    time.sleep(2)
    
    # Set paper servo
    set_servo_angle(servo_paper_pwm, SERVO_PIN_PAPER, angle)
    print(f"Paper servo {position}ed")
    time.sleep(2)
    
    # Set trash servo
    set_servo_angle(servo_trash_pwm, SERVO_PIN_TRASH, trash_angle)
    print(f"Trash servo {position}ed")
    
    print(f"All servos have been {position}ed!")

try:
    # Execute the command based on the parameter
    set_all_servos(args.position)
    time.sleep(2)  # Keep the servos in position for 2 seconds

except KeyboardInterrupt:
    print("Program stopped by user")

finally:
    # Clean up
    servo_paper_pwm.stop()
    servo_plastic_pwm.stop()
    servo_metal_pwm.stop()
    servo_trash_pwm.stop()
    GPIO.cleanup()
    print("Cleanup complete")