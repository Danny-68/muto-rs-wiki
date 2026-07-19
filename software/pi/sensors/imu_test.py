#!/usr/bin/env python3
"""
imu_test.py — losstaand testscript om de IMU-yaw uitlezing te verifieren.
Wijzigt niets aan robot_bridge.py. Draai dit terwijl de bridge GESTOPT is
(anders bezetten beide /dev/myserial).

Test 1: leest 20x de yaw in rust -> controleer stabiliteit/ruis.
Test 2: start een langzame rotatie, leest yaw tijdens het draaien,
         stopt automatisch na ~4 seconden -> controleer of uitlezing
         tijdens beweging bruikbaar is.

Gebruik:
    pkill -f robot_bridge.py        # bridge stoppen (bezet anders serial)
    python3 /home/pi/imu_test.py
"""
import serial
import time

SERIAL_PORT = "/dev/myserial"
BAUD = 115200

# IMU yaw-uitlees commando (uit eerdere sessies bevestigd)
IMU_CMD = bytes([0x55, 0x00, 0x09, 0x02, 0x60, 0x07, 0x8D, 0x00, 0xAA])

def make_cmd(addr, data=0x00):
    """Zelfde protocol als robot_bridge.py."""
    wr = 0x01
    length = 0x09
    body = [wr, addr, data]
    chk = (0xFF - ((length + sum(body)) & 0xFF)) & 0xFF
    return bytes([0x55, 0x00, length] + body + [chk, 0x00, 0xAA])

def read_yaw(ser):
    """
    Stuurt het IMU-commando en probeert de yaw uit de respons te halen.
    Respons: yaw als signed big-endian int op bytes i+9:i+11, /100 = graden.
    Retourneert (yaw_graden, ruwe_bytes_hex) of (None, ruwe_bytes_hex).
    """
    ser.reset_input_buffer()
    ser.write(IMU_CMD)
    time.sleep(0.05)
    raw = ser.read(32)  # lees ruim genoeg
    hexstr = raw.hex()

    # Zoek het frame: begint met 55 00, header-byte 0x60 zit rond positie 4
    # yaw op i+9:i+11 volgens eerdere sessie-notities
    for i in range(len(raw) - 10):
        if raw[i] == 0x55 and raw[i+1] == 0x00:
            hi = raw[i+9]
            lo = raw[i+10]
            val = (hi << 8) | lo
            if val >= 0x8000:       # signed 16-bit
                val -= 0x10000
            return val / 100.0, hexstr
    return None, hexstr

def main():
    print(f"Openen {SERIAL_PORT} @ {BAUD}...")
    with serial.Serial(SERIAL_PORT, BAUD, timeout=1) as ser:
        time.sleep(0.5)

        print("\n=== TEST 1: yaw in rust (20 metingen) ===")
        vals = []
        for n in range(20):
            yaw, hexstr = read_yaw(ser)
            if yaw is not None:
                vals.append(yaw)
                print(f"  {n:2d}: yaw = {yaw:7.2f} graden")
            else:
                print(f"  {n:2d}: GEEN yaw gevonden | ruw: {hexstr}")
            time.sleep(0.1)

        if vals:
            print(f"\n  min={min(vals):.2f}  max={max(vals):.2f}  "
                  f"spreiding={max(vals)-min(vals):.2f} graden")
        else:
            print("\n  GEEN enkele geldige meting -> stop, iets klopt niet met de uitlezing.")
            return

        print("\n=== TEST 2: yaw tijdens rotatie (roteer links, 4s) ===")
        input("  Zorg dat de robot vrij kan draaien. Druk Enter om te starten...")

        start_yaw, _ = read_yaw(ser)
        print(f"  Start-yaw: {start_yaw:.2f} graden")

        # Start langzame rotatie naar links (0x16, step 15)
        ser.write(make_cmd(0x16, 15))
        t0 = time.time()
        while time.time() - t0 < 4.0:
            yaw, hexstr = read_yaw(ser)
            if yaw is not None:
                delta = yaw - start_yaw
                print(f"  t={time.time()-t0:4.1f}s  yaw={yaw:7.2f}  delta={delta:+7.2f}")
            else:
                print(f"  t={time.time()-t0:4.1f}s  GEEN yaw | ruw: {hexstr}")
            time.sleep(0.1)

        # Stop
        ser.write(make_cmd(0x11, 0x00))
        end_yaw, _ = read_yaw(ser)
        print(f"\n  Eind-yaw: {end_yaw:.2f} graden")
        if start_yaw is not None and end_yaw is not None:
            print(f"  Totaal gedraaid: {end_yaw - start_yaw:+.2f} graden in 4s")

    print("\nKlaar. Herstart daarna de bridge:")
    print("  python3 /home/pi/robot_bridge.py > /home/pi/bridge_debug.log 2>&1 &")

if __name__ == "__main__":
    main()