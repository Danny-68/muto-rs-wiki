#!/usr/bin/env python3
"""
Consumeert /pose_settling: wacht tot de pose-naslinger voorbij is voordat een
NavigateToPose-doel wordt verstuurd. Doel wordt relatief opgegeven (afstand
recht vooruit t.o.v. de huidige AMCL-pose), zodat oriëntatiefouten in het
doel zelf (zoals bij de eerdere test, deuropening-rechts-doel-rechtdoor)
zoveel mogelijk worden vermeden.
"""
import sys
import time
import math
import subprocess
import re

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import Bool
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav2_msgs.action import NavigateToPose


def get_amcl_pose_polled():
    """/amcl_pose publiceert alleen bij updates, geen continue stream -- een
    verse rclpy-subscriber mist het laatste bericht (bekende valkuil, zie
    PROBLEMS.md). One-shot poll i.p.v. live subscriptie."""
    out = subprocess.run(
        ["bash", "-c",
         "source /opt/ros/humble/setup.bash && timeout 4 ros2 topic echo /amcl_pose --once 2>/dev/null"],
        capture_output=True, text=True, timeout=10).stdout
    if not out.strip():
        return None
    xs = re.findall(r"x:\s*(-?[\d.eE+-]+)", out)
    ys = re.findall(r"y:\s*(-?[\d.eE+-]+)", out)
    zs = re.findall(r"z:\s*(-?[\d.eE+-]+)", out)
    ws = re.findall(r"w:\s*(-?[\d.eE+-]+)", out)
    x = float(xs[0])
    y = float(ys[0])
    qz = float(zs[1])   # zs[0]=position.z, zs[1]=orientation.z
    qw = float(ws[0])
    yaw = 2.0 * math.atan2(qz, qw)
    return x, y, yaw


def yaw_from_quat(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def quat_from_yaw(yaw):
    return math.sin(yaw / 2.0), math.cos(yaw / 2.0)  # (z, w)


class GuardedNavigate(Node):
    def __init__(self, distance_m):
        super().__init__('guarded_navigate_test')
        self.distance_m = distance_m
        self.settling = None
        self.amcl_pose = None
        self.create_subscription(Bool, 'pose_settling', self._settling_cb, 10)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def _settling_cb(self, msg):
        self.settling = msg.data

    def wait_for_settled(self, timeout_s=60.0):
        print("[guarded_nav] wachten tot pose_settling=false...")
        t0 = time.time()
        while rclpy.ok() and (time.time() - t0) < timeout_s:
            rclpy.spin_once(self, timeout_sec=0.5)
            if self.settling is False:
                print(f"[guarded_nav] settled na {time.time()-t0:.1f}s")
                return True
            elif self.settling is True:
                print(f"[guarded_nav] t={time.time()-t0:.1f}s -- nog aan het naslingeren...")
        print("[guarded_nav] TIMEOUT wachten op settling=false")
        return False

    def wait_for_amcl_pose(self, timeout_s=10.0):
        t0 = time.time()
        while rclpy.ok() and (time.time() - t0) < timeout_s:
            pose = get_amcl_pose_polled()
            if pose is not None:
                self.amcl_pose = pose
                return True
            time.sleep(1.0)
        return False

    def send_forward_goal(self):
        x0, y0, yaw = self.amcl_pose
        gx = x0 + self.distance_m * math.cos(yaw)
        gy = y0 + self.distance_m * math.sin(yaw)
        gz, gw = quat_from_yaw(yaw)

        print(f"[guarded_nav] huidige pose: x={x0:.2f} y={y0:.2f} yaw={math.degrees(yaw):.1f}deg")
        print(f"[guarded_nav] doel ({self.distance_m}m recht vooruit): x={gx:.2f} y={gy:.2f}")

        if not self.client.wait_for_server(timeout_sec=10.0):
            print("[guarded_nav] FOUT: navigate_to_pose actionserver niet bereikbaar")
            return False

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = gx
        goal.pose.pose.position.y = gy
        goal.pose.pose.orientation.z = gz
        goal.pose.pose.orientation.w = gw

        print("[guarded_nav] doel versturen...")
        future = self.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future, timeout_sec=15.0)
        handle = future.result()
        if handle is None or not handle.accepted:
            print("[guarded_nav] FOUT: doel niet geaccepteerd")
            return False

        result_future = handle.get_result_async()
        print("[guarded_nav] wachten op resultaat...")
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=90.0)
        result = result_future.result()
        if result is None:
            print("[guarded_nav] TIMEOUT op resultaat")
            return False
        print(f"[guarded_nav] status={result.status}  (4=SUCCEEDED)")
        return result.status == 4


def main():
    distance_m = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    rclpy.init()
    node = GuardedNavigate(distance_m)

    if not node.wait_for_settled():
        print("[guarded_nav] afgebroken: pose kwam niet tot rust")
        node.destroy_node(); rclpy.shutdown(); return

    if not node.wait_for_amcl_pose():
        print("[guarded_nav] FOUT: geen /amcl_pose ontvangen")
        node.destroy_node(); rclpy.shutdown(); return

    node.send_forward_goal()

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
