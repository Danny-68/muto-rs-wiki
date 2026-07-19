#!/usr/bin/env python3
"""
Optie A - Servo hoek uitlezen via Muto baseboard protocol.
Run ZONDER muto_driver actief (deelt anders de serial poort).
Servo IDs: RF=1,2,3 | RM=4,5,6 | RR=7,8,9
           LR=10,11,12 | LM=13,14,15 | LF=16,17,18
Tibia's = servo 3,6,9,12,15,18 (3e servo per poot)
"""
import serial
import time

DEVICE  = "/dev/myserial"
BAUD    = 115200
TIMEOUT = 0.3

TIBIA_IDS = [3, 6, 9, 12, 15, 18]
LEG_NAMES = {3:"RF", 6:"RM", 9:"RR", 12:"LR", 15:"LM", 18:"LF"}

def checksum(length, wr, addr, data):
    return (0xFF - (length + wr + addr + data)) & 0xFF

def build_read_angle_packet(servo_id):
    length = 0x09
    wr     = 0x02
    addr   = 0x60
    cs     = checksum(length, wr, addr, servo_id)
    return bytes([0x55, 0x00, length, wr, addr, servo_id, cs, 0x00, 0xAA])

def read_servo_angle(ser, servo_id):
    pkt = build_read_angle_packet(servo_id)
    ser.reset_input_buffer()
    ser.write(pkt)
    time.sleep(0.02)
    resp = ser.read(32)  # iets ruim lezen
    return pkt, resp

def parse_response(resp):
    """Zoek het Muto response frame: 0x55 0x00 0x0F 0x12 0x60 ..."""
    for i in range(len(resp) - 4):
        if resp[i] == 0x55 and resp[i+1] == 0x00 and resp[i+3] == 0x12 and resp[i+4] == 0x60:
            frame_len = resp[i+2]
            frame = resp[i : i + frame_len]
            if len(frame) >= frame_len:
                data_bytes = frame[5:-3]  # strip header + length + WR + addr + check + tail
                return data_bytes
    return None

# ── Hoofdprogramma ──────────────────────────────────────────
ser = serial.Serial(DEVICE, baudrate=BAUD, timeout=TIMEOUT)
time.sleep(0.2)
print(f"Verbonden met {DEVICE} @ {BAUD} baud\n")

print("=== RAW DUMP: alle tibia servos ===")
for sid in TIBIA_IDS:
    pkt, resp = read_servo_angle(ser, sid)
    data = parse_response(resp)
    leg  = LEG_NAMES[sid]
    
    print(f"\nServo {sid:2d} ({leg}) tibia:")
    print(f"  Verzonden:  {pkt.hex(' ')}")
    print(f"  Ontvangen:  {resp.hex(' ')}")
    if data:
        print(f"  Data bytes: {data.hex(' ')}")
        print(f"  Als graden: {list(data)}")
    else:
        print("  ⚠️  Geen geldig frame herkend")
    time.sleep(0.05)

print("\n\n=== LIVE MONITORING (Ctrl+C om te stoppen) ===")
print("Til de poten handmatig op en neer terwijl dit loopt.\n")

try:
    while True:
        line_parts = []
        for sid in TIBIA_IDS:
            _, resp = read_servo_angle(ser, sid)
            data = parse_response(resp)
            leg = LEG_NAMES[sid]
            if data and len(data) >= 1:
                angle = data[0]
                line_parts.append(f"{leg}:{angle:3d}°")
            else:
                line_parts.append(f"{leg}:???")
        print("  ".join(line_parts), end="\r")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nKlaar.")

ser.close()
