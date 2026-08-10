#!/usr/bin/env python3
"""
phoenix_yaw_drift_test.py — Yaw-drift karakterisering voor phoenix_gait.py
v3: vloeiende stop (decel binnen gait + geinterpoleerde overgang naar
neutraal) i.p.v. abrupte snap. Retry op IMU-read, pkill app_muto.py vooraf.
"""
import sys
import math
import time
import serial

sys.path.insert(0, '/root')
from phoenix_gait import (PhoenixGait, HardwareInterface, GAITS,
                           NEUTRAL_POS, ease)


def read_imu_yaw(ser: serial.Serial, retries: int = 3) -> float:
    cmd = bytes([0x55, 0x00, 0x09, 0x02, 0x60, 0x07, 0x8D, 0x00, 0xAA])
    last_err = None
    for attempt in range(retries):
        try:
            ser.reset_input_buffer()
            ser.write(cmd)
            time.sleep(0.05 + attempt * 0.05)
            resp = ser.read(20)
            if len(resp) < 11:
                raise RuntimeError(f"IMU-antwoord te kort: {len(resp)} bytes")
            yaw_raw = (resp[9] << 8) | resp[10]
            if yaw_raw >= 32768:
                yaw_raw -= 65536
            yaw = yaw_raw / 100.0
            if abs(yaw) > 180.5:
                raise RuntimeError(f"Yaw buiten geldig bereik: {yaw}")
            return yaw
        except RuntimeError as e:
            last_err = e
            time.sleep(0.1)
    raise RuntimeError(f"IMU-read mislukt na {retries} pogingen: {last_err}")


def run_cycles(iface, gait, engine, cycles: float, direction: float = 1.0,
               sway: bool = True, hz: int = 50):
    """Draai <cycles> cycli op volle snelheid. Retourneert laatst verstuurde posities."""
    dt = 1.0 / hz
    global_phase = 0.0
    steps_needed = int(cycles * gait.cycle_time_s / dt)
    positions = None
    for _ in range(steps_needed):
        positions, _ = engine.foot_targets(global_phase, gait,
                                            travel_x=direction,
                                            target_speed=1.0,
                                            body_sway=sway, body_dip=True)
        iface.send(positions)
        time.sleep(dt)
        global_phase = (global_phase + dt / gait.cycle_time_s) % 1.0
    return positions, global_phase


def decel_to_stop(iface, gait, engine, global_phase, direction, sway=True,
                   duration_s=1.0, hz=50):
    """Laat de gait uitlopen: target_speed=0 zodat _speed_ramp exponentieel
    naar 0 decayt, robot zet nog een laatste, vertragende stap i.p.v. abrupt
    stoppen midden-swing."""
    dt = 1.0 / hz
    steps = int(duration_s * hz)
    positions = None
    for _ in range(steps):
        positions, _ = engine.foot_targets(global_phase, gait,
                                            travel_x=direction,
                                            target_speed=0.0,
                                            body_sway=sway, body_dip=True)
        iface.send(positions)
        time.sleep(dt)
        global_phase = (global_phase + dt / gait.cycle_time_s) % 1.0
    return positions


def smooth_to_neutral(iface, from_positions, duration_s=1.0, hz=50):
    """Sinusoidale interpolatie van huidige pootposities naar NEUTRAL_POS,
    i.p.v. een instant snap."""
    if from_positions is None:
        from_positions = list(NEUTRAL_POS)
    dt = 1.0 / hz
    steps = int(duration_s * hz)
    for s in range(1, steps + 1):
        t = ease(s / steps)
        interp = []
        for (fx, fy, fz), (nx, ny, nz) in zip(from_positions, NEUTRAL_POS):
            interp.append((fx + (nx - fx) * t,
                           fy + (ny - fy) * t,
                           fz + (nz - fz) * t))
        iface.send(interp)
        time.sleep(dt)


def stable_stop(iface, gait, engine, global_phase, direction, sway=True):
    """Volledige, vloeiende stop-sequentie: decel binnen gait + interpolatie
    naar neutraal. Vervangt de oude abrupte return_to_neutral()."""
    last_pos = decel_to_stop(iface, gait, engine, global_phase, direction,
                              sway=sway, duration_s=1.0)
    smooth_to_neutral(iface, last_pos, duration_s=1.0)
    time.sleep(0.3)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--direction', choices=['forward', 'backward'], required=True)
    p.add_argument('--cycles', type=float, default=5.3)
    p.add_argument('--reps', type=int, default=2)
    p.add_argument('--port', default='/dev/myserial')
    args = p.parse_args()

    iface = HardwareInterface(port=args.port, exec_time_ms=18)
    gait = GAITS['tripod']
    direction = 1.0 if args.direction == 'forward' else -1.0

    results = []
    for rep in range(1, args.reps + 1):
        engine = PhoenixGait()  # verse speed-ramp state per rep
        input(f"\n--- Rep {rep}/{args.reps} ({args.direction}) ---\n"
              f"Zorg dat de robot recht staat en op de startpositie.\n"
              f"Druk Enter om te starten...")

        try:
            yaw_before = read_imu_yaw(iface._ser)
        except RuntimeError as e:
            print(f"[FOUT] {e} — deze rep wordt overgeslagen.")
            continue
        print(f"[YAW] Referentie voor start: {yaw_before:.2f}°")

        _, phase_at_stop = run_cycles(iface, gait, engine, args.cycles,
                                       direction=direction, sway=True)

        print("[INFO] Vloeiend afremmen en naar neutrale stand...")
        stable_stop(iface, gait, engine, phase_at_stop, direction, sway=True)

        try:
            yaw_after = read_imu_yaw(iface._ser)
        except RuntimeError as e:
            print(f"[FOUT] {e} — drift voor deze rep onbekend.")
            continue

        drift = yaw_after - yaw_before
        print(f"[YAW] Na {args.cycles} cycli ({args.direction}): "
              f"{yaw_after:.2f}° (drift: {drift:+.2f}°)")

        actual_cm = input("Gemeten werkelijke afstand in cm (meetlint, "
                           "Enter om over te slaan): ").strip()

        results.append({
            'rep': rep, 'direction': args.direction, 'cycles': args.cycles,
            'yaw_before': yaw_before, 'yaw_after': yaw_after, 'drift': drift,
            'measured_cm': actual_cm or None,
        })

        print("[INFO] Robot staat neutraal. Handmatig terug naar startpositie voor volgende rep.")

    print("\n" + "=" * 60)
    print("SAMENVATTING")
    print("=" * 60)
    for r in results:
        cm = r['measured_cm'] or '?'
        print(f"Rep {r['rep']} | {r['direction']:8s} | {r['cycles']} cycli | "
              f"drift {r['drift']:+.2f}° | gemeten {cm}cm")

    iface.destroy()


if __name__ == '__main__':
    main()
