import asyncio
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from tf_transformations import euler_from_quaternion
import logging
from typing import Optional, Dict
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RobotControlNode(Node):
    """ROS2 node for robot control."""

    def __init__(self):
        super().__init__('gazebo_robot_control')

        # Publisher for velocity commands
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # Subscriber for odometry (robot pose)
        self.odom_sub = self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10
        )

        # Current pose
        self.current_pose = {
            "x": 0.0,
            "y": 0.0,
            "yaw": 0.0
        }

        # Spin task
        self.spin_task = None

        logger.info("RobotControlNode initialized")

    def odom_callback(self, msg: Odometry):
        """Callback for odometry updates."""
        # Extract position
        self.current_pose["x"] = msg.pose.pose.position.x
        self.current_pose["y"] = msg.pose.pose.position.y

        # Extract orientation (yaw from quaternion)
        orientation = msg.pose.pose.orientation
        quaternion = (
            orientation.x,
            orientation.y,
            orientation.z,
            orientation.w
        )
        euler = euler_from_quaternion(quaternion)
        self.current_pose["yaw"] = euler[2]  # yaw is the third element

    def send_velocity(self, linear_x: float, angular_z: float):
        """Send velocity command to robot."""
        twist = Twist()
        twist.linear.x = linear_x
        twist.angular.z = angular_z
        self.cmd_vel_pub.publish(twist)
        logger.info(f"Sent velocity: linear_x={linear_x}, angular_z={angular_z}")

    def stop_robot(self):
        """Stop the robot."""
        self.send_velocity(0.0, 0.0)

    async def spin_robot_async(self, angular_speed: float, duration: float):
        """Spin robot for specified duration."""
        logger.info(f"Spinning robot: {angular_speed} rad/s for {duration}s")

        # Cancel any existing spin task
        if self.spin_task and not self.spin_task.done():
            self.spin_task.cancel()

        # Start spinning
        self.send_velocity(0.0, angular_speed)

        # Wait for duration
        await asyncio.sleep(duration)

        # Stop spinning
        self.stop_robot()
        logger.info("Spin complete")


class ROS2Bridge:
    """Bridge between FastAPI and ROS2."""

    def __init__(self):
        self.node: Optional[RobotControlNode] = None
        self.executor = None
        self.spin_thread = None
        self._running = False

    async def start(self):
        """Initialize ROS2 node."""
        try:
            # Initialize rclpy if not already initialized
            if not rclpy.ok():
                rclpy.init()

            # Create node
            self.node = RobotControlNode()

            # Create executor
            self.executor = rclpy.executors.SingleThreadedExecutor()
            self.executor.add_node(self.node)

            # Start spinning in background thread
            self._running = True
            self.spin_thread = threading.Thread(target=self._spin_ros2, daemon=True)
            self.spin_thread.start()

            logger.info("ROS2 bridge started")

        except Exception as e:
            logger.error(f"Failed to start ROS2: {e}")
            raise

    def _spin_ros2(self):
        """Spin ROS2 in background thread."""
        while self._running and rclpy.ok():
            try:
                self.executor.spin_once(timeout_sec=0.1)
            except Exception as e:
                logger.error(f"Error in ROS2 spin: {e}")
                break

    async def stop(self):
        """Shutdown ROS2 node."""
        self._running = False

        if self.spin_thread:
            self.spin_thread.join(timeout=2.0)

        if self.node:
            self.node.stop_robot()
            self.node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()

        logger.info("ROS2 bridge stopped")

    def is_running(self) -> bool:
        """Check if ROS2 is running."""
        return self._running and self.node is not None

    async def send_velocity(self, linear_x: float, angular_z: float):
        """Send velocity command."""
        if not self.is_running():
            raise RuntimeError("ROS2 bridge not running")

        self.node.send_velocity(linear_x, angular_z)

    async def spin_robot(self, angular_speed: float, duration: float):
        """Spin robot for duration."""
        if not self.is_running():
            raise RuntimeError("ROS2 bridge not running")

        await self.node.spin_robot_async(angular_speed, duration)

    async def get_current_pose(self) -> Optional[Dict[str, float]]:
        """Get current robot pose."""
        if not self.is_running():
            return None

        return self.node.current_pose.copy()
