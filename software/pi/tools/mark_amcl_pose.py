#!/usr/bin/env python3
"""Genereert een ingezoomde kaartafbeelding met AMCL's geschatte positie+oriëntatie
gemarkeerd (rode stip + pijl), voor visuele koerscorrectie door de gebruiker."""
import yaml
import math
from PIL import Image, ImageDraw
import subprocess
import re
import sys

MAP_YAML = "/home/pi/lidar_only_map.yaml"
MAP_PGM = "/home/pi/lidar_only_map.pgm"
OUT_PATH = "/home/pi/amcl_pose_marked.png"


def get_amcl_pose():
    out = subprocess.run(
        ["docker", "exec", "humble_run", "bash", "-c",
         "source /opt/ros/humble/setup.bash && timeout 4 ros2 topic echo /amcl_pose --once 2>/dev/null"],
        capture_output=True, text=True, timeout=15).stdout
    def grab(key, text, occurrence=0):
        vals = re.findall(rf"{key}:\s*(-?[\d.eE+-]+)", text)
        return float(vals[occurrence])
    x = grab("x", out, 0)
    y = grab("y", out, 0)
    qz = grab("z", out, 1)
    qw = grab("w", out, 0)
    yaw = 2.0 * math.atan2(qz, qw)
    return x, y, yaw


def main():
    with open(MAP_YAML) as f:
        m = yaml.safe_load(f)
    res = m["resolution"]
    origin_x, origin_y, _ = m["origin"]

    img = Image.open(MAP_PGM).convert("RGB")
    w, h = img.size

    x, y, yaw = get_amcl_pose()
    print(f"AMCL pose: x={x:.3f} y={y:.3f} yaw={math.degrees(yaw):.1f} graden")

    px = (x - origin_x) / res
    py = h - 1 - (y - origin_y) / res

    draw = ImageDraw.Draw(img)
    r = 6
    draw.ellipse([px - r, py - r, px + r, py + r], fill=(255, 0, 0))
    arrow_len = 40
    ax = px + arrow_len * math.cos(yaw)
    ay = py - arrow_len * math.sin(yaw)
    draw.line([px, py, ax, ay], fill=(255, 0, 0), width=3)

    zoom = 300
    box = (max(0, int(px - zoom)), max(0, int(py - zoom)),
           min(w, int(px + zoom)), min(h, int(py + zoom)))
    cropped = img.crop(box)
    cropped = cropped.resize((cropped.width * 2, cropped.height * 2), Image.NEAREST)
    cropped.save(OUT_PATH)
    print(f"Opgeslagen: {OUT_PATH}")


if __name__ == "__main__":
    main()
