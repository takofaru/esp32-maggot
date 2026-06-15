from machine import Pin, WDT
import time
import dht
import network
import ujson
import gc
import ssl
from umqtt.simple import MQTTClient

# --- Konfigurasi Perangkat Keras ---
LEDPIN = 32
BUZZPIN = 33
DHTPIN = 25
CONFIG = 'config.json'

DHT = dht.DHT22(Pin(DHTPIN))
LED = Pin(LEDPIN, Pin.OUT)
BUZZ = Pin(BUZZPIN, Pin.OUT)

# --- Pra-Alokasi Byte MQTT (Hemat Memori) ---
TOPIC_STATUS = b"maggot/status/fase"
TOPIC_STATUS_BATAS = b"maggot/status/batas"
TOPIC_KONTROL = b"maggot/kontrol/fase"
TOPIC_BATAS = b"maggot/kontrol/batas"
TOPIC_SENSOR = b"maggot/sensor/data"

# --- 1. Definisi Fase dan Batasan ---
class MaggotPhase:
    def __init__(self, phaseName, tempMin, tempMax, humidMin, humidMax, durasiHari):
        self.phaseName = phaseName
        self.tempMin = float(tempMin)
        self.tempMax = float(tempMax)
        self.humidMin = float(humidMin)
        self.humidMax = float(humidMax)
        self.durasiHari = float(durasiHari)

    def to_dict(self):
        return {
            "phaseName": self.phaseName,
            "tempMin": self.tempMin,
            "tempMax": self.tempMax,
            "humidMin": self.humidMin,
            "humidMax": self.humidMax,
            "durasiHari": self.durasiHari
        }

LIMITS_FILE = 'limits.json'

default_limits = [
    MaggotPhase("Fase Telur", 28, 35, 60, 80, 7),
    MaggotPhase("Fase Larva", 27, 30, 60, 80, 21),
    MaggotPhase("Fase Pupa", 27, 30, 0, 40, 21),
    MaggotPhase("Fase Lalat", 27.5, 37.5, 60, 70, 6)
]

siklus_maggot = []

def simpan_limits_config():
    try:
        data = [fase.to_dict() for fase in siklus_maggot]
        with open(LIMITS_FILE, 'w') as file:
            ujson.dump(data, file)
        print("[SISTEM] Batasan fase disimpan ke", LIMITS_FILE)
    except OSError as e:
        print("[ERROR] Gagal menyimpan batasan fase:", e)

def muat_limits_config():
    global siklus_maggot
    try:
        with open(LIMITS_FILE, 'r') as file:
            data = ujson.load(file)
        siklus_maggot = []
        for d in data:
            siklus_maggot.append(MaggotPhase(
                d["phaseName"], d["tempMin"], d["tempMax"],
                d["humidMin"], d["humidMax"], d["durasiHari"]
            ))
        print("[SISTEM] Batasan fase dimuat dari", LIMITS_FILE)
    except (OSError, ValueError, KeyError):
        print("[SISTEM] File batasan tidak ditemukan atau rusak. Menggunakan nilai default.")
        siklus_maggot = default_limits[:]
        simpan_limits_config()

# Muat konfigurasi batasan saat startup
muat_limits_config()

# --- Variabel Pelacak Waktu, Fase, dan Status Jaringan ---
indeks_fase = 0 
waktu_mulai_fase = time.time() # time.time() tetap dipakai untuk hitungan hari (jangka panjang)
DETIK_PER_HARI = 86400 

mqtt_online = False

# Gunakan ticks_ms untuk perhitungan interval pendek yang lebih efisien
waktu_reconnect_terakhir = time.ticks_ms()
waktu_baca_terakhir = time.ticks_ms()
INTERVAL_RECONNECT_MS = 10000 
INTERVAL_SENSOR_MS = 2000


# --- Fungsi untuk Mengirim Status Fase (Retained) ---
def kirim_status_fase():
    if not mqtt_online:
        return 
        
    fase_aktif = siklus_maggot[indeks_fase]
    hari_berjalan = (time.time() - waktu_mulai_fase) / DETIK_PER_HARI
    payload_status = ujson.dumps({
        "fase": fase_aktif.phaseName,
        "hari_ke": round(hari_berjalan, 1),
        "tempMin": fase_aktif.tempMin,
        "tempMax": fase_aktif.tempMax,
        "humidMin": fase_aktif.humidMin,
        "humidMax": fase_aktif.humidMax
    })
    
    try:
        mqtt.publish(TOPIC_STATUS, payload_status, retain=True)
        print(f"\n[MQTT] Status fase terkirim: {payload_status}")
    except OSError:
        pass 

# --- 2. Fungsi Penerima Perintah MQTT ---
def terima_pesan(topic, msg):
    global indeks_fase, waktu_mulai_fase
    
    topik_str = topic.decode('utf-8')
    pesan_str = msg.decode('utf-8')
    
    if topik_str == TOPIC_KONTROL.decode('utf-8'):
        cmd = pesan_str.strip()
        target_idx = -1
        
        if cmd.upper() == "NEXT":
            target_idx = (indeks_fase + 1) % len(siklus_maggot)
            print("\n[MANUAL OVERRIDE] Pengurus memerintahkan pindah ke fase berikutnya!")
        elif cmd.isdigit():
            idx = int(cmd)
            if 0 <= idx < len(siklus_maggot):
                target_idx = idx
                print("\n[MANUAL OVERRIDE] Pengurus memilih fase indeks:", idx)
        else:
            # Cari berdasarkan nama
            for i, f in enumerate(siklus_maggot):
                if f.phaseName.lower() == cmd.lower():
                    target_idx = i
                    print("\n[MANUAL OVERRIDE] Pengurus memilih fase nama:", f.phaseName)
                    break
        
        if target_idx != -1:
            indeks_fase = target_idx
            waktu_mulai_fase = time.time()
            kirim_status_fase()
            for _ in range(3):
                BUZZ.value(1); time.sleep_ms(100)
                BUZZ.value(0); time.sleep_ms(100)
        else:
            print("\n[MANUAL OVERRIDE ERROR] Perintah fase tidak valid:", cmd)
            
    elif topik_str == TOPIC_BATAS.decode('utf-8'):
        try:
            data = ujson.loads(pesan_str)
            target_index = -1
            
            # Cari berdasarkan indeks jika diberikan
            if "indeks" in data:
                idx = int(data["indeks"])
                if 0 <= idx < len(siklus_maggot):
                    target_index = idx
            # Cari berdasarkan nama fase
            elif "fase" in data:
                nama_target = str(data["fase"]).lower()
                for i, fase_item in enumerate(siklus_maggot):
                    if fase_item.phaseName.lower() == nama_target:
                        target_index = i
                        break
            
            if target_index != -1:
                fase = siklus_maggot[target_index]
                if "tempMin" in data: fase.tempMin = float(data["tempMin"])
                if "tempMax" in data: fase.tempMax = float(data["tempMax"])
                if "humidMin" in data: fase.humidMin = float(data["humidMin"])
                if "humidMax" in data: fase.humidMax = float(data["humidMax"])
                if "durasiHari" in data: fase.durasiHari = float(data["durasiHari"])
                
                print("\n[MQTT CONFIG] Berhasil memperbarui batas fase:", fase.phaseName)
                simpan_limits_config()
                
                # Kirim status batas ter-update ke MQTT sebagai konfirmasi dari ESP32
                payload_konfirmasi = ujson.dumps({
                    "status": "SUCCESS",
                    "fase": fase.phaseName,
                    "tempMin": fase.tempMin,
                    "tempMax": fase.tempMax,
                    "humidMin": fase.humidMin,
                    "humidMax": fase.humidMax
                })
                try:
                    mqtt.publish(TOPIC_STATUS_BATAS, payload_konfirmasi)
                    print(f"[MQTT] Konfirmasi perubahan batas terkirim: {payload_konfirmasi}")
                except OSError:
                    pass
                
                # Kirim konfirmasi suara & visual (2 beep panjang 200ms)
                for _ in range(2):
                    BUZZ.value(1); LED.value(1); time.sleep_ms(200)
                    BUZZ.value(0); LED.value(0); time.sleep_ms(100)
                
                # Jika fase yang diperbarui adalah fase aktif, kirim status ter-update ke dashboard
                if target_index == indeks_fase:
                    kirim_status_fase()
            else:
                print("\n[MQTT CONFIG ERROR] Fase tidak ditemukan dalam data:", pesan_str)
        except (ValueError, KeyError, OSError) as e:
            print("\n[MQTT CONFIG ERROR] Gagal memproses payload konfigurasi:", e)

# --- 3. Membaca Config & Koneksi Wi-Fi ---
try:
    with open(CONFIG, 'r') as file:
        config = ujson.load(file)
except OSError:
    print("Error: config.json tidak ditemukan!")

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.disconnect() 
time.sleep(1)

wlan.connect(config['ssid'], config['pass'])
print('Menghubungkan ke Wi-Fi...')
while not wlan.isconnected():
    time.sleep(1)
    print('.', end='')
print('\n[WIFI] Connected! IP: ' + wlan.ifconfig()[0])

# --- 4. Inisialisasi MQTT ---
mqtt = MQTTClient(
    client_id="ESP32_Maggot_01", 
    server=config['mqtt_server'], 
    port=config.get('mqtt_port', 1883),
    user=config.get('mqtt_user', ''),
    password=config.get('mqtt_pass', ''),
    keepalive=60,
    ssl=True,
    ssl_params={"server_hostname": config['mqtt_server']}

)
mqtt.set_callback(terima_pesan)

# --- Patched Socket Module untuk umqtt.simple ---
class PatchedSocketModule:
    def __init__(self, orig_module, timeout=5.0):
        self.orig_module = orig_module
        self.timeout = timeout

    def __getattr__(self, name):
        return getattr(self.orig_module, name)

    def socket(self, *args, **kwargs):
        s = self.orig_module.socket(*args, **kwargs)
        s.settimeout(self.timeout)
        return s

import umqtt.simple
import usocket
# Patch namespace umqtt.simple agar menggunakan socket dengan timeout 5.0 detik
umqtt.simple.socket = PatchedSocketModule(usocket, 5.0)

try:
    mqtt.connect()
    mqtt.subscribe(TOPIC_KONTROL)
    mqtt.subscribe(TOPIC_BATAS)
    mqtt_online = True
    print("[MQTT] Terhubung! Menunggu instruksi...")
    kirim_status_fase()
except OSError:
    mqtt_online = False
    print("[SISTEM] Gagal koneksi awal MQTT. Berjalan dalam mode OFFLINE.")

# Aktifkan Hardware Watchdog (Otomatis Reset jika hang lebih dari 15 detik)
wdt = WDT(timeout=15000)

# --- 5. Loop Utama (Terisolasi & Fault Tolerant) ---
print("[SISTEM] Memulai pemantauan utama...")

while True:
    try:
        # 1. Beri makan Watchdog di awal loop agar sistem tidak reset
        wdt.feed()
        
        waktu_sekarang_ms = time.ticks_ms()
        waktu_sekarang_detik = time.time()
        
        hari_berjalan = (waktu_sekarang_detik - waktu_mulai_fase) / DETIK_PER_HARI
        fase_aktif = siklus_maggot[indeks_fase]

        # A. Cek Auto-Next Fase
        if hari_berjalan >= fase_aktif.durasiHari:
            indeks_fase = (indeks_fase + 1) % len(siklus_maggot)
            waktu_mulai_fase = waktu_sekarang_detik
            fase_aktif = siklus_maggot[indeks_fase]
            print(f"\n[AUTO SYSTEM] Berpindah ke: {fase_aktif.phaseName}")
            kirim_status_fase()

        # B. Pembacaan Sensor & Alarm Utama (Interval Menggunakan ticks_diff)
        if time.ticks_diff(waktu_sekarang_ms, waktu_baca_terakhir) >= INTERVAL_SENSOR_MS:
            try:
                DHT.measure()
                dhtTemp = DHT.temperature()
                dhtHumid = DHT.humidity()
                
                status_jaringan = "ON" if mqtt_online else "OFF"
                print(f"[{status_jaringan}] ({wlan.ifconfig()[0]}) T:{dhtTemp}C | H:{dhtHumid}%")
                
                # Logika Alarm
                kond_suhu = dhtTemp > fase_aktif.tempMax or dhtTemp < fase_aktif.tempMin
                kond_humid = dhtHumid > fase_aktif.humidMax or dhtHumid < fase_aktif.humidMin
                
                if kond_suhu and kond_humid:
                    for _ in range(5):
                        LED.value(1); BUZZ.value(1); time.sleep_ms(50)
                        LED.value(0); BUZZ.value(0); time.sleep_ms(50)
                elif kond_suhu:
                    for _ in range(2):
                        LED.value(1); BUZZ.value(1); time.sleep_ms(150)
                        LED.value(0); BUZZ.value(0); time.sleep_ms(150)
                elif kond_humid:
                    LED.value(1); BUZZ.value(1); time.sleep_ms(600)
                    LED.value(0); BUZZ.value(0)
                else:
                    LED.value(0); BUZZ.value(0)
                    
                # C. Pengiriman Data MQTT
                if mqtt_online:
                    try:
                        payload_sensor = ujson.dumps({"suhu": dhtTemp, "kelembapan": dhtHumid})
                        mqtt.publish(TOPIC_SENSOR, payload_sensor)
                    except OSError:
                        mqtt_online = False
                        print("[ERROR] Koneksi MQTT terputus saat publish data!")
                
                # Perbarui waktu baca menggunakan ticks_ms yang baru
                waktu_baca_terakhir = time.ticks_ms() 
                
            except OSError:
                print("[ERROR] Gagal membaca sensor DHT")

        # D. Penerimaan Pesan & Sistem Auto-Reconnect
        if mqtt_online:
            try:
                mqtt.check_msg()
            except OSError:
                mqtt_online = False
                print("[ERROR] Koneksi MQTT terputus saat mengecek pesan!")
        else:
            if time.ticks_diff(waktu_sekarang_ms, waktu_reconnect_terakhir) >= INTERVAL_RECONNECT_MS:
                print("[MQTT] Mencoba menyambung ulang...")
                try:
                    try: mqtt.disconnect() 
                    except: pass 
                    
                    mqtt.connect()
                    mqtt.subscribe(TOPIC_KONTROL)
                    mqtt.subscribe(TOPIC_BATAS)
                    mqtt_online = True
                    print("[MQTT] Berhasil tersambung kembali!")
                    kirim_status_fase() 
                except OSError:
                    print("[MQTT] Gagal menyambung ulang.")
                    
                waktu_reconnect_terakhir = time.ticks_ms()
                
        # 2. Bersihkan memori RAM dari sampah variabel (Sangat Krusial!)
        gc.collect()
        
        # 3. Jeda super singkat (100ms) untuk mengurangi beban CPU tanpa memblokir sistem
        time.sleep_ms(100)

    except Exception as e:
        # Tangkapan layar darurat: Jika ada error fatal (misal memori penuh), program tidak akan mati.
        print(f"[CRITICAL ERROR] Sistem pulih dari gangguan: {e}")
        time.sleep(1) # Beri nafas sejenak sebelum mengulang loop
