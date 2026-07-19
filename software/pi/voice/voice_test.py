import serial, time

ser = serial.Serial('/dev/myspeech', 115200)
print("Wacht op spraak (Ctrl+C om te stoppen)...")
baseline = "aa550500fb"
try:
    while True:
        count = ser.inWaiting()
        if count:
            raw = ser.read(count)
            hex_data = raw.hex()
            if hex_data != baseline:
                byte1 = int(hex_data[4:6], 16) if len(hex_data) >= 6 else None
                byte2 = int(hex_data[6:8], 16) if len(hex_data) >= 8 else None
                print(f">>> AFWIJKEND raw_hex={hex_data}  byte2(wake/taal)={byte1}  byte3(commando_id)={byte2}")
        time.sleep(0.05)
except KeyboardInterrupt:
    ser.close()
    print("Gestopt")
