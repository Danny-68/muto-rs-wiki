import serial, time

ser = serial.Serial('/dev/myspeech', 115200)
print("Luistert... (Ctrl+C om te stoppen)")
baseline = "aa550500fb"
try:
    while True:
        count = ser.inWaiting()
        if count:
            raw = ser.read(count)
            hex_data = raw.hex()
            ts = time.strftime("%H:%M:%S")
            if hex_data != baseline:
                print(f"[{ts}] AFWIJKEND: {hex_data}  (bytes: {' '.join(raw.hex()[i:i+2] for i in range(0, len(raw.hex()), 2))})")
            else:
                print(f"[{ts}] baseline")
        time.sleep(0.05)
except KeyboardInterrupt:
    ser.close()
    print("Gestopt")
