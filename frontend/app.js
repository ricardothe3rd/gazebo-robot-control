// WebSocket connection
let ws = null;
let currentSpeed = 0.5;
let currentRotation = 0;

// DOM elements
const statusEl = document.getElementById('connection-status');
const statusTextEl = document.getElementById('status-text');
const robot = document.getElementById('robot');
const speedSlider = document.getElementById('speed-slider');
const speedValueEl = document.getElementById('speed-value');

// Control buttons
const forwardBtn = document.getElementById('forward-btn');
const backwardBtn = document.getElementById('backward-btn');
const leftBtn = document.getElementById('left-btn');
const rightBtn = document.getElementById('right-btn');
const stopBtn = document.getElementById('stop-btn');
const spinBtn = document.getElementById('spin-btn');

// Get WebSocket URL from window location
function getWebSocketUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/ws`;
}

// Connect to backend WebSocket
function connectToBackend() {
    const wsUrl = getWebSocketUrl();
    console.log('Connecting to:', wsUrl);

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('Connected to backend');
        statusTextEl.textContent = 'Robot Ready';
        statusEl.classList.add('connected');
        enableControls();
    };

    ws.onclose = () => {
        console.log('Disconnected from backend');
        statusTextEl.textContent = 'Disconnected';
        statusEl.classList.remove('connected');
        disableControls();
        // Try to reconnect after 3 seconds
        setTimeout(connectToBackend, 3000);
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleServerMessage(data);
        } catch (err) {
            console.error('Error parsing message:', err);
        }
    };
}

// Handle messages from server
function handleServerMessage(data) {
    console.log('Received from server:', data);

    if (data.type === 'pose_update') {
        // Update robot visual orientation
        if (data.yaw !== undefined) {
            // Convert radians to degrees (yaw is in radians from ROS2)
            currentRotation = data.yaw * (180 / Math.PI);
            robot.style.transform = `rotate(${currentRotation}deg)`;
        }
    }
}

// Send command to robot
function sendCommand(type, params = {}) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        const command = {
            type: type,
            ...params
        };
        ws.send(JSON.stringify(command));
        console.log('Sent command:', command);
    } else {
        console.warn('WebSocket not connected');
    }
}

// Movement commands
function moveForward() {
    sendCommand('move', {
        linear_x: currentSpeed,
        angular_z: 0
    });
}

function moveBackward() {
    sendCommand('move', {
        linear_x: -currentSpeed,
        angular_z: 0
    });
}

function turnLeft() {
    sendCommand('move', {
        linear_x: 0,
        angular_z: 1.0 // rad/s
    });
}

function turnRight() {
    sendCommand('move', {
        linear_x: 0,
        angular_z: -1.0 // rad/s
    });
}

function stopRobot() {
    sendCommand('stop');
}

function spinRobot() {
    // Random duration between 6-10 seconds
    const duration = 6 + Math.random() * 4;

    // Random direction
    const direction = Math.random() > 0.5 ? 1 : -1;
    const angularSpeed = 2.0 * direction;

    sendCommand('spin', {
        angular_speed: angularSpeed,
        duration: duration
    });

    // Animate the UI robot too
    animateSpin(duration, direction);
}

// Animate UI robot spinning
function animateSpin(duration, direction) {
    const startTime = performance.now();
    const durationMs = duration * 1000;
    const ROBOT_SPEED_DEG_PER_FRAME = (114.6 * 0.3) / 60;
    const FULL_SPEED_RATIO = 0.8;
    const fullSpeedDuration = durationMs * FULL_SPEED_RATIO;
    const decelDuration = durationMs * (1 - FULL_SPEED_RATIO);

    spinBtn.disabled = true;

    function animate(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / durationMs, 1);

        let speed;
        if (elapsed < fullSpeedDuration) {
            // Phase 1: Full speed
            speed = ROBOT_SPEED_DEG_PER_FRAME;
        } else {
            // Phase 2: Deceleration
            const decelElapsed = elapsed - fullSpeedDuration;
            const decelProgress = decelElapsed / decelDuration;
            speed = ROBOT_SPEED_DEG_PER_FRAME * (1 - Math.pow(decelProgress, 2));
        }

        currentRotation += speed * (-direction);
        robot.style.transform = `rotate(${currentRotation}deg)`;

        if (progress < 1) {
            requestAnimationFrame(animate);
        } else {
            spinBtn.disabled = false;
        }
    }

    requestAnimationFrame(animate);
}

// Speed slider handler
speedSlider.addEventListener('input', (e) => {
    currentSpeed = parseFloat(e.target.value);
    speedValueEl.textContent = currentSpeed.toFixed(1);
});

// Button event listeners
forwardBtn.addEventListener('mousedown', moveForward);
forwardBtn.addEventListener('mouseup', stopRobot);
forwardBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    moveForward();
});
forwardBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    stopRobot();
});

backwardBtn.addEventListener('mousedown', moveBackward);
backwardBtn.addEventListener('mouseup', stopRobot);
backwardBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    moveBackward();
});
backwardBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    stopRobot();
});

leftBtn.addEventListener('mousedown', turnLeft);
leftBtn.addEventListener('mouseup', stopRobot);
leftBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    turnLeft();
});
leftBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    stopRobot();
});

rightBtn.addEventListener('mousedown', turnRight);
rightBtn.addEventListener('mouseup', stopRobot);
rightBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    turnRight();
});
rightBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    stopRobot();
});

stopBtn.addEventListener('click', stopRobot);
spinBtn.addEventListener('click', spinRobot);

// Enable/disable controls
function enableControls() {
    forwardBtn.disabled = false;
    backwardBtn.disabled = false;
    leftBtn.disabled = false;
    rightBtn.disabled = false;
    stopBtn.disabled = false;
    spinBtn.disabled = false;
    speedSlider.disabled = false;
}

function disableControls() {
    forwardBtn.disabled = true;
    backwardBtn.disabled = true;
    leftBtn.disabled = true;
    rightBtn.disabled = true;
    stopBtn.disabled = true;
    spinBtn.disabled = true;
    speedSlider.disabled = true;
}

// Connect on page load
disableControls();
connectToBackend();
