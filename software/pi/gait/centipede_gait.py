#!/usr/bin/env python3
"""
centipede_gait.py — Centipede Wave Gait voor Yahboom Muto RS
=============================================================

Afgeleid van de Yahboom standaard tripod gait (muto_rs_gait.docx).
Vier biologische verbeteringen ten opzichte van de basegait:

  1. BODY DIP      — lichaam zakt licht als een been in de lucht is
  2. SNELHEID-LIFT — lifthoogte schaalt mee met loopsnelheid
  3. ACCELERATIE   — geleidelijk optrekken en afremmen (geen schokstart)
  4. BODY SWAY     — licht zwaaien naar de stance-zijde voor stabiliteit

Centipede volgorde: RR → LR → RM → LM → RF → LF (golf achter→voor)
duty factor β = 5/6 ≈ 0.833  →  altijd precies 1 been in de lucht

GEBRUIK:
    python3 /root/centipede_gait.py --test neutral
    python3 /root/centipede_gait.py --test centipede
    python3 /root/centipede_gait.py --test centipede --period 2.0 --lift 30 --step 35
    python3 /root/centipede_gait.py --test tripod
    python3 /root/centipede_gait.py --test centipede --no-imu --duration 30
"""

import sys
import math
import time
import argparse
import serial
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ── MutoLib ────────────────────────────────────────────────────────
sys.path.insert(0, '/root/yahboomcar_ros2_ws/software/MutoLib/')
try:
    from MutoLib import Servo, Leg, point3d
    from MutoLib.config import (
        p1_x, p1_y, p1_z,
        p2_x, p2_y, p2_z,
        p3_x, p3_y, p3_z,
        p4_x, p4_y, p4_z,
        p5_x, p5_y, p5_z,
        p6_x, p6_y, p6_z,
    )
except ImportError as e:
    print(f"[FOUT] MutoLib niet gevonden: {e}")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════════
# ROBOT GEOMETRIE
#   Coördinaten: +x = rechts, +y = voor, +z = omhoog
#   Index:  0=RF  1=RM  2=RR  3=LR  4=LF*  5=LM*
#   (* index 4 en 5 zijn fysiek omgekeerd t.o.v. verwachting)
# ════════════════════════════════════════════════════════════════════
NEUTRAL: List[Tuple[float, float, float]] = [
    (p1_x, p1_y, p1_z),   # 0  RF  rechts-voor
    (p2_x, p2_y, p2_z),   # 1  RM  rechts-midden
    (p3_x, p3_y, p3_z),   # 2  RR  rechts-achter
    (p4_x, p4_y, p4_z),   # 3  LR  links-achter
    (p5_x, p5_y, p5_z),   # 4  LF  links-voor   (fysiek index 4)
    (p6_x, p6_y, p6_z),   # 5  LM  links-midden (fysiek index 5)
]

# Welke kant: +1 = rechts (legs 0,1,2), -1 = links (legs 3,4,5)
LEG_SIDE = [+1, +1, +1, -1, -1, -1]


# ════════════════════════════════════════════════════════════════════
# GAIT PARAMETERS
# ════════════════════════════════════════════════════════════════════
@dataclass
class GaitParams:
    """
    Beschrijft een volledig gaitpatroon inclusief biologische bewegingsparameters.

    Basis:
        leg_offsets  faseverschuiving [0, 1) per been
        swing_frac   fractie cyclus dat been in lucht is
        lift_height  maximale lifthoogte (mm)
        step_length  nominale staplengte in y-richting (mm)
        period       seconden per volledige cyclus

    Biologische verbeteringen:
        body_dip     hoeveel het lichaam zakt tijdens swing (mm)
        body_sway    hoeveel het lichaam zijwaarts zwaait (mm)
        accel_rate   hoe snel step_y verandert bij start/stop (mm/s²)
        lift_min_frac minimale lift als fractie van lift_height (bij stilstand)
    """
    name: str
    leg_offsets: List[float]
    swing_frac: float
    lift_height: float
    step_length: float
    period: float
    # Biologische verbeteringen (met defaults)
    body_dip: float = 4.0        # mm — body zakt bij swing
    body_sway: float = 6.0       # mm — laterale sway naar stance zijde
    accel_rate: float = 20.0     # mm/s² — acceleratie bij start/stop
    lift_min_frac: float = 0.3   # minimale lift = 30% van lift_height


# ── Yahboom tripod (referentie uit document §5.4) ─────────────────
TRIPOD_YAHBOOM = GaitParams(
    name="tripod_yahboom",
    leg_offsets=[0.5, 0.0, 0.5, 0.0, 0.5, 0.0],
    #            RF   RM   RR   LR   LF   LM
    swing_frac=0.45,
    lift_height=25.0,
    step_length=35.0,
    period=1.2,
    body_dip=3.0,
    body_sway=5.0,
    accel_rate=30.0,
)

# ── Centipede wave gait ───────────────────────────────────────────
# Volgorde:
#   fase 0/6: RR(2)  achter-rechts  → 1e
#   fase 1/6: LR(3)  achter-links   → 2e
#   fase 2/6: RM(1)  midden-rechts  → 3e
#   fase 3/6: LM(5)  midden-links   → 4e   (fysiek index 5)
#   fase 4/6: RF(0)  voor-rechts    → 5e
#   fase 5/6: LF(4)  voor-links     → 6e   (fysiek index 4)
CENTIPEDE = GaitParams(
    name="centipede",
    leg_offsets=[4/6, 2/6, 0/6, 1/6, 5/6, 3/6],
    #            RF   RM   RR   LR   LF   LM
    swing_frac=1/6,
    lift_height=25.0,
    step_length=30.0,
    period=2.5,
    body_dip=4.0,
    body_sway=6.0,
    accel_rate=20.0,
    lift_min_frac=0.3,
)

GAITS = {
    'tripod_yahboom': TRIPOD_YAHBOOM,
    'centipede':      CENTIPEDE,
}


# ════════════════════════════════════════════════════════════════════
# SERIEEL / IMU
# ════════════════════════════════════════════════════════════════════
_IMU_CMD = bytes([0x55, 0x00, 0x09, 0x02, 0x60, 0x07, 0x8D, 0x00, 0xAA])
_IMU_HDR = bytes([0x55, 0x00, 0x0F, 0x12, 0x60])


def _open_serial(port: str, baud: int = 115200) -> serial.Serial:
    return serial.Serial(port, baud, timeout=0.1)


def _read_yaw(ser: serial.Serial) -> Optional[float]:
    """Lees IMU yaw [-180, +180] graden. Geeft None bij timeout."""
    ser.reset_input_buffer()
    ser.write(_IMU_CMD)
    time.sleep(0.025)
    data = ser.read(64)
    for i in range(len(data) - 11):
        if data[i:i+5] == _IMU_HDR:
            raw = (data[i+9] << 8) | data[i+10]
            yaw = raw / 100.0
            if yaw > 180.0:
                yaw -= 360.0
            return yaw
    return None


# ════════════════════════════════════════════════════════════════════
# GAIT ENGINE
# ════════════════════════════════════════════════════════════════════

def _ease(t: float) -> float:
    """Sinusoïdale easing: ease(t) = 0.5 - 0.5·cos(π·t)."""
    return 0.5 - 0.5 * math.cos(math.pi * t)


def _foot_pos(
    phase: float,
    params: GaitParams,
    nx: float, ny: float, nz: float,
    step_y: float,
    step_x: float = 0.0,
    rot: float = 0.0,
    body_dip: float = 0.0,
    body_sway: float = 0.0,
    eff_lift: Optional[float] = None,
) -> Tuple[float, float, float]:
    """
    Bereken voetpositie (body frame) voor één been.

    body_dip   — negatieve z verschuiving van het lichaam (mm, negatief = lager)
    body_sway  — x verschuiving voor alle benen (mm, positief = rechts)
    eff_lift   — effectieve lifthoogte na snelheidsscaling (mm)
    """
    if eff_lift is None:
        eff_lift = params.lift_height

    # Stap richting + rotatie correctie
    sx = step_x - rot * ny
    sy = step_y + rot * nx

    # Body dip: verschuif de nul-positie in z voor dit been
    nz_eff = nz + body_dip

    if phase < params.swing_frac:
        # ── SWING ──────────────────────────────────────────────
        t = phase / params.swing_frac
        t_e = _ease(t)
        x = nx + sx * (t_e - 0.5) + body_sway
        y = ny + sy * (t_e - 0.5)
        z = nz_eff + eff_lift * math.sin(math.pi * t)
    else:
        # ── STANCE ─────────────────────────────────────────────
        t = (phase - params.swing_frac) / (1.0 - params.swing_frac)
        t_e = _ease(t)
        x = nx + sx * (0.5 - t_e) + body_sway
        y = ny + sy * (0.5 - t_e)
        z = nz_eff

    return x, y, z


def run_gait(
    legs: List[Leg],
    params: GaitParams,
    ser: serial.Serial,
    step_y: Optional[float] = None,
    step_x: float = 0.0,
    use_imu: bool = True,
    kp_yaw: float = 0.003,
    duration: Optional[float] = None,
) -> None:
    """
    Voer gait uit op 50 Hz met vier biologische verbeteringen.

    Per frame:
        [Accel]   current_step ramp naar target_step (accel_rate mm/s²)
        [Swing]   bepaal welk been in swing zit en zijn voortgang t∈[0,1]
        [Dip]     body_dip_z  = -body_dip · sin(π·t_swing)
        [Sway]    body_sway_x = ±body_sway · sin(π·t_swing)
        [Lift]    eff_lift    = lift_height · clamp(speed/nominal, min_frac, 1.0)
        [Loop]    6× _foot_pos → move_tip
        [IMU]     elke 2s: yaw lezen, rot bijwerken
    """
    target_step_y = params.step_length if step_y is None else step_y
    current_step_y = 0.0   # begint stil, ramt op

    DT = 0.02
    phase = 0.0
    rot = 0.0
    yaw_ref: Optional[float] = None
    last_imu = 0.0
    t_start = time.time()

    print(f"\n[GAIT] {params.name}")
    print(f"  period={params.period:.1f}s | swing={params.swing_frac:.3f} "
          f"| lift={params.lift_height:.0f}mm | step={target_step_y:.0f}mm")
    print(f"  dip={params.body_dip:.0f}mm | sway={params.body_sway:.0f}mm "
          f"| accel={params.accel_rate:.0f}mm/s² | IMU={'aan' if use_imu else 'uit'}")
    if 'centipede' in params.name:
        print(f"  volgorde: RR → LR → RM → LM → RF → LF")
    print()

    try:
        while True:
            t0 = time.time()
            if duration is not None and (t0 - t_start) >= duration:
                break

            # ── 1. ACCELERATIE ────────────────────────────────────
            # Lineaire ramp: current_step_y ramt naar target_step_y
            delta = params.accel_rate * DT
            diff = target_step_y - current_step_y
            if abs(diff) <= delta:
                current_step_y = target_step_y
            else:
                current_step_y += delta * (1.0 if diff > 0 else -1.0)

            # ── 2. BEPAAL SWINGEND BEEN ───────────────────────────
            # Centipede: altijd precies 1 been in swing
            swing_idx = -1
            swing_t = 0.0
            for i in range(6):
                lp = (phase + params.leg_offsets[i]) % 1.0
                if lp < params.swing_frac:
                    swing_idx = i
                    swing_t = lp / params.swing_frac   # 0→1 door swing fase
                    break

            swing_envelope = math.sin(math.pi * swing_t) if swing_idx >= 0 else 0.0

            # ── 3. BODY DIP ───────────────────────────────────────
            # Lichaam zakt naarmate het swingend been stijgt
            # Peak bij t=0.5 (been op maximale hoogte), 0 bij t=0 en t=1
            body_dip_z = -params.body_dip * swing_envelope

            # ── 4. BODY SWAY ──────────────────────────────────────
            # Zwaaien naar de stance-zijde (weg van het swingend been)
            # Rechts been swingt → sway richting links (+x in body frame)
            # Links been swingt  → sway richting rechts (-x in body frame)
            if swing_idx >= 0:
                sway_sign = +1.0 if LEG_SIDE[swing_idx] > 0 else -1.0
                body_sway_x = sway_sign * params.body_sway * swing_envelope
            else:
                body_sway_x = 0.0

            # ── 5. SNELHEID-AFHANKELIJKE LIFTHOOGTE ──────────────
            # Meer snelheid = meer lift (lineair geschaald)
            # Minimum: lift_min_frac × lift_height (ook bij stilstand)
            if target_step_y > 0:
                speed_frac = min(1.0, abs(current_step_y) / target_step_y)
            else:
                speed_frac = 0.0
            eff_lift = params.lift_height * max(params.lift_min_frac, speed_frac)

            # ── 6. IMU YAW CORRECTIE (elke 2 seconden) ───────────
            if use_imu and (t0 - last_imu) >= 2.0:
                yaw = _read_yaw(ser)
                if yaw is not None:
                    if yaw_ref is None:
                        yaw_ref = yaw
                        print(f"  [IMU] ref yaw={yaw:.2f}°")
                    else:
                        err = yaw - yaw_ref
                        if err >  180.0: err -= 360.0
                        if err < -180.0: err += 360.0
                        rot = kp_yaw * err
                        if abs(err) > 0.5:
                            print(f"  [IMU] drift={err:+.1f}° | corr={rot:.4f}")
                last_imu = t0

            # ── 7. VOETPOSITIES BEREKENEN EN STUREN ──────────────
            for i in range(6):
                nx, ny, nz = NEUTRAL[i]
                leg_phase = (phase + params.leg_offsets[i]) % 1.0

                x, y, z = _foot_pos(
                    leg_phase, params,
                    nx, ny, nz,
                    current_step_y, step_x, rot,
                    body_dip=body_dip_z,
                    body_sway=body_sway_x,
                    eff_lift=eff_lift,
                )
                legs[i].move_tip(point3d(x, y, z))

            # ── 8. FASE BIJWERKEN ─────────────────────────────────
            phase = (phase + DT / params.period) % 1.0

            elapsed = time.time() - t0
            if elapsed < DT:
                time.sleep(DT - elapsed)

    except KeyboardInterrupt:
        print("\n[GAIT] Gestopt.")
    finally:
        # Afremmen voor neutraal (soepele stop)
        print("[GAIT] Afremmen...")
        stop_steps = int(0.5 / DT)   # 0.5 seconden afremmen
        for _ in range(stop_steps):
            current_step_y *= 0.85    # exponentieel afremmen
            for i in range(6):
                nx, ny, nz = NEUTRAL[i]
                leg_phase = (phase + params.leg_offsets[i]) % 1.0
                x, y, z = _foot_pos(leg_phase, params, nx, ny, nz,
                                     current_step_y, step_x, rot)
                legs[i].move_tip(point3d(x, y, z))
            phase = (phase + DT / params.period) % 1.0
            time.sleep(DT)

        print("[GAIT] Neutraal...")
        _go_neutral(legs)


# ════════════════════════════════════════════════════════════════════
# HULPFUNCTIES
# ════════════════════════════════════════════════════════════════════

def _go_neutral(legs: List[Leg]) -> None:
    for i, leg in enumerate(legs):
        nx, ny, nz = NEUTRAL[i]
        leg.move_tip(point3d(nx, ny, nz))
    time.sleep(0.8)


def init_robot(port: str) -> Tuple[List[Leg], serial.Serial]:
    """Servo(ser) verwacht een serial.Serial object."""
    ser = _open_serial(port)
    srv = Servo(ser)
    legs = [Leg(i, srv) for i in range(6)]
    return legs, ser


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Centipede wave gait voor Muto RS',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Biologische parameters (overschrijfbaar via flags):
  --dip    body dip tijdens swing (mm, default: 4)
  --sway   laterale sway naar stance zijde (mm, default: 6)

Centipede volgorde: RR → LR → RM → LM → RF → LF
Body speed:         step / period  (bijv. 30mm / 2.5s = 12 mm/s)
        """,
    )
    parser.add_argument('--test',     default='centipede',
                        choices=['neutral', 'centipede', 'tripod'])
    parser.add_argument('--period',   type=float, default=None)
    parser.add_argument('--lift',     type=float, default=None)
    parser.add_argument('--step',     type=float, default=None)
    parser.add_argument('--dip',      type=float, default=None,
                        help='Body dip hoogte in mm (default: gait preset)')
    parser.add_argument('--sway',     type=float, default=None,
                        help='Body sway breedte in mm (default: gait preset)')
    parser.add_argument('--kp',       type=float, default=0.003)
    parser.add_argument('--no-imu',   action='store_true')
    parser.add_argument('--port',     default='/dev/myserial')
    parser.add_argument('--duration', type=float, default=None)
    args = parser.parse_args()

    print("=" * 56)
    print("  Centipede Gait  —  Yahboom Muto RS")
    print("=" * 56)

    legs, ser = init_robot(args.port)

    if args.test == 'neutral':
        print("\n[TEST] Neutrale positie...")
        _go_neutral(legs)
        print("[KLAAR]")
        return

    params = GAITS['centipede' if args.test == 'centipede' else 'tripod_yahboom']
    if args.period is not None: params.period      = args.period
    if args.lift   is not None: params.lift_height = args.lift
    if args.step   is not None: params.step_length = args.step
    if args.dip    is not None: params.body_dip    = args.dip
    if args.sway   is not None: params.body_sway   = args.sway

    print("\n[INIT] Neutrale positie...")
    _go_neutral(legs)
    time.sleep(0.5)

    run_gait(
        legs=legs,
        params=params,
        ser=ser,
        step_y=params.step_length,
        use_imu=not args.no_imu,
        kp_yaw=args.kp,
        duration=args.duration,
    )


if __name__ == '__main__':
    main()