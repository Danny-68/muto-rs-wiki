#!/usr/bin/env python3
"""Zoekt de diepste (meest horizontale) IK-geldige splay-pose, puur in
software (geen hardware-beweging) -- voor een dieper play_dead t.b.v. de
draaischijf-test (gebruiker wil poten horizontaler dan de huidige
SPLAY_EXTEND=35/SPLAY_Z=-62)."""
import sys
import math
sys.path.insert(0, "/home/pi/muto/MutoLib/MutoLib")
from MutoLib.base import point3d
sys.path.insert(0, "/home/pi")
from body_pose import BodyPose

class Dummy:
    def write(self, *a): pass
    def flush(self): pass

bp = BodyPose(Dummy())

def make_splay(extend, z):
    out = []
    for p in bp.neutral:
        r = math.hypot(p.x, p.y)
        ux, uy = (p.x / r, p.y / r) if r > 1e-6 else (1.0, 0.0)
        out.append(point3d(p.x + extend * ux, p.y + extend * uy, z))
    return out

best = None
for extend in range(35, 141, 5):
    for z in [x * -1 for x in range(0, 95, 5)]:  # van -90 (huidige buurt) tot 0
        cand = make_splay(extend, z)
        if bp._validate(cand):
            if best is None or z > best[1]:  # minder negatief = dieper gezakt
                best = (extend, z)

print(f"Diepste geldige splay: EXTEND={best[0]}mm, Z={best[1]}mm" if best else "Geen geldige diepere pose gevonden")
if best:
    cand = make_splay(*best)
    for i, p in enumerate(cand):
        print(f"  poot {i}: x={p.x:.1f} y={p.y:.1f} z={p.z:.1f}")
