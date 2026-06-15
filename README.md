# ESP32 for tracking maggot farm
It's only a simulation, so it's inaccurate to be implemented in a real maggot farm. The only thing you need is:
- ESP32 (with MicroPython installed. Check their [website](https://micropython.org/))
- LED
- DHT22
- 3V Buzzer
- 220 ohm Resistor (for the LED)
- and a Breadboard (if needed)

Here's the setup
<img width="1755" height="1203" alt="espbb" src="https://github.com/user-attachments/assets/8c1abe89-8d13-4cf8-80a2-7a89120c77a3" />

# How to Setup
## Connecting The ESP32 to the MQTT
After you setup MicroPython to your ESP32, you need to configure the config.json. 
There, you need to fill your:
- Designated wifi,
- The MQTT broker
- The MQTT user and password for the ESP32 (if you configure it)
After that, try to connect to the MQTT and make sure all set.
## Connecting The Client to the MQTT
You can check this [repo](https://github.com/Daorza/Maggots-for-Mobile-Computing) for instruction

