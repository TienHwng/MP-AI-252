let websocket;
const gateway = `ws://${window.location.hostname}/ws`;
const statusEl = document.getElementById('connection-status');

// Max points for the graphs
const MAX_POINTS = 20;

// Hardcoded realistic initial data to avoid empty graphs
let tempData = [25.1, 25.2, 25.3, 25.5, 25.6, 25.8, 25.9, 25.8, 25.7, 25.6, 25.5, 25.3, 25.2, 25.1, 25.0, 24.9, 24.8, 24.9, 25.0, 25.2];
let humiData = [58, 59, 60, 61, 62, 63, 64, 65, 64, 63, 62, 61, 60, 59, 58, 57, 56, 57, 58, 59];
let lightData = [310, 315, 320, 330, 340, 350, 360, 355, 345, 335, 325, 315, 305, 295, 285, 280, 290, 300, 310, 320];

document.addEventListener("DOMContentLoaded", () => {
    
    // 1. Sidebar & Tabs Management
    const menuBtn = document.getElementById('menuBtn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    const menuItems = document.querySelectorAll('.menu-item');
    const pages = document.querySelectorAll('.page');

    function toggleSidebar() {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('show');
    }

    menuBtn.addEventListener('click', toggleSidebar);
    overlay.addEventListener('click', toggleSidebar);

    menuItems.forEach(item => {
        item.addEventListener('click', function() {
            // Remove active class
            menuItems.forEach(i => i.classList.remove('active'));
            pages.forEach(p => p.classList.remove('active'));
            
            // Set active class
            this.classList.add('active');
            const targetId = this.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');

            // Hide sidebar on mobile after click
            if(window.innerWidth < 850) toggleSidebar();
        });
    });

    // 2. Control Buttons Logic
    const controlButtons = document.querySelectorAll('.control-btn');
    controlButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const isActive = this.classList.toggle('active');
            const statusText = this.querySelector('.status-text');
            if(statusText) statusText.textContent = isActive ? 'Active' : 'Inactive';

            const deviceId = this.getAttribute('data-id');
            const payload = { type: "control", device: deviceId, state: isActive };

            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify(payload));
            }
        });
    });

    // 3. Configuration Form Logic
    const configForm = document.getElementById('configForm');
    if(configForm) {
        configForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(e.target);
            const configValues = {};
            formData.forEach((value, key) => { configValues[key] = value; });

            const payload = { page: "setting", value: configValues };
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify(payload));
                alert("Configuration saved! Device will restart.");
            } else {
                alert("UI Offline Test Mode. Data captured: " + JSON.stringify(payload));
            }
        });
    }

    // Set Initial Values for UI Text
    document.getElementById('val_temp').textContent = tempData[tempData.length - 1];
    document.getElementById('val_humi').textContent = humiData[humiData.length - 1];
    document.getElementById('val_light').textContent = lightData[lightData.length - 1];

    // Initialize Charts & Websocket
    initCharts();
    initWebSocket();
});

// ================= CANVAS CHART DRAWING =================
function initCharts() {
    drawChart('tempChart', tempData, '#EF4444'); // Red
    drawChart('humiChart', humiData, '#3B82F6'); // Blue
    drawChart('lightChart', lightData, '#F59E0B'); // Orange
}

function updateChart(canvasId, dataArray, newValue, color) {
    if (dataArray.length >= MAX_POINTS) dataArray.shift();
    dataArray.push(newValue);
    drawChart(canvasId, dataArray, color);
}

function drawChart(canvasId, data, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || data.length === 0) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width; const h = canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.lineJoin = 'round';

    const min = Math.min(...data) * 0.9;
    const max = Math.max(...data) * 1.1;
    const range = (max - min) || 1;
    const stepX = w / (MAX_POINTS - 1);

    const startX = w - ((data.length - 1) * stepX);

    data.forEach((val, i) => {
        const x = startX + (i * stepX);
        const y = h - ((val - min) / range) * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
}

// ================= WEBSOCKET LOGIC =================
function initWebSocket() {
    websocket = new WebSocket(gateway);
    websocket.onopen = () => {
        statusEl.textContent = 'Device Connected';
        statusEl.className = 'status connected';
    };
    websocket.onclose = () => {
        statusEl.textContent = 'Offline (Test Mode)';
        statusEl.className = 'status disconnected';
    };
    websocket.onmessage = onMessage;
}

function onMessage(event) {
    try {
        const data = JSON.parse(event.data);
        
        // Populate Form
        if(data.type === "sys_info") {
            Object.keys(data).forEach(key => {
                const input = document.getElementById(key);
                if(input) input.value = data[key];
            });
        }

        // Update Sensors & Charts
        if(data.temp !== undefined) {
            document.getElementById('val_temp').textContent = data.temp;
            updateChart('tempChart', tempData, data.temp, '#EF4444');
        }
        if(data.humi !== undefined) {
            document.getElementById('val_humi').textContent = data.humi;
            updateChart('humiChart', humiData, data.humi, '#3B82F6');
        }
        if(data.light !== undefined) {
            document.getElementById('val_light').textContent = data.light;
            updateChart('lightChart', lightData, data.light, '#F59E0B');
        }
    } catch (e) {
        console.error("JSON Parse Error:", e);
    }
}