let websocket;
let reconnectTimer;

const gateway = getWebSocketGateway();
const statusEl = document.getElementById("connection-status");

const CONFIG_ALIASES = {
	wifi_ssid: ["wifi_ssid", "ssid", "WIFI_SSID"],
	wifi_pass: ["wifi_pass", "password", "WIFI_PASS"],
	mqtt_broker: ["mqtt_broker", "mqtt_server", "broker", "CORE_IOT_SERVER"],
	mqtt_port: ["mqtt_port", "port", "CORE_IOT_PORT"],
	sys_token: ["sys_token", "token", "coreIOT_Token", "CORE_IOT_TOKEN"],
};

document.addEventListener("DOMContentLoaded", () => {
	const configForm = document.getElementById("configForm");
	if (configForm) {
		configForm.addEventListener("submit", function (event) {
			event.preventDefault();

			const configValues = Object.fromEntries(new FormData(event.target).entries());
			if (configValues.mqtt_port) {
				configValues.mqtt_port = Number(configValues.mqtt_port);
			}

			const payload = {
				type: "setting",
				page: "setting",
				value: configValues,
			};

			if (sendPayload(payload)) {
				alert("Configuration sent. Device will save and restart.");
			} else {
				alert("Offline Test Mode. Data captured: " + JSON.stringify(payload));
			}
		});
	}

	initWebSocket();
});

function getWebSocketGateway() {
	if (!window.location.host) return null;

	const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
	return `${protocol}//${window.location.host}/ws`;
}

function setConnectionStatus(text, state) {
	if (!statusEl) return;
	statusEl.textContent = text;
	statusEl.className = `status ${state}`;
}

function sendPayload(payload) {
	if (websocket && websocket.readyState === WebSocket.OPEN) {
		websocket.send(JSON.stringify(payload));
		return true;
	}

	console.info("[BoardHost] Payload captured without WebSocket:", payload);
	return false;
}

function initWebSocket() {
	if (!gateway) {
		setConnectionStatus("Offline (Local Preview)", "disconnected");
		return;
	}

	clearTimeout(reconnectTimer);
	websocket = new WebSocket(gateway);

	websocket.onopen = () => {
		setConnectionStatus("Device Connected", "connected");
	};

	websocket.onclose = () => {
		setConnectionStatus("Offline (Test Mode)", "disconnected");
		reconnectTimer = setTimeout(initWebSocket, 3000);
	};

	websocket.onerror = () => {
		setConnectionStatus("Connection Error", "disconnected");
	};

	websocket.onmessage = onMessage;
}

function onMessage(event) {
	try {
		const data = JSON.parse(event.data);

		if (data.type === "sys_info" || data.type === "settings" || data.page === "setting") {
			populateForm(data.value || data);
		}
	} catch (error) {
		console.error("[BoardHost] JSON parse error:", error);
	}
}

function populateForm(source) {
	Object.entries(CONFIG_ALIASES).forEach(([inputId, aliases]) => {
		const input = document.getElementById(inputId);
		if (!input) return;

		for (const alias of aliases) {
			const value = valueAtPath(source, alias);
			if (value !== undefined && value !== null) {
				input.value = value;
				return;
			}
		}
	});
}

function valueAtPath(source, path) {
	if (!source || !path) return undefined;

	return path.split(".").reduce((current, key) => {
		if (current && Object.prototype.hasOwnProperty.call(current, key)) {
			return current[key];
		}
		return undefined;
	}, source);
}
