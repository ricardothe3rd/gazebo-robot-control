"""
Platform WebSocket Client - Connects to developers.remake.ai for robot command relay

This module provides the communication layer between the deployed app and the robot
running locally with ROS2. Commands flow through the platform's Socket.IO namespace.
"""

import socketio
import asyncio
import logging
import os
from typing import Optional, Callable, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlatformClient:
    """
    Client for connecting to developers.remake.ai Socket.IO namespace.

    Architecture:
    - Browser → App WebSocket → Platform Socket.IO → Robot (kaiaai)
    - Robot → Platform Socket.IO → App WebSocket → Browser

    Handles:
    - Connection to /sessions/{sessionId}/robot namespace
    - Authentication with session token
    - Sending robot commands (move, stop, spin)
    - Receiving robot data (pose, laser scan, etc.)
    """

    def __init__(self, session_id: str, session_token: str, platform_url: str = None):
        """
        Initialize the platform client.

        Args:
            session_id: Session ID from platform
            session_token: Session token for authentication
            platform_url: Base URL of platform API (defaults to PLATFORM_URL env var)
        """
        self.session_id = session_id
        self.session_token = session_token
        self.platform_url = platform_url or os.getenv('PLATFORM_URL', 'https://api.developers.remake.ai')
        self.namespace = f'/sessions/{session_id}/robot'

        # Socket.IO client
        self.sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_delay=1,
            reconnection_delay_max=5,
            reconnection_attempts=5
        )

        # Callbacks for robot data
        self.pose_callback: Optional[Callable] = None
        self.laser_scan_callback: Optional[Callable] = None
        self.battery_callback: Optional[Callable] = None

        # Track connection state
        self._connected = False

        logger.info(f"[PlatformClient] Initialized for session {session_id}")

    async def connect(self) -> bool:
        """
        Connect to platform Socket.IO namespace.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Event to signal when server confirms connection
            connection_confirmed = asyncio.Event()

            # Register event handlers BEFORE connecting
            @self.sio.event(namespace=self.namespace)
            async def connected(data=None):
                """Called when connected to platform namespace"""
                self._connected = True
                logger.info(f"[PlatformClient] Connected to platform session {self.session_id}")
                connection_confirmed.set()

            @self.sio.event(namespace=self.namespace)
            async def robot_pose(data):
                """Called when robot sends pose update"""
                logger.debug(f"[PlatformClient] Received robot_pose: x={data.get('x')}, y={data.get('y')}")
                if self.pose_callback:
                    await self.pose_callback(data)

            @self.sio.event(namespace=self.namespace)
            async def laser_scan(data):
                """Called when robot sends laser scan data"""
                logger.debug(f"[PlatformClient] Received laser_scan")
                if self.laser_scan_callback:
                    await self.laser_scan_callback(data)

            @self.sio.event(namespace=self.namespace)
            async def battery(data):
                """Called when robot sends battery update"""
                logger.debug(f"[PlatformClient] Received battery: {data.get('percentage')}%")
                if self.battery_callback:
                    await self.battery_callback(data)

            @self.sio.event(namespace=self.namespace)
            async def disconnect():
                """Called when disconnected from platform"""
                self._connected = False
                logger.warning(f"[PlatformClient] Disconnected from platform session {self.session_id}")

            # Connect to platform with authentication
            logger.info(f"[PlatformClient] Connecting to {self.platform_url}{self.namespace}")
            await self.sio.connect(
                self.platform_url,
                namespaces=[self.namespace],
                auth={'token': self.session_token},
                wait_timeout=10
            )

            # Wait for server to confirm connection (max 10 seconds)
            try:
                await asyncio.wait_for(connection_confirmed.wait(), timeout=10.0)
                logger.info(f"[PlatformClient] Connection confirmed, ready to send commands")
                return True
            except asyncio.TimeoutError:
                logger.error(f"[PlatformClient] Server did not confirm connection within 10 seconds")
                return False

        except Exception as e:
            logger.error(f"[PlatformClient] Connection failed: {e}")
            self._connected = False
            return False

    async def send_twist_command(self, linear_x: float, angular_z: float) -> bool:
        """
        Send twist (velocity) command to robot via platform.

        Args:
            linear_x: Forward/backward velocity (m/s)
            angular_z: Rotation velocity (rad/s)

        Returns:
            True if sent successfully
        """
        if not self._connected:
            logger.warning("[PlatformClient] Cannot send twist - not connected")
            return False

        try:
            await self.sio.emit('twist_command', {
                'linear_x': linear_x,
                'angular_z': angular_z
            }, namespace=self.namespace)
            logger.info(f"[PlatformClient] Sent twist_command: linear={linear_x}, angular={angular_z}")
            return True
        except Exception as e:
            logger.error(f"[PlatformClient] Failed to send twist: {e}")
            return False

    async def send_stop_command(self) -> bool:
        """
        Send stop command to robot (twist with zero velocities).

        Returns:
            True if sent successfully
        """
        return await self.send_twist_command(0.0, 0.0)

    async def send_navigate_command(self, x: float, y: float, yaw: float = 0.0, relative: bool = True) -> bool:
        """
        Send navigation command to robot via platform.

        Args:
            x: X position (meters)
            y: Y position (meters)
            yaw: Rotation in radians
            relative: If True, move relative to current position

        Returns:
            True if sent successfully
        """
        if not self._connected:
            logger.warning("[PlatformClient] Cannot send navigate - not connected")
            return False

        try:
            await self.sio.emit('navigate_cmd', {
                'x': x,
                'y': y,
                'yaw': yaw,
                'relative': relative
            }, namespace=self.namespace)
            logger.info(f"[PlatformClient] Sent navigate_cmd: x={x}, y={y}, yaw={yaw}")
            return True
        except Exception as e:
            logger.error(f"[PlatformClient] Failed to send navigate: {e}")
            return False

    def on_pose_update(self, callback: Callable) -> None:
        """
        Register callback for robot pose updates.

        Args:
            callback: Async function that takes (data: dict) with x, y, yaw
        """
        self.pose_callback = callback
        logger.info("[PlatformClient] Pose callback registered")

    def on_laser_scan(self, callback: Callable) -> None:
        """
        Register callback for laser scan data.

        Args:
            callback: Async function that takes (data: dict) with ranges array
        """
        self.laser_scan_callback = callback
        logger.info("[PlatformClient] Laser scan callback registered")

    def on_battery_update(self, callback: Callable) -> None:
        """
        Register callback for battery updates.

        Args:
            callback: Async function that takes (data: dict) with percentage
        """
        self.battery_callback = callback
        logger.info("[PlatformClient] Battery callback registered")

    async def disconnect(self) -> None:
        """Disconnect from platform namespace."""
        try:
            await self.sio.disconnect()
            self._connected = False
            logger.info("[PlatformClient] Disconnected from platform")
        except Exception as e:
            logger.error(f"[PlatformClient] Error during disconnect: {e}")

    def is_connected(self) -> bool:
        """Check if currently connected to platform."""
        return self._connected
