#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
floor_tricks.py — Laag 3 vloertrucs voor Yahboom Muto RS
  play_dead : langzame collapse -> splay -> servo torque UIT (robot gaat slap)
  get_up    : torque AAN -> gecontroleerd opdrukken naar stand

Torque commando's (baseboard protocol, geverifieerd uit doc):
  AAN  = addr 0x26 -> 55 00 09 01 26 00 CF 00 AA
  UIT  = addr 0x27 -> 55 00 09 01 27 00 CE 00 AA

Gebruik:
  python3 floor_tricks.py play_dead
  python3 floor_tricks.py get_up
  python3 floor_tricks.py demo        # dead, pauze, dan opstaan
"""

import sys
import time
import math
import serial

sys.path.insert(0, "/home/pi/muto/MutoLib/MutoLib")
from MutoLib.base import point3d

# Hergebruik de bewezen Laag-2 engine (IK + validator)
sys.path.insert(0, "/home/pi")
from body_pose import BodyPose, SERIAL_PORT, BAUD, RATE_HZ, DT

# ---------------------------------------------------------------- splay-pose
# Radiaal naar buiten + omhoog t.o.v. neutraal => lichaam zakt.
# Conservatief gekozen; de IK-validator moet dit goedkeuren.
SPLAY_EXTEND = 35.0     # mm radiaal naar buiten (IK-geverifieerd)
SPLAY_Z      = -62.0    # mm foothoogte -> lichaam zakt ~32mm

# ---------------------------------------------------------------- torque via baseboard
def build_packet(addr, data_bytes):
    """Bouw een baseboard-pakket met correcte length + checksum."""
    length = 8 + len(data_bytes)                     # header2+len1+wr1+addr1+data+chk1+tail2
    chk = (0xFF - (length + 0x01 + addr + sum(data_bytes))) & 0xFF
    return bytes([0x55, 0x00, length, 0x01, addr] + list(data_bytes) + [chk, 0x00, 0xAA])

def torque_on(ser):
    ser.write(build_packet(0x26, [0x00]))            # 55 00 09 01 26 00 CF 00 AA
    ser.flush()

def torque_off(ser):
    ser.write(build_packet(0x27, [0x00]))            # 55 00 09 01 27 00 CE 00 AA
    ser.flush()

# ---------------------------------------------------------------- helpers
def make_splay(bp):
    """Splay-targets afgeleid van de neutrale stand: radiaal naar buiten, omhoog."""
    out = []
    for p in bp.neutral:
        r = math.hypot(p.x, p.y)
        if r < 1e-6:
            ux, uy = 1.0, 0.0
        else:
            ux, uy = p.x / r, p.y / r
        out.append(point3d(p.x + SPLAY_EXTEND * ux,
                           p.y + SPLAY_EXTEND * uy,
                           SPLAY_Z))
    return out

def force_set(bp, targets):
    """Commandeer targets ongeacht de move_tip-cache (cache-break)."""
    for leg, t in zip(bp.legs, targets):
        leg._tip_pos = point3d(t.x + 0.001, t.y, t.z)   # forceer verschil
        leg.move_tip(t)

def lerp_targets(bp, A, B, duration):
    """Vloeiend van target-set A naar B (cosinus-easing)."""
    steps = max(2, int(duration * RATE_HZ))
    for s in range(1, steps + 1):
        f = (1 - math.cos((s / steps) * math.pi)) / 2
        frame = [point3d(a.x + (b.x - a.x) * f,
                         a.y + (b.y - a.y) * f,
                         a.z + (b.z - a.z) * f) for a, b in zip(A, B)]
        for leg, t in zip(bp.legs, frame):
            leg.move_tip(t)
        time.sleep(DT)

# ---------------------------------------------------------------- trucs
def play_dead(bp, ser):
    print("[play_dead] collapse...")
    stand = list(bp.neutral)
    splay = make_splay(bp)

    if not bp._validate(splay):
        print("  ! splay-pose buiten IK-limieten - afgebroken (geen torque-uit).")
        print("    Meld dit; dan tune ik SPLAY_EXTEND / SPLAY_Z.")
        return False

    # 1) langzame collapse van stand naar splay
    lerp_targets(bp, stand, splay, duration=2.5)
    time.sleep(0.3)
    # 2) kleine 'laatste adem' settle
    for _ in range(2):
        lerp_targets(bp, splay, [point3d(p.x, p.y, p.z + 3) for p in splay], 0.35)
        lerp_targets(bp, [point3d(p.x, p.y, p.z + 3) for p in splay], splay, 0.35)
    time.sleep(0.4)
    # 3) torque uit -> robot gaat volledig slap
    print("[play_dead] torque UIT (0x27) - robot is nu slap.")
    torque_off(ser)
    return True

def get_up(bp, ser):
    print("[get_up] torque AAN (0x26)...")
    torque_on(ser)
    time.sleep(0.4)                       # servo's engagen

    splay = make_splay(bp)
    # herstel splay expliciet (cache-break!) zodat fysiek == interne toestand
    print("[get_up] splay herstellen...")
    force_set(bp, splay)
    time.sleep(1.0)
    # gecontroleerd opdrukken naar stand
    print("[get_up] opdrukken naar stand...")
    lerp_targets(bp, splay, list(bp.neutral), duration=2.8)
    time.sleep(0.2)
    print("[get_up] staat.")
    return True

# ---------------------------------------------------------------- main
def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "demo"
    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.5)
    time.sleep(0.3)
    bp = BodyPose(ser)

    try:
        if name == "play_dead":
            # zorg dat we vanaf een bekende stand vertrekken
            force_set(bp, list(bp.neutral)); time.sleep(1.0)
            play_dead(bp, ser)
        elif name == "get_up":
            get_up(bp, ser)
        elif name == "demo":
            force_set(bp, list(bp.neutral)); time.sleep(1.0)
            if play_dead(bp, ser):
                print("\n... 3 seconden slap ...")
                time.sleep(3.0)
                get_up(bp, ser)
        else:
            print(f"Onbekend: '{name}'. Keuze: play_dead, get_up, demo")
            return
    except KeyboardInterrupt:
        print("\nOnderbroken - torque AAN + terug naar stand voor veiligheid.")
        torque_on(ser); time.sleep(0.3)
        force_set(bp, list(bp.neutral))
    finally:
        ser.close()
        print("Klaar.")

if __name__ == "__main__":
    main()
