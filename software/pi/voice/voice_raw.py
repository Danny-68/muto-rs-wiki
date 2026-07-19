import serial, time

ser = serial.Serial('/dev/myspeech', 115200)
print("Luistert... (Ctrl+C om te stoppen)")
try:
    while True:
        count = ser.inWaiting()
        if count:
            raw = ser.read(count)
            print(f"raw_hex={raw.hex()}")
        time.sleep(0.05)
except KeyboardInterrupt:
    ser.close()
    print("Gestopt")
