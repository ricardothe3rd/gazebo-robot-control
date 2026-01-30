# Gazebo Robot Control App

A web-based robot control interface for controlling a robot in Gazebo simulation via ROS2.

## Features

- **Real-time Control**: Control robot movement with directional buttons
- **Speed Control**: Adjustable speed slider (0.1 - 1.0 m/s)
- **Spin Function**: Make the robot spin like a wheel of fortune
- **Live Feedback**: Real-time robot pose visualization
- **WebSocket Communication**: Low-latency control via WebSocket

## Architecture

```
Web Browser (Frontend)
    ↕ WebSocket
FastAPI Backend
    ↕ ROS2 Topics
Gazebo Simulation
```

## Prerequisites

- ROS2 Humble
- Python 3.10+
- Gazebo with a robot configured

## Local Development

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the App

```bash
# Source ROS2
source /opt/ros/humble/setup.bash

# Run backend
python backend/main.py
```

Open browser at `http://localhost:8080`

## Deploy to Remake Platform

### 1. Create Git Repository

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

### 2. Deploy via Platform

```bash
# Create app
remake apps create gazebo-robot-control

# Deploy from git
remake deploy --app gazebo-robot-control --git-url <your-repo-url>
```

## ROS2 Topics

- **Publishes to:** `/cmd_vel` (geometry_msgs/Twist)
- **Subscribes to:** `/odom` (nav_msgs/Odometry)

## Environment Variables

- `PORT`: Server port (default: 8080)

## Controls

- **Arrow Buttons**: Move forward/backward/left/right
- **STOP Button**: Emergency stop
- **SPIN Button**: Spin the robot (6-10 seconds, random direction)
- **Speed Slider**: Adjust movement speed

## License

MIT
