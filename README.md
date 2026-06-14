# ESP32 for tracking maggot farm
It's only a simulation, so it's inaccurate to be implemented in a real maggot farm. The only thing you need is:
- ESP32 (with MicroPython installed. Check their [website](https://micropython.org/))
- LED
- DHT22
- 3V Buzzer
- 220 ohm Resistor (for the LED)
- and a Breadboard (if needed)

# How to Setup
## Connecting The ESP32 to the MQTT
After you setup MicroPython to your ESP32, you need to configure the config.json. 
There, you need to fill your:
- Designated wifi,
- The MQTT broker
- The MQTT user and password for the ESP32 (if you configure it)
After that, try to connect to the MQTT and make sure all set.
## Connecting The Client to the MQTT

