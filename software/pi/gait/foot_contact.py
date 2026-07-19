#!/usr/bin/env python3
"""
Optie A — Voetcontact detectie via servo hoekfout.
v3: retry logic voor flaky servo responses (STM32 auto-packets vervuilen buffer)
"""
import serial, time, threading

TIBIA_IDS         = [3, 6, 9, 12, 15, 18]
LEG_NAMES         = {3:"RF", 6:"RM", 9:"RR", 12:"LR", 15:"LM", 18:"LF"}
CONTACT_THRESHOLD = 12    # graden
MAX_RETRIES       = 3     # pogingen per servo read

class FootContactDetector:
    def __init__(self, ser: serial.Serial):
        self.ser       = ser
        self.lock      = threading.Lock()
        self.commanded = {sid: None  for sid in TIBIA_IDS}
        self.contact   = {sid: False for sid in TIBIA_IDS}
        self.actual    = {sid: None  for sid in TIBIA_IDS}
        self.error_deg = {sid: 0.0   for sid in TIBIA_IDS}

    def _cs(self, *b):
        return (0xFF - sum(b)) & 0xFF

    def standing_posture(self):
        cs  = self._cs(0x09, 0x01, 0x06, 0x00)
        pkt = bytes([0x55, 0x00, 0x09, 0x01, 0x06, 0x00, cs, 0x00, 0xAA])
        self.ser.write(pkt)

    def _read_angle_raw(self, servo_id) -> int | None:
        """Lees tibia hoek met retry bij buffer vervuiling door STM32 auto-packets."""
        cs  = self._cs(0x09, 0x02, 0x60, servo_id)
        pkt = bytes([0x55, 0x00, 0x09, 0x02, 0x60, servo_id, cs, 0x00, 0xAA])

        for attempt in range(MAX_RETRIES):
            # Flush buffer grondig — wacht op eventuele lopende STM32 transmissie
            time.sleep(0.015 * (attempt + 1))
            self.ser.reset_input_buffer()
            self.ser.write(pkt)
            time.sleep(0.035)
            resp = self.ser.read(64)   # ruimer lezen voor meerdere packets

            # Zoek ons specifieke antwoord: 55 00 0F 12 60
            for i in range(len(resp) - 10):
                if (resp[i]   == 0x55 and resp[i+1] == 0x00 and
                    resp[i+2] == 0x0F and resp[i+3] == 0x12 and resp[i+4] == 0x60):
                    angle = resp[i + 6]
                    if 0 < angle < 200:   # sanity check
                        return angle

            # Geen geldig frame — probeer opnieuw
        return None

    def set_commanded(self, servo_id: int, angle_deg: int):
        if servo_id in self.commanded:
            self.commanded[servo_id] = angle_deg

    def calibrate_baseline(self):
        """Lees alle tibia hoeken als commanded baseline, met retry."""
        print("  Baseline uitlezen...")
        for sid in TIBIA_IDS:
            angle = self._read_angle_raw(sid)
            leg   = LEG_NAMES[sid]
            if angle is not None:
                self.commanded[sid] = angle
                print(f"    {leg} tibia (servo {sid:2d}): {angle}°  ✅")
            else:
                print(f"    {leg} tibia (servo {sid:2d}): geen response na {MAX_RETRIES}x ⚠️")
            time.sleep(0.02)

    def update(self):
        with self.lock:
            for sid in TIBIA_IDS:
                actual = self._read_angle_raw(sid)
                if actual is None:
                    continue
                self.actual[sid] = actual

                cmd = self.commanded[sid]
                if cmd is not None:
                    err = abs(cmd - actual)
                    self.error_deg[sid] = err
                    self.contact[sid]   = err > CONTACT_THRESHOLD
                else:
                    # Nog geen baseline — gebruik huidige meting als baseline
                    self.commanded[sid] = actual
                    self.error_deg[sid] = 0.0
                    self.contact[sid]   = False

                time.sleep(0.01)

    def get_contact(self) -> dict:
        with self.lock:
            return {LEG_NAMES[sid]: self.contact[sid] for sid in TIBIA_IDS}

    def get_status(self) -> dict:
        with self.lock:
            return {
                LEG_NAMES[sid]: {
                    "contact":   self.contact[sid],
                    "commanded": self.commanded[sid],
                    "actual":    self.actual[sid],
                    "error_deg": self.error_deg[sid],
                }
                for sid in TIBIA_IDS
            }


# ── Standalone test ───────────────────────────────────────────────────
if __name__ == "__main__":
    DEVICE = "/dev/myserial"

    print("=" * 50)
    print(" FootContact detector v3")
    print(f" Drempel: {CONTACT_THRESHOLD}°  Retries: {MAX_RETRIES}")
    print("=" * 50)

    ser = serial.Serial(DEVICE, baudrate=115200, timeout=0.3)
    time.sleep(0.2)
    fc = FootContactDetector(ser)

    # 1. Startstand
    print("\n[1/3] Startstand commando sturen...")
    fc.standing_posture()
    for i in range(3, 0, -1):
        print(f"      {i}...", end="\r")
        time.sleep(1)
    print("      Klaar ✅          ")

    # 2. Baseline
    print("\n[2/3] Baseline hoeken vastleggen:")
    fc.calibrate_baseline()
    print("      Baseline opgeslagen ✅")

    # 3. Live monitoring
    print(f"\n[3/3] Live contact detectie (drempel={CONTACT_THRESHOLD}°)")
    print("      Til robot op → alle poten 'vrij'")
    print("      Zet neer    → alle poten 'GROND'")
    print("      Ctrl+C = stoppen\n")
    print(f"  {'RF':>7} {'RM':>7} {'RR':>7} {'LR':>7} {'LM':>7} {'LF':>7}")
    print("  " + "-" * 44)

    try:
        while True:
            fc.update()
            s = fc.get_status()
            line = "  "
            for leg in ["RF", "RM", "RR", "LR", "LM", "LF"]:
                st = s[leg]
                if st["commanded"] is None:
                    marker = "  ???"
                elif st["contact"]:
                    marker = "GROND"
                else:
                    marker = f" {st['error_deg']:3.0f}°"
                line += f"{marker:>7}"
            print(line, end="\r")
            time.sleep(0.15)

    except KeyboardInterrupt:
        print("\n\nEindstatus:")
        for leg, st in fc.get_status().items():
            status = "GROND" if st["contact"] else "vrij"
            print(f"  {leg}: actual={st['actual']}°  "
                  f"cmd={st['commanded']}°  "
                  f"err={st['error_deg']:.0f}°  "
                  f"→ {status}")

    ser.close()
