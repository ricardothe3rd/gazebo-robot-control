import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
from typing import Optional
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gazebo Robot Control")

# Active WebSocket connections
active_connections: list[WebSocket] = []

# TODO: Add platform WebSocket client here to connect to developers.remake.ai
# The robot runs locally with ROS2, this app relays commands through the platform


@app.get("/health")
async def health_check():
    """Health check endpoint for platform."""
    return JSONResponse({
        "status": "ok",
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
            "connected": True,
            "message": "Connected to Gazebo Robot Control App"
        })

        # TODO: Connect to platform WebSocket client here
        # Platform will relay commands to robot running locally with ROS2

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
    cmd_type = command.get("type")
    logger.info(f"Received command: {cmd_type} - {command}")

    # TODO: Send commands to platform WebSocket client, which will relay to robot
    # For now, just acknowledge receipt

    try:
        if cmd_type == "move":
            linear_x = command.get("linear_x", 0.0)
            angular_z = command.get("angular_z", 0.0)
            logger.info(f"Move command: linear={linear_x}, angular={angular_z}")
            await websocket.send_json({
                "type": "command_received",
                "command": cmd_type,
                "message": f"Move command received (linear={linear_x}, angular={angular_z})"
            })

        elif cmd_type == "stop":
            logger.info("Stop command")
            await websocket.send_json({
                "type": "command_received",
                "command": cmd_type,
                "message": "Stop command received"
            })

        elif cmd_type == "spin":
            angular_speed = command.get("angular_speed", 2.0)
            duration = command.get("duration", 5.0)
            logger.info(f"Spin command: speed={angular_speed}, duration={duration}")
            await websocket.send_json({
                "type": "command_received",
                "command": cmd_type,
                "message": f"Spin command received (speed={angular_speed}, duration={duration})"
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


# TODO: Implement pose updates from platform WebSocket client
# Robot will send pose data through platform, app will forward to browser


# Mount static files (frontend)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
else:
    logger.warning(f"Frontend directory not found: {frontend_path}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
