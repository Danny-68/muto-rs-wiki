#!/usr/bin/env python3
"""
Verificatie: beweeg servo 3 (RF tibia) ±15° en lees hoek terug.
Bevestigt welke databyte de werkelijke hoek is.
"""
import serial, time

DEVICE = "/dev/myserial"
BAUD   = 115200

def cs(length, wr, addr, *data):
    return (0xFF - (length + wr + addr + sum(data))) & 0xFF

def read_angle(ser, servo_id):
    c   = cs(0x09, 0x02, 0x60, servo_id)
    pkt = bytes([0x55, 0x00, 0x09, 0x02, 0x60, servo_id, c, 0x00, 0xAA])
    ser.reset_input_buffer()
    ser.write(pkt)
    time.sleep(0.03)
    resp = ser.read(32)
    for i in range(len(resp) - 10):
        if (resp[i]==0x55 and resp[i+1]==0x00 and
            resp[i+2]==0x0F and resp[i+3]==0x12 and resp[i+4]==0x60):
            return list(resp[i+5 : i+12])   # 7 databytes
    return None

def move_servo(ser, servo_id, angle, speed=100):
    """Control a single steering gear angle — addr 0x40"""
    speed_hi = (speed >> 8) & 0xFF
    speed_lo = speed & 0xFF
    c   = cs(0x0C, 0x01, 0x40, servo_id, angle, speed_hi, speed_lo)
    pkt = bytes([0x55, 0x00, 0x0C, 0x01, 0x40,
                 servo_id, angle, speed_hi, speed_lo, c, 0x00, 0xAA])
    ser.write(pkt)

ser = serial.Serial(DEVICE, baudrate=BAUD, timeout=0.3)
time.sleep(0.2)

# Lees beginpositie
r = read_angle(ser, 3)
if not r:
    print("Geen response — is de driver nog actief?")
    ser.close()
    exit()

baseline = r[1]
print(f"Beginpositie RF tibia: byte[1]={r[1]}°  (alle bytes: {[hex(x) for x in r]})")
print()

# Beweeg naar baseline + 15°
target_up   = min(baseline + 15, 150)
target_down = max(baseline - 15,  30)

for label, target in [("omhoog", target_up), ("terug", baseline), ("omlaag", target_down), ("terug", baseline)]:
    print(f"→ Commando: {target}° ({label})")
    move_servo(ser, 3, target, speed=80)
    time.sleep(0.6)   # servo tijd om te bewegen

    r = read_angle(ser, 3)
    if r:
        print(f"  Gelezen bytes: {[f'{x:3d}' for x in r]}")
        print(f"  byte[0]={r[0]}  byte[1]={r[1]}  byte[3]={r[3]}")
        print(f"  → Verwacht ~{target}°, byte[1]={r[1]}°  verschil={r[1]-target:+d}°")
    else:
        print("  Geen response")
    print()

ser.close()
print("Klaar — welke byte volgt de beweging?")
