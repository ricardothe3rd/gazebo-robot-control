import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
from typing import Optional
import json
import logging

# Import ROS2 bridge
from ros2_bridge import ROS2Bridge

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gazebo Robot Control")

# ROS2 bridge instance
ros2_bridge: Optional[ROS2Bridge] = None

# Active WebSocket connections
active_connections: list[WebSocket] = []


@app.on_event("startup")
async def startup_event():
    """Initialize ROS2 bridge on startup."""
    global ros2_bridge
    try:
        ros2_bridge = ROS2Bridge()
        await ros2_bridge.start()
        logger.info("ROS2 bridge started successfully")
    except Exception as e:
        logger.error(f"Failed to start ROS2 bridge: {e}")
        ros2_bridge = None


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup ROS2 on shutdown."""
    global ros2_bridge
    if ros2_bridge:
        await ros2_bridge.stop()
        logger.info("ROS2 bridge stopped")


@app.get("/health")
async def health_check():
    """Health check endpoint for platform."""
    return JSONResponse({
        "status": "ok",
        "ros2_connected": ros2_bridge is not None and ros2_bridge.is_running(),
        "active_connections": len(active_connections)
    })


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for browser control."""
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"Client connected. Total connections: {len(active_connections)}")

    try:
        # Send initial status
        await websocket.send_json({
            "type": "status",
            "connected": ros2_bridge is not None and ros2_bridge.is_running()
        })

        # Start listening to ROS2 pose updates
        if ros2_bridge:
            asyncio.create_task(forward_pose_updates(websocket))

        # Handle incoming messages
        while True:
            data = await websocket.receive_text()
            try:
                command = json.loads(data)
                await handle_command(command, websocket)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {data}")
            except Exception as e:
                logger.error(f"Error handling command: {e}")

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        active_connections.remove(websocket)
        logger.info(f"Client removed. Total connections: {len(active_connections)}")


async def handle_command(command: dict, websocket: WebSocket):
    """Handle commands from browser."""
    if not ros2_bridge or not ros2_bridge.is_running():
        await websocket.send_json({
            "type": "error",
            "message": "ROS2 bridge not available"
        })
        return

    cmd_type = command.get("type")
    logger.info(f"Received command: {cmd_type}")

    try:
        if cmd_type == "move":
            # Move command with linear_x and angular_z
            linear_x = command.get("linear_x", 0.0)
            angular_z = command.get("angular_z", 0.0)
            await ros2_bridge.send_velocity(linear_x, angular_z)

        elif cmd_type == "stop":
            # Stop robot
            await ros2_bridge.send_velocity(0.0, 0.0)

        elif cmd_type == "spin":
            # Spin robot for duration
            angular_speed = command.get("angular_speed", 2.0)
            duration = command.get("duration", 5.0)
            await ros2_bridge.spin_robot(angular_speed, duration)

        else:
            logger.warning(f"Unknown command type: {cmd_type}")
            await websocket.send_json({
                "type": "error",
                "message": f"Unknown command: {cmd_type}"
            })

    except Exception as e:
        logger.error(f"Error executing command: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


async def forward_pose_updates(websocket: WebSocket):
    """Forward robot pose updates from ROS2 to browser."""
    if not ros2_bridge:
        return

    try:
        while True:
            pose = await ros2_bridge.get_current_pose()
            if pose:
                await websocket.send_json({
                    "type": "pose_update",
                    "x": pose["x"],
                    "y": pose["y"],
                    "yaw": pose["yaw"]
                })
            await asyncio.sleep(0.5)  # Update every 500ms
    except Exception as e:
        logger.error(f"Error forwarding pose updates: {e}")


# Mount static files (frontend)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
else:
    logger.warning(f"Frontend directory not found: {frontend_path}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
