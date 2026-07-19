#!/usr/bin/env python3
"""
Contact detectie via actieve probe:
- Stuur elke tibia 20° omlaag (probeer in vloer te duwen)
- Als grond blokkeert → error groot → GROND
- Als poot vrij in lucht → servo volgt → error klein → vrij

Test 1: robot op grond   → verwacht alle GROND
Test 2: robot optillen   → verwacht alle vrij
"""
import serial, time

DEVICE            = "/dev/myserial"
TIBIA_IDS         = [3, 6, 9, 12, 15, 18]
LEG_NAMES         = {3:"RF", 6:"RM", 9:"RR", 12:"LR", 15:"LM", 18:"LF"}
PROBE_OFFSET      = 20    # graden omlaag proberen
CONTACT_THRESHOLD = 10    # graden — groter dan speling (~3°), kleiner dan probe (20°)
MAX_RETRIES       = 3

def cs(*b):
    return (0xFF - sum(b)) & 0xFF

def standing_posture(ser):
    c   = cs(0x09, 0x01, 0x06, 0x00)
    ser.write(bytes([0x55, 0x00, 0x09, 0x01, 0x06, 0x00, c, 0x00, 0xAA]))

def move_servo(ser, servo_id, angle, speed=60):
    sh, sl = (speed >> 8) & 0xFF, speed & 0xFF
    c   = cs(0x09, 0x01, 0x40, servo_id, angle, sh, sl)
    ser.write(bytes([0x55, 0x00, 0x0C, 0x01, 0x40,
                     servo_id, angle, sh, sl, c, 0x00, 0xAA]))

def read_angle(ser, servo_id) -> int | None:
    for _ in range(MAX_RETRIES):
        c   = cs(0x09, 0x02, 0x60, servo_id)
        pkt = bytes([0x55, 0x00, 0x09, 0x02, 0x60, servo_id, c, 0x00, 0xAA])
        ser.reset_input_buffer()
        ser.write(pkt)
        time.sleep(0.035)
        resp = ser.read(64)
        for i in range(len(resp) - 10):
            if (resp[i]==0x55 and resp[i+1]==0x00 and
                resp[i+2]==0x0F and resp[i+3]==0x12 and resp[i+4]==0x60):
                a = resp[i+6]
                if 0 < a < 200:
                    return a
        time.sleep(0.015)
    return None

def probe_contact(ser, baselines) -> dict:
    """Stuur elke tibia 20° omlaag, meet error, herstel naar baseline."""
    results = {}
    for sid in TIBIA_IDS:
        leg      = LEG_NAMES[sid]
        baseline = baselines[sid]
        target   = max(baseline - PROBE_OFFSET, 20)

        # Beweeg omlaag
        move_servo(ser, sid, target, speed=60)
        time.sleep(0.4)

        # Lees werkelijke positie
        actual = read_angle(ser, sid)

        # Herstel naar baseline
        move_servo(ser, sid, baseline, speed=60)
        time.sleep(0.3)

        if actual is not None:
            error   = abs(target - actual)
            contact = error > CONTACT_THRESHOLD
            results[leg] = {
                "baseline": baseline,
                "target":   target,
                "actual":   actual,
                "error":    error,
                "contact":  contact
            }
        else:
            results[leg] = None

    return results

def print_results(results, label):
    print(f"\n  [{label}]")
    print(f"  {'Poot':<5} {'base':>5} {'→doel':>6} {'actual':>7} {'error':>6} {'status':>7}")
    print("  " + "-" * 42)
    for leg in ["RF","RM","RR","LR","LM","LF"]:
        r = results.get(leg)
        if r is None:
            print(f"  {leg:<5} {'geen response':>36}")
        else:
            status = "GROND ✅" if r["contact"] else "  vrij"
            print(f"  {leg:<5} {r['baseline']:>5}° "
                  f"{r['target']:>5}° "
                  f"{r['actual']:>6}° "
                  f"{r['error']:>5}°  "
                  f"{status}")

# ── Hoofdprogramma ───────────────────────────────────────────
ser = serial.Serial(DEVICE, baudrate=115200, timeout=0.3)
time.sleep(0.2)

print("=" * 50)
print(" Probe contact test")
print(f" Probe offset: -{PROBE_OFFSET}°  Drempel: {CONTACT_THRESHOLD}°")
print("=" * 50)

# Startstand + baseline
print("\nNaar startstand...")
standing_posture(ser)
time.sleep(3)

print("Baselines uitlezen...")
baselines = {}
for sid in TIBIA_IDS:
    a = read_angle(ser, sid)
    baselines[sid] = a if a else 100
    print(f"  {LEG_NAMES[sid]}: {baselines[sid]}°")
    time.sleep(0.03)

# Test 1: robot op de grond
input("\n[Test 1] Robot staat op de grond — druk ENTER om te meten...")
r1 = probe_contact(ser, baselines)
print_results(r1, "ROBOT OP GROND — verwacht alle GROND")

# Herstel
standing_posture(ser)
time.sleep(2)

# Test 2: robot optillen
input("\n[Test 2] Til de robot nu op — druk ENTER als hij vrij hangt...")
r2 = probe_contact(ser, baselines)
print_results(r2, "ROBOT IN LUCHT — verwacht alle vrij")

# Herstel
standing_posture(ser)
time.sleep(2)

print("\nKlaar — probe test afgerond.")
ser.close()
