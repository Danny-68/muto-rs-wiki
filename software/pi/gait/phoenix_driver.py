#!/usr/bin/env python3
"""
phoenix_driver.py — Nav2-bewegingsbackend op basis van PhoenixGait (tripod-only)
i.p.v. de STM32-firmware-gait (0x12-0x17) die muto_driver_fixed.py aanstuurt.

Vervangt muto_driver_fixed.py NIET — dat bestand blijft intact als terugval-
optie. Dit is een apart te starten/stoppen ROS2-node die op hetzelfde topic
('cmd_vel', gevoed via de bestaande `ros2 run topic_tools relay /cmd_vel_nav
/cmd_vel`) abonneert, zodat de rest van de Nav2-stack ongewijzigd blijft.

Nog NIET in de Nav2-launch-keten gehaakt — dit bestand is voor stap 1
(zelfstandig bouwen en los testen), per expliciete instructie.

--------------------------------------------------------------------------
KALIBRATIE-STATUS — zie ook PROBLEMS.md:

  MAX_LINEAR_SPEED_MPS    — geschat uit gemeten ~9.5cm/cyclus bij
                             cycle_time_s=1.6s (phoenix_yaw_drift_test.py,
                             10 aug 2026). Nooit apart gevalideerd bij
                             gedeeltelijke (niet-volle) snelheid.
  MAX_ANGULAR_SPEED_RADPS — GEKALIBREERD 10 aug 2026 via /imu (extern,
                             ICM20948) met phoenix_driver.py zelf als
                             bewegingsbron (n=3: +5.14 graden/2s,
                             +4.66 graden/2s, +15.24 graden/5s bij
                             angular.z aan/boven de max). Resultaat:
                             ~3.0-3.3 graden/s bij volle inzet, dus
                             ~0.055 rad/s -- de oorspronkelijke placeholder
                             (0.5 rad/s) stond ~9x te hoog. Een gebruiker
                             schatte de eerste test visueel op "~40 graden"
                             i.p.v. de gemeten 5.14 graden -- makkelijk te
                             overschatten bij een zwaaiende hexapod-gait,
                             vertrouw hier de IMU-meting. n=3 is een eerste
                             indicatie, geen definitieve validatie.
--------------------------------------------------------------------------
"""
import math
import subprocess
import sys
import threading
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

sys.path.insert(0, '/root')
from phoenix_gait import PhoenixGait, HardwareInterface, GAITS, NEUTRAL_POS, ease

SERIAL_PORT = '/dev/myserial'
HZ = 50
DT = 1.0 / HZ

# -- zie "KALIBRATIE-STATUS" hierboven --
MAX_LINEAR_SPEED_MPS = 0.0594
MAX_ANGULAR_SPEED_RADPS = 0.055  # gekalibreerd 10 aug 2026, n=3, zie boven

CMD_TIMEOUT_S = 5.0  # zelfde als de huidige live waarde in muto_driver_fixed.py
CMD_DEADBAND = 0.02  # onder deze genormaliseerde waarde tellen we als "stil"
DECEL_DURATION_S = 1.0
NEUTRAL_DURATION_S = 1.0
# Live Nav2-test (10 aug 2026) toonde dat de controller vaak kort onder de
# deadband duikt tijdens normale bijsturing (~elke 2.5-3s een dip) -- zonder
# debounce triggerde dat elke keer de volledige (2s, blokkerende) stop-
# sequentie, waardoor de robot nooit vooruitkwam. Pas als "stil" langer dan
# deze tijd aanhoudt, behandelen we het als een echte stop.
STOP_DEBOUNCE_S = 0.5


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _stop_app_muto():
    """Zelfde noodzaak als robot_bridge.py: app_muto.py en phoenix_driver.py
    delen exclusief /dev/myserial, en een seriele-poort-conflict corrumpeert
    IMU-/servocommunicatie (zie GAIT.md, 'Bekende valkuil')."""
    if subprocess.run(["pgrep", "-f", "app_muto.py"], capture_output=True).returncode == 0:
        print("[startup] app_muto.py actief, wordt gestopt (serial poort vrijmaken)...")
        subprocess.run(["pkill", "-f", "app_muto.py"])
        time.sleep(2)
        subprocess.run(["pkill", "-9", "-f", "app_muto.py"])
        time.sleep(1)


class PhoenixDriver(Node):
    def __init__(self):
        super().__init__('phoenix_driver')
        self._lock = threading.Lock()

        self.iface = HardwareInterface(port=SERIAL_PORT, exec_time_ms=18)
        self.engine = PhoenixGait()
        self.gait = GAITS['tripod']  # UITSLUITEND tripod, per expliciete eis

        self.travel_x = 0.0
        self.rotate = 0.0
        self.target_speed = 0.0
        self.state = 'idle'  # 'idle' | 'moving'
        self.global_phase = 0.0
        self.last_cmd = self.get_clock().now()
        self.zero_since = None

        self.sub = self.create_subscription(Twist, 'cmd_vel', self.cb, 10)
        self.create_timer(0.3, self.timeout_check)
        self.create_timer(DT, self._step)
        self.get_logger().info(
            'Phoenix driver gestart (tripod-only, PhoenixGait i.p.v. STM32-firmware-gait)')

    def cb(self, msg):
        self.last_cmd = self.get_clock().now()
        with self._lock:
            travel_x = clamp(msg.linear.x / MAX_LINEAR_SPEED_MPS, -1.0, 1.0)
            rotate = clamp(msg.angular.z / MAX_ANGULAR_SPEED_RADPS, -1.0, 1.0)
            want_moving = abs(travel_x) > CMD_DEADBAND or abs(rotate) > CMD_DEADBAND
            self.travel_x = travel_x
            self.rotate = rotate
            if want_moving:
                self.zero_since = None
                if self.state == 'idle':
                    self.state = 'moving'
                    self.target_speed = 1.0
            elif self.state == 'moving' and self.zero_since is None:
                # Zie STOP_DEBOUNCE_S -- niet meteen stoppen, eerst afwachten
                # of dit een kortstondige dip is (normaal Nav2-controllergedrag)
                # of een echte stop.
                self.zero_since = self.get_clock().now()

    def _check_stop_debounce(self):
        with self._lock:
            if self.state != 'moving' or self.zero_since is None:
                return
            elapsed = (self.get_clock().now() - self.zero_since).nanoseconds / 1e9
            should_stop = elapsed > STOP_DEBOUNCE_S
        if should_stop:
            self._do_stable_stop()

    def _step(self):
        if self.state != 'moving':
            return
        with self._lock:
            travel_x, rotate, target_speed = self.travel_x, self.rotate, self.target_speed
        positions, _ = self.engine.foot_targets(
            self.global_phase, self.gait,
            travel_x=travel_x, travel_z=0.0, rotate=rotate,
            target_speed=target_speed, body_sway=True, body_dip=True)
        self.iface.send(positions)
        self.global_phase = (self.global_phase + DT / self.gait.cycle_time_s) % 1.0

    def _do_stable_stop(self):
        """Vloeiende stop: decel binnen de gait (target_speed -> 0) gevolgd
        door sinusoidale interpolatie naar NEUTRAL_POS. Zelfde patroon als
        stable_stop() in phoenix_yaw_drift_test.py, gegeneraliseerd naar
        gecombineerde travel_x+rotate (de referentie-implementatie test alleen
        pure vooruit/achteruit, geen gecombineerde beweging+draai)."""
        self.get_logger().info('Vloeiende stop-sequentie (decel + neutraal)')
        with self._lock:
            last_travel_x, last_rotate = self.travel_x, self.rotate

        decel_steps = int(DECEL_DURATION_S * HZ)
        last_pos = None
        for _ in range(decel_steps):
            positions, _ = self.engine.foot_targets(
                self.global_phase, self.gait,
                travel_x=last_travel_x, travel_z=0.0, rotate=last_rotate,
                target_speed=0.0, body_sway=True, body_dip=True)
            self.iface.send(positions)
            last_pos = positions
            time.sleep(DT)
            self.global_phase = (self.global_phase + DT / self.gait.cycle_time_s) % 1.0

        neutral_steps = int(NEUTRAL_DURATION_S * HZ)
        for s in range(1, neutral_steps + 1):
            t = ease(s / neutral_steps)
            interp = [(fx + (nx - fx) * t, fy + (ny - fy) * t, fz + (nz - fz) * t)
                      for (fx, fy, fz), (nx, ny, nz) in zip(last_pos, NEUTRAL_POS)]
            self.iface.send(interp)
            time.sleep(DT)

        with self._lock:
            self.travel_x = 0.0
            self.rotate = 0.0
            self.target_speed = 0.0
            self.state = 'idle'
            self.zero_since = None

    def timeout_check(self):
        elapsed = (self.get_clock().now() - self.last_cmd).nanoseconds / 1e9
        if elapsed > CMD_TIMEOUT_S and self.state == 'moving':
            self.get_logger().info(f'Timeout ({CMD_TIMEOUT_S}s zonder nieuw cmd_vel)')
            self._do_stable_stop()
            return
        self._check_stop_debounce()

    def destroy_node(self):
        if self.state == 'moving':
            self._do_stable_stop()
        self.iface.destroy()
        super().destroy_node()


def main():
    _stop_app_muto()
    rclpy.init()
    node = PhoenixDriver()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
