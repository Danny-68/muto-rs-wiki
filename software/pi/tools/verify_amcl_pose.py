#!/usr/bin/env python3
"""
Objectieve verificatie van AMCL's pose: vergelijkt live /scan_fixed-metingen
op 0/90/180/270 graden (robot-relatief) met een 2D-raycast tegen de kaart
vanaf de huidige AMCL-pose. Grote, consistente afwijkingen op meerdere
richtingen = echte lokalisatiefout; een enkele afwijking dicht bij een
deuropening/kozijn is normaal.
"""
import yaml
import math
import json
import subprocess
import re
from PIL import Image

MAP_YAML = "/home/pi/lidar_only_map.yaml"
MAP_PGM = "/home/pi/lidar_only_map.pgm"
MAX_RANGE = 8.0


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


def get_scan_ranges():
    """
    Leest /scan_fixed en retourneert (angle_min, angle_increment, ranges[]).
    LET OP (11 aug 2026): eerdere versie parsete de tekst-output van
    'ros2 topic echo' met een regex -- dat bleek onbetrouwbaar voor grote
    arrays (2020 elementen), de CLI/weergave knipt af en de regex ving dan
    maar een deel (kwam als "128 punten" naar boven, zie PROBLEMS.md). Nu:
    rechtstreeks via rclpy, geen tekst-parsing van array-velden meer.
    """
    script = (
        "import rclpy\n"
        "from rclpy.node import Node\n"
        "from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy\n"
        "from sensor_msgs.msg import LaserScan\n"
        "import json, sys\n"
        "class N(Node):\n"
        "    def __init__(self):\n"
        "        super().__init__('scan_reader_tmp')\n"
        "        self.msg = None\n"
        "        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT,\n"
        "                          history=HistoryPolicy.KEEP_LAST)\n"
        "        self.create_subscription(LaserScan, '/scan_fixed', self.cb, qos)\n"
        "    def cb(self, m):\n"
        "        self.msg = m\n"
        "rclpy.init()\n"
        "n = N()\n"
        "while n.msg is None:\n"
        "    rclpy.spin_once(n, timeout_sec=1.0)\n"
        "print(json.dumps({'angle_min': n.msg.angle_min, 'angle_increment': n.msg.angle_increment,\n"
        "                   'ranges': list(n.msg.ranges)}))\n"
        "n.destroy_node()\n"
        "rclpy.shutdown()\n"
    )
    with open("/tmp/_scan_reader_tmp.py", "w") as f:
        f.write(script)
    subprocess.run(["docker", "cp", "/tmp/_scan_reader_tmp.py",
                     "humble_run:/root/_scan_reader_tmp.py"], check=True)
    out = subprocess.run(
        ["docker", "exec", "humble_run", "bash", "-c",
         "source /opt/ros/humble/setup.bash && timeout 8 python3 /root/_scan_reader_tmp.py 2>/dev/null"],
        capture_output=True, text=True, timeout=20).stdout
    data = json.loads(out.strip().splitlines()[-1])
    ranges = [float('nan') if r != r else r for r in data["ranges"]]
    return data["angle_min"], data["angle_increment"], ranges


def scan_range_at(angle_deg, angle_min, angle_inc, ranges):
    a = math.radians(angle_deg)
    idx = int(round((a - angle_min) / angle_inc)) % len(ranges)
    r = ranges[idx]
    return r if (r == r and r != float('inf')) else None  # filter nan/inf


def load_map():
    with open(MAP_YAML) as f:
        m = yaml.safe_load(f)
    img = Image.open(MAP_PGM).convert("L")
    return img, m["resolution"], m["origin"][0], m["origin"][1], m["occupied_thresh"]


def raycast(img, res, ox, oy, occ_thresh, x, y, angle_world, max_range=MAX_RANGE):
    w, h = img.size
    px_data = img.load()
    step = res  # 1 pixel per stap
    dist = 0.0
    while dist < max_range:
        wx = x + dist * math.cos(angle_world)
        wy = y + dist * math.sin(angle_world)
        px = int((wx - ox) / res)
        py = h - 1 - int((wy - oy) / res)
        if px < 0 or px >= w or py < 0 or py >= h:
            return None
        val = px_data[px, py] / 255.0
        if val < (1.0 - occ_thresh):  # donker = occupied (PGM: 0=zwart/occupied bij negate=0, trinary)
            return dist
        dist += step
    return None


def main():
    x, y, yaw = get_amcl_pose()
    print(f"AMCL pose: x={x:.3f} y={y:.3f} yaw={math.degrees(yaw):.1f} graden\n")

    angle_min, angle_inc, ranges = get_scan_ranges()
    img, res, ox, oy, occ_thresh = load_map()

    print(f"{'hoek (robot)':>14} | {'laser (m)':>10} | {'raycast (m)':>11} | {'verschil':>9}")
    print("-" * 55)
    for rel_deg in (0, 90, 180, 270):
        laser_r = scan_range_at(rel_deg, angle_min, angle_inc, ranges)
        world_angle = yaw + math.radians(rel_deg)
        rc = raycast(img, res, ox, oy, occ_thresh, x, y, world_angle)
        laser_s = f"{laser_r:.2f}" if laser_r is not None else "geen"
        rc_s = f"{rc:.2f}" if rc is not None else "geen"
        if laser_r is not None and rc is not None:
            diff = f"{laser_r - rc:+.2f}"
        else:
            diff = "n.v.t."
        print(f"{rel_deg:>13}° | {laser_s:>10} | {rc_s:>11} | {diff:>9}")


if __name__ == "__main__":
    main()
