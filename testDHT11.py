#!/usr/bin/env python3

from time import sleep

def read_bus(path):
    """Read a value from the IIO bus"""
    with open(path, 'r') as f:
        return float(f.read().strip())

def dht11_val():
    t = h = 0
    try:
        t = read_bus("/sys/bus/iio/devices/iio:device0/in_temp_input")/1000
        h = read_bus("/sys/bus/iio/devices/iio:device0/in_humidityrelative_input")/1000
    except Exception as e:
        print(f"Error reading sensor: {e}")
        t = h = "N/A"
    return t, h

print("DHT11 Sensor Test")
print("=================")
print("Press CTRL+C to exit")
print()


try:
    while True:
        (temp, hum) = dht11_val()
        if temp != "N/A" and hum != "N/A":
            print(f"Temperature {temp:.2f}°C, Humidity: {hum:.2f}%")
        else:
            print("Failed to read from DHT11 sensor")
        sleep(2)
except KeyboardInterrupt:
    print("\nExiting program")