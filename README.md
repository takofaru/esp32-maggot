# ESP32 for tracking maggot farm
System for the ESP32 to track temperature and humidity for a maggot farm. It's only a simulation, so it's inaccurate to be implemented in a real maggot farm.

## How to Setup
### Setup the ESP32
The only thing you need is:
- ESP32 (with MicroPython installed. Check their [website](https://micropython.org/))
- LED
- DHT22
- 3V Buzzer
- 220 ohm Resistor (for the LED)
- and a Breadboard (if needed)

Here's the setup
<img width="1755" height="1203" alt="espbb" src="https://github.com/user-attachments/assets/8c1abe89-8d13-4cf8-80a2-7a89120c77a3" />
<img width="1312" height="663" alt="esp" src="https://github.com/user-attachments/assets/735418ad-6865-425b-9880-f3df1a30db92" />

You can use battery just by plug the positive and the negative into the correct line in the breadboard. For me, the power source came from the USB to a charging brick (for around 1 - 2 weeks, it's still fine, so yeah).

It's pretty easy with the schematic, you only need to plug the cable pin into the correct hole according to the schematic. _Even a kid can do it_ ~.

### Connecting The ESP32 to the MQTT
After you setup MicroPython to your ESP32, you need to configure the `config.json`. 
There, you need to fill your:
- Designated wifi
- The MQTT broker
- The MQTT user and password for the ESP32 (if you configure it)

After that, use `mpremote cp config.json :` and `mpremote cp main.py :` (or anything that can put a file into the ESP32) to put the configuration and the main script. 

If you don't use TLS/SSL for some reason (e.g. if the ESP32 is connected to the MQTT locally), you can comment on these lines
```python
mqtt = MQTTClient(
    client_id="ESP32_Maggot_01", 
    server=config['mqtt_server'], 
    port=config.get('mqtt_port', 1883),
    user=config.get('mqtt_user', ''),
    password=config.get('mqtt_pass', ''),
    keepalive=60,
    ssl=True,                                             # <--- Comment on it
    ssl_params={"server_hostname": config['mqtt_server']} # <--- Comment on it

)
```
and change the port into `1883` in the `config.json`
```json
{
    "ssid": "wifi-ssid",
    "pass": "wifi-password",
    "mqtt_server": "mqtt-server",
    "mqtt_port": 8883,                <--- Change it into 1883 
    "mqtt_user": "esp32-mqtt-user",
    "mqtt_pass": "esp32-mqtt-pasword"
}
```
You can remove the SSL library from the `main.py`, although imo, it's not really necessary, except if you are frustated with it because the SSL library is not used in the literal code lol

### Connecting The Client to the MQTT
You can check this [repo](https://github.com/Daorza/Maggots-for-Mobile-Computing) for instruction. It's in Bahasa Indonesia, but the setup is pretty simple.

1. Make the virtual environment for the Python
    ```bash
    # Linux
    $ python -m venv venv
    $ source venv/bin/activate

    # Windows
    $ python -m venv venv 
    $ venv/bin/activate
    ```
2. Install the dependencies
    ```bash
    pip install -r requirements.txt
    ```
3. Configure the .env
   ```env
   MQTT_BROKER=namabroker.com
   MQTT_PORT=8883
   MQTT_USERNAME=user_anda
   MQTT_PASSWORD=password_anda
   
   GROQ_API_KEY=gsk_xxxxxxxxxxxx
   GROQ_MODEL=llama-3.3-70b-versatile
   
   SECRET_KEY=kunci_rahasia_untuk_jwt_disini
   ```
4. Run the backend
   ```bash
   uvicorn main:app --port 8000 --reload
   ```
5. Go to the frontend
6. Initalize NPM
   ```bash
   npm install
   ```
7. Run the client
   ```bash
   npm run dev
   ```
8. You can access the website by check the address from the `npm run dev` command in the terminal
