import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
from typing import Optional
import json
import logging
from platform_client import PlatformClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gazebo Robot Control")

# Active WebSocket connections
active_connections: list[WebSocket] = []

# Platform client for robot communication
platform_client: Optional[PlatformClient] = None


@app.on_event("startup")
async def startup_event():
    """Initialize platform client on startup."""
    global platform_client

    # Get session credentials from environment
    # These are provided by the platform when launching the app
    session_id = os.getenv("SESSION_ID")
    session_token = os.getenv("SESSION_TOKEN")
    platform_url = os.getenv("PLATFORM_URL", "https://api.developers.remake.ai")

    if session_id and session_token:
        try:
            platform_client = PlatformClient(session_id, session_token, platform_url)

            # Register callbacks for robot data
            platform_client.on_pose_update(handle_pose_update)
            platform_client.on_laser_scan(handle_laser_scan)
            platform_client.on_battery_update(handle_battery_update)

            # Connect to platform
            success = await platform_client.connect()
            if success:
                logger.info("✓ Platform client connected successfully")
            else:
                logger.error("✗ Platform client connection failed")
                platform_client = None
        except Exception as e:
            logger.error(f"✗ Failed to initialize platform client: {e}")
            platform_client = None
    else:
        logger.warning("⚠ No session credentials - running in standalone mode (no robot connection)")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global platform_client
    if platform_client:
        await platform_client.disconnect()
        logger.info("Platform client disconnected")


@app.get("/health")
async def health_check():
    """Health check endpoint for platform."""
    return JSONResponse({
        "status": "ok",
        "platform_connected": platform_client is not None and platform_client.is_connected(),
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
        platform_connected = platform_client is not None and platform_client.is_connected()
        await websocket.send_json({
            "type": "status",
            "connected": True,
            "platform_connected": platform_connected,
            "message": "Connected to app" + (" and robot" if platform_connected else " (robot offline)")
        })

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
    """Handle commands from browser and relay to robot via platform."""
    if not platform_client or not platform_client.is_connected():
        await websocket.send_json({
            "type": "error",
            "message": "Not connected to robot"
        })
        return

    cmd_type = command.get("type")
    logger.info(f"Received command: {cmd_type}")

    try:
        if cmd_type == "move":
            # Send twist command to robot via platform
            linear_x = command.get("linear_x", 0.0)
            angular_z = command.get("angular_z", 0.0)
            success = await platform_client.send_twist_command(linear_x, angular_z)

            if success:
                await websocket.send_json({
                    "type": "command_sent",
                    "command": "move"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to send move command"
                })

        elif cmd_type == "stop":
            # Send stop command to robot via platform
            success = await platform_client.send_stop_command()

            if success:
                await websocket.send_json({
                    "type": "command_sent",
                    "command": "stop"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to send stop command"
                })

        elif cmd_type == "spin":
            # Spin is implemented as a timed angular velocity command
            angular_speed = command.get("angular_speed", 2.0)
            duration = command.get("duration", 5.0)

            # Send angular velocity
            success = await platform_client.send_twist_command(0.0, angular_speed)

            if success:
                await websocket.send_json({
                    "type": "command_sent",
                    "command": "spin",
                    "duration": duration
                })

                # Stop after duration
                await asyncio.sleep(duration)
                await platform_client.send_stop_command()
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to send spin command"
                })

        else:
            logger.warning(f"Unknown command type: {cmd_type}")
            await websocket.send_json({
                "type": "error",
                "message": f"Unknown command: {cmd_type}"
            })

    except Exception as e:
        logger.error(f"Error handling command: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


async def handle_pose_update(data: dict):
    """
    Handle pose updates from robot via platform.
    Forward to all connected browser clients.
    """
    message = {
        "type": "pose_update",
        "x": data.get("x", 0.0),
        "y": data.get("y", 0.0),
        "yaw": data.get("yaw", 0.0)
    }

    # Broadcast to all connected clients
    for websocket in active_connections:
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending pose update to client: {e}")


async def handle_laser_scan(data: dict):
    """
    Handle laser scan data from robot via platform.
    Forward to all connected browser clients.
    """
    message = {
        "type": "laser_scan",
        "ranges": data.get("ranges", []),
        "angle_min": data.get("angle_min", -3.14),
        "angle_max": data.get("angle_max", 3.14),
        "angle_increment": data.get("angle_increment", 0.0175)
    }

    # Broadcast to all connected clients
    for websocket in active_connections:
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending laser scan to client: {e}")


async def handle_battery_update(data: dict):
    """
    Handle battery updates from robot via platform.
    Forward to all connected browser clients.
    """
    message = {
        "type": "battery",
        "percentage": data.get("percentage", 0),
        "voltage": data.get("voltage", 0.0),
        "charging": data.get("charging", False)
    }

    # Broadcast to all connected clients
    for websocket in active_connections:
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending battery update to client: {e}")


# Mount static files (frontend)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
else:
    logger.warning(f"Frontend directory not found: {frontend_path}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
