#!/usr/bin/env python3
"""
imu_diag.py — leest de ruwe IMU-yaw en toont zowel de ruwe bytes als
meerdere interpretaties, zodat we de juiste schaal/eenheid kunnen bepalen.
Draait de robot NIET. Bridge eerst stoppen.

Gebruik:
    pkill -f robot_bridge.py
    python3 /home/pi/imu_diag.py
Draai de robot HANDMATIG een kwartslag (90 graden) tussen de metingen door
en kijk hoeveel de getallen veranderen.
"""
import serial, time

SERIAL_PORT = "/dev/myserial"
BAUD = 115200
IMU_CMD = bytes([0x55, 0x00, 0x09, 0x02, 0x60, 0x07, 0x8D, 0x00, 0xAA])

def read_raw(ser):
    ser.reset_input_buffer()
    ser.write(IMU_CMD)
    time.sleep(0.05)
    raw = ser.read(32)
    for i in range(len(raw) - 10):
        if raw[i] == 0x55 and raw[i + 1] == 0x00:
            hi = raw[i + 9]
            lo = raw[i + 10]
            val = (hi << 8) | lo
            signed = val - 0x10000 if val >= 0x8000 else val
            return {
                "frame_hex": raw[i:i+12].hex(),
                "hi_lo": (hi, lo),
                "raw_uint16": val,
                "signed_div100": signed / 100.0,
                "signed_div10": signed / 10.0,
                "signed_div16": signed / 16.0,     # sommige IMU's: 1/16 graden
                "signed_raw": signed,
            }
    return {"frame_hex": raw.hex(), "error": "geen frame"}

def main():
    with serial.Serial(SERIAL_PORT, BAUD, timeout=1) as ser:
        time.sleep(0.3)
        print("Druk Enter voor een meting (Ctrl+C om te stoppen).")
        print("Tip: meet, draai de robot handmatig 90 graden, meet opnieuw.\n")
        n = 0
        while True:
            input(f"[meting {n}] Enter...")
            d = read_raw(ser)
            print(f"  frame:        {d.get('frame_hex')}")
            if "error" not in d:
                print(f"  hi,lo:        {d['hi_lo']}")
                print(f"  raw_uint16:   {d['raw_uint16']}")
                print(f"  signed:       {d['signed_raw']}")
                print(f"  /100 (huidig):{d['signed_div100']:.2f} graden")
                print(f"  /10:          {d['signed_div10']:.2f}")
                print(f"  /16:          {d['signed_div16']:.2f}")
            print()
            n += 1

if __name__ == "__main__":
    main()