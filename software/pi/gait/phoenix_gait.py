#!/usr/bin/env python3
"""
phoenix_gait.py — Phoenix-style gait engine voor Yahboom Muto RS
"""

import sys
import math
import time
import argparse
import serial
from dataclasses import dataclass
from typing import List, Tuple

COXA_A    = 27.5
COXA_B    = 50.59
COXA_LEN  = COXA_A + COXA_B
FEMUR_LEN = 72.60
TIBIA_LEN = 134.5

MOUNT_DEG = [-45.0, 0.0, 45.0, 135.0, 180.0, 225.0]
MOUNT_RAD = [math.radians(d) for d in MOUNT_DEG]

def _compute_neutral():
    f_rad = math.radians(30.0)
    t_rad = math.radians(60.0)
    r_femur = FEMUR_LEN * math.cos(f_rad)
    h_femur = FEMUR_LEN * math.sin(f_rad)
    abs_tibia = f_rad - (math.pi - t_rad)
    r_tibia = TIBIA_LEN * math.cos(abs_tibia)
    h_tibia = TIBIA_LEN * math.sin(abs_tibia)
    reach  = COXA_LEN + r_femur + r_tibia
    z_down = -(h_femur - h_tibia)
    return [(reach * math.cos(a), reach * math.sin(a), z_down) for a in MOUNT_RAD]

from MutoLib import (p1_x, p1_y, p1_z, p2_x, p2_y, p2_z,
                     p3_x, p3_y, p3_z, p4_x, p4_y, p4_z,
                     p5_x, p5_y, p5_z, p6_x, p6_y, p6_z)
NEUTRAL_POS = [(p1_x,p1_y,p1_z),(p2_x,p2_y,p2_z),(p3_x,p3_y,p3_z),
               (p4_x,p4_y,p4_z),(p5_x,p5_y,p5_z),(p6_x,p6_y,p6_z)]
print("[INFO] Neutrale posities geladen uit MutoLib")

@dataclass
class GaitParams:
    name: str
    steps_in_gait: int
    nr_lifted_pos: int
    lift_height: float
    step_length: float
    nom_gait_speed_ms: float
    gait_leg_nr: List[int]

TRIPOD_4 = GaitParams("tripod_4", 4, 1, 40.0, 60.0, 100, [0,2,0,2,0,2])
TRIPOD_6 = GaitParams("tripod_6", 6, 2, 40.0, 60.0,  80, [0,3,0,3,0,3])
TRIPOD_8 = GaitParams("tripod_8", 8, 3, 40.0, 60.0,  80, [0,4,0,4,0,4])
RIPPLE_6 = GaitParams("ripple_6", 6, 2, 40.0, 50.0,  80, [0,4,2,0,4,2])
WAVE_12  = GaitParams("wave_12", 12, 2, 40.0, 40.0,  80, [0,2,4,6,8,10])

GAITS = {'tripod_4': TRIPOD_4, 'tripod_6': TRIPOD_6, 'tripod_8': TRIPOD_8,
         'ripple_6': RIPPLE_6, 'wave_12': WAVE_12}

class PhoenixGait:
    def step(self, gait_step, gait, travel_x=1.0, travel_z=0.0,
             rotate=0.0, body_sway=False):
        positions = []
        for leg in range(6):
            phase = (gait_step - gait.gait_leg_nr[leg]) % gait.steps_in_gait
            if phase < gait.nr_lifted_pos:
                t = phase / gait.nr_lifted_pos
                pos = self._swing(leg, t, gait, travel_x, travel_z, rotate)
            else:
                stance_len = gait.steps_in_gait - gait.nr_lifted_pos
                t = (phase - gait.nr_lifted_pos) / max(stance_len - 1, 1)
                pos = self._stance(leg, t, gait, travel_x, travel_z, rotate)
            positions.append(pos)
        if body_sway:
            positions = self._body_sway(gait_step, gait, positions)
        return positions

    def _foot_delta(self, leg, gait, tx, tz, rot):
        angle = MOUNT_RAD[leg]
        nx, ny, _ = NEUTRAL_POS[leg]
        dx = gait.step_length * tx * math.cos(angle)
        dy = gait.step_length * tx * math.sin(angle)
        dx += gait.step_length * tz *  math.sin(angle)
        dy += gait.step_length * tz * -math.cos(angle)
        rot_scale = gait.step_length * 0.6
        rx = -ny * rot * rot_scale / max(math.hypot(nx, ny), 1)
        ry =  nx * rot * rot_scale / max(math.hypot(nx, ny), 1)
        return (dx + rx, dy + ry)

    def _swing(self, leg, t, gait, tx, tz, rot):
        nx, ny, nz = NEUTRAL_POS[leg]
        ddx, ddy = self._foot_delta(leg, gait, tx, tz, rot)
        return (nx + (t-0.5)*ddx, ny + (t-0.5)*ddy,
                nz + math.sin(math.pi * t) * gait.lift_height)

    def _stance(self, leg, t, gait, tx, tz, rot):
        nx, ny, nz = NEUTRAL_POS[leg]
        ddx, ddy = self._foot_delta(leg, gait, tx, tz, rot)
        return (nx + (0.5-t)*ddx, ny + (0.5-t)*ddy, nz)

    def _body_sway(self, gait_step, gait, positions):
        stance_pts = [positions[leg] for leg in range(6)
                      if (gait_step - gait.gait_leg_nr[leg]) % gait.steps_in_gait
                      >= gait.nr_lifted_pos]
        if not stance_pts:
            return positions
        cx = sum(p[0] for p in stance_pts) / len(stance_pts)
        cy = sum(p[1] for p in stance_pts) / len(stance_pts)
        SWAY = 0.12
        return [(x - cx*SWAY, y - cy*SWAY, z) for x, y, z in positions]


class HardwareInterface:
    """Stuurt echte servo's via MutoLib Leg.move_tip()"""

    def __init__(self, port='/dev/myserial'):
        from MutoLib import Servo, Leg, point3d
        self._point3d = point3d
        ser = serial.Serial(port, 115200, timeout=0.1)
        srv = Servo(ser)
        self._legs = [Leg(i, srv) for i in range(6)]
        self._point3d = point3d
        # Eerst naar neutrale stand voordat gait begint
        print(f"[HW] Naar neutrale stand...")
        for i, leg in enumerate(self._legs):
            from MutoLib import p1_x, p1_y, p1_z, p2_x, p2_y, p2_z,                                 p3_x, p3_y, p3_z, p4_x, p4_y, p4_z,                                 p5_x, p5_y, p5_z, p6_x, p6_y, p6_z
            neutral = [(p1_x,p1_y,p1_z),(p2_x,p2_y,p2_z),(p3_x,p3_y,p3_z),
                       (p4_x,p4_y,p4_z),(p5_x,p5_y,p5_z),(p6_x,p6_y,p6_z)]
            leg.move_tip(point3d(*neutral[i]))
        import time as _time
        _time.sleep(1.0)
        print(f"[HW] MutoLib geladen, 6 poten op {port}")

    def send(self, positions):
        for i, (x, y, z) in enumerate(positions):
            self._legs[i].move_tip(self._point3d(x, y, z))

    def destroy(self):
        pass


def test_neutral(iface):
    print("[TEST] neutral — Ctrl-C om te stoppen")
    while True:
        iface.send(list(NEUTRAL_POS))
        time.sleep(0.05)

def test_one_leg(iface, gait, cycles=4):
    print(f"[TEST] one_leg — {cycles} cycli")
    dt = gait.nom_gait_speed_ms / 1000.0
    for _ in range(cycles):
        for step in range(16):
            t = step / 16
            positions = list(NEUTRAL_POS)
            nx, ny, nz = NEUTRAL_POS[0]
            positions[0] = (nx, ny, nz + math.sin(math.pi * t) * gait.lift_height)
            iface.send(positions)
            time.sleep(dt)
        time.sleep(0.3)

def test_gait(iface, gait, engine, sway=False):
    print(f"[TEST] {gait.name} — lift={gait.lift_height:.0f}mm "
          f"speed={gait.nom_gait_speed_ms:.0f}ms/stap — Ctrl-C om te stoppen")
    dt = gait.nom_gait_speed_ms / 1000.0
    gait_step = 0
    while True:
        positions = engine.step(gait_step, gait,
                                travel_x=1.0, body_sway=sway)
        iface.send(positions)
        time.sleep(dt)
        gait_step = (gait_step + 1) % gait.steps_in_gait


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--test', choices=['neutral','one_leg','tripod','ripple','wave'],
                   default='tripod')
    p.add_argument('--gait', choices=list(GAITS.keys()), default='tripod_8')
    p.add_argument('--speed', type=float, default=None)
    p.add_argument('--lift',  type=float, default=None)
    p.add_argument('--sway',  action='store_true')
    p.add_argument('--cycles', type=int, default=4)
    p.add_argument('--port', default='/dev/myserial')
    args = p.parse_args()

    iface = HardwareInterface(port=args.port)
    gait  = GAITS[args.gait]
    if args.speed: gait.nom_gait_speed_ms = args.speed
    if args.lift:  gait.lift_height = args.lift
    engine = PhoenixGait()

    print("=" * 50)
    print(f"  Phoenix Gait | {gait.name} | lift={gait.lift_height:.0f}mm | "
          f"speed={gait.nom_gait_speed_ms:.0f}ms | sway={'aan' if args.sway else 'uit'}")
    print("=" * 50)

    try:
        if   args.test == 'neutral':  test_neutral(iface)
        elif args.test == 'one_leg':  test_one_leg(iface, gait, args.cycles)
        else:                         test_gait(iface, gait, engine, args.sway)
    except KeyboardInterrupt:
        print("\n[INFO] Gestopt.")
    finally:
        iface.destroy()

if __name__ == '__main__':
    main()
