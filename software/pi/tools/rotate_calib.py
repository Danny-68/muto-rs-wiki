#!/usr/bin/env python3
"""
rotate_calib.py — kalibratietest voor de closed-loop rotatie.
Roept het draaiende robot_bridge.py aan (poort 5000) en draait een reeks
hoeken, met pauze zodat je de FYSIEKE afwijking kunt noteren.

De bridge blijft gewoon draaien; dit script praat er alleen mee via HTTP.

Gebruik:
    python3 /home/pi/rotate_calib.py

Voor elke hoek zie je:
    - gevraagd (requested_deg)
    - gemeten door IMU (turned_deg)
    - start/eind yaw
En jij noteert wat je FYSIEK ziet (bijv. met een markering op de vloer).
"""
import requests
import time

BRIDGE = "http://localhost:5000"

# Reeks testhoeken. Groot = makkelijker fysiek te beoordelen.
# Positief = links, negatief = rechts.
TEST_ANGLES = [180, -180, 360, -360, 90, -90]

def rotate(angle):
    r = requests.post(f"{BRIDGE}/robot/rotate_to_angle",
                      json={"angle_deg": angle}, timeout=60)
    return r.json()

def main():
    print("=" * 60)
    print("ROTATIE KALIBRATIE")
    print("=" * 60)
    print("Tip: leg een markering neer (bv. tape) en richt de 'neus' van")
    print("de robot daar precies op voor elke meting. Zo zie je de")
    print("fysieke afwijking het scherpst, vooral bij 180 en 360 graden.")
    print()

    results = []
    for angle in TEST_ANGLES:
        richting = "links" if angle > 0 else "rechts"
        input(f">>> Klaar om {abs(angle)} graden naar {richting} te draaien? "
              f"Richt de robot op de markering en druk Enter...")
        print(f"    Draaien: {angle} graden...")
        res = rotate(angle)
        turned = res.get("turned_deg", "?")
        print(f"    IMU meet: {turned} graden  (start_yaw={res.get('start_yaw')}, "
              f"end_yaw={res.get('end_yaw')})")
        fysiek = input(f"    Wat zie JIJ fysiek? (schat graden, of Enter om over te slaan): ").strip()
        results.append({
            "gevraagd": angle,
            "imu_gemeten": turned,
            "fysiek_gezien": fysiek or "n.v.t.",
        })
        print()
        time.sleep(0.5)

    print("=" * 60)
    print("SAMENVATTING")
    print("=" * 60)
    print(f"{'gevraagd':>10} | {'IMU meet':>10} | {'fysiek gezien':>14}")
    print("-" * 40)
    for r in results:
        print(f"{r['gevraagd']:>10} | {str(r['imu_gemeten']):>10} | {r['fysiek_gezien']:>14}")
    print()
    print("Plak deze tabel terug in de chat, dan bepalen we de exacte")
    print("marge-correctie (constant of hoek-afhankelijk).")

if __name__ == "__main__":
    main()