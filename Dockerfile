# Use ROS2 Humble base image
FROM osrf/ros:humble-desktop

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy frontend code
COPY frontend/ ./frontend/

# Expose port
EXPOSE 8080

# Source ROS2 setup and run the app
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && python3 backend/main.py"]
