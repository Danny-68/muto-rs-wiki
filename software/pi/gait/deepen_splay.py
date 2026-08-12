#!/usr/bin/env python3
import sys, time, math
sys.path.insert(0, "/home/pi/muto/MutoLib/MutoLib")
from MutoLib.base import point3d
sys.path.insert(0, "/home/pi")
from body_pose import BodyPose, SERIAL_PORT, BAUD, RATE_HZ, DT
import serial
from floor_tricks import torque_on, torque_off, force_set, lerp_targets, make_splay, SPLAY_EXTEND, SPLAY_Z

DEEP_EXTEND = 80.0
DEEP_Z = 0.0

def make_deep_splay(bp):
    out = []
    for p in bp.neutral:
        r = math.hypot(p.x, p.y)
        ux, uy = (p.x / r, p.y / r) if r > 1e-6 else (1.0, 0.0)
        out.append(point3d(p.x + DEEP_EXTEND * ux, p.y + DEEP_EXTEND * uy, DEEP_Z))
    return out

ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.5)
time.sleep(0.3)
bp = BodyPose(ser)

print("[deepen] torque AAN...")
torque_on(ser)
time.sleep(0.4)

old_splay = make_splay(bp)
deep_splay = make_deep_splay(bp)

if not bp._validate(deep_splay):
    print("FOUT: diepe splay niet geldig op dit moment, afgebroken")
    sys.exit(1)

print("[deepen] huidige (ondiepe) splay herstellen (cache-break)...")
force_set(bp, old_splay)
time.sleep(0.8)

print("[deepen] langzaam naar diepere, vlakkere stand...")
lerp_targets(bp, old_splay, deep_splay, duration=3.0)
time.sleep(0.5)

print("[deepen] torque UIT - robot is nu slap in de diepe stand.")
torque_off(ser)
ser.close()
print("Klaar.")
