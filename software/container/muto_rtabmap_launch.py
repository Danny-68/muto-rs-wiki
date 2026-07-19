import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess, TimerAction

def generate_launch_description():
    cam_remappings = [
        ("rgb/image", "/camera/color/image_raw"),
        ("rgb/camera_info", "/camera/color/camera_info"),
        ("depth/image", "/camera/depth/image_raw"),
    ]
    icp_odometry = Node(
        package="rtabmap_odom", executable="icp_odometry", output="screen",
        parameters=[{"frame_id": "base_link", "odom_frame_id": "odom",
            "publish_tf": True, "use_sim_time": False,
            "Reg/Force3DoF": "true", "Icp/VoxelSize": "0.1",
            "Icp/MaxCorrespondenceDistance": "0.5"}],
        remappings=[("scan", "/scan")])
    rgbd_sync = Node(
        package="rtabmap_sync", executable="rgbd_sync", output="screen",
        parameters=[{"approx_sync": True, "use_sim_time": False, "approx_sync_max_interval": 0.05}],
        remappings=cam_remappings)
    rtabmap_node = Node(
        package="rtabmap_slam", executable="rtabmap", output="screen",
        parameters=[{"use_sim_time": False, "subscribe_rgbd": True,
            "subscribe_scan": True, "subscribe_odom": True,
            "frame_id": "base_link", "map_frame_id": "map",
            "odom_frame_id": "odom", "publish_tf": False,
            "Reg/Force3DoF": "true", "Grid/3D": "false",
            "Grid/RayTracing": "true", "Grid/RangeMin": "0.2",
            "Grid/RangeMax": "3.5", "Grid/Sensor": "2",
            "RGBD/LinearUpdate": "0.05", "RGBD/AngularUpdate": "0.05",
            "database_path": "/root/rtabmap.db",
            "Vis/MinInliers": "5",
            "Reg/Strategy": "1",
            "Icp/CorrespondenceRatio": "0.2",
            "RGBD/LoopClosureReactivationRatio": "0.1"}],
        remappings=[("scan", "/scan"), ("odom", "/odom")],
        arguments=["-d"])
    odom_tf = Node(package="tf2_ros", executable="static_transform_publisher",
        arguments=["0","0","0","0","0","0","1","odom","base_link"])
    camera_tf = Node(package="tf2_ros", executable="static_transform_publisher",
        arguments=["0.05","0","0.10","0","0","0","1","base_link","camera_link"])
    camera_color_tf = Node(package="tf2_ros", executable="static_transform_publisher",
        arguments=["-0.002","0.025","0.0","0.0","0.0","0.0","1.0","camera_link","camera_color_frame"])
    camera_optical_tf = Node(package="tf2_ros", executable="static_transform_publisher",
        arguments=["0","0","0","-0.5","0.5","-0.5","0.5","camera_color_frame","camera_color_optical_frame"])
    depth_tf = Node(package="tf2_ros", executable="static_transform_publisher",
        arguments=["0","0","0","0","0","0","1","camera_link","camera_depth_frame"])
    depth_optical_tf = Node(package="tf2_ros", executable="static_transform_publisher",
        arguments=["0","0","0","-0.5","0.5","-0.5","0.5","camera_depth_frame","camera_depth_optical_frame"])
    laser_tf = Node(package="tf2_ros", executable="static_transform_publisher",
        arguments=["0","0","0.02","0","0","0","1","base_link","laser"])
    disable_cam_tf = TimerAction(period=5.0, actions=[ExecuteProcess(
        cmd=["ros2","param","set","/camera/camera","publish_tf","false"])])
    return LaunchDescription([odom_tf, camera_tf, camera_color_tf, camera_optical_tf,
        depth_tf, depth_optical_tf, laser_tf, disable_cam_tf,
        icp_odometry, rgbd_sync, rtabmap_node])
