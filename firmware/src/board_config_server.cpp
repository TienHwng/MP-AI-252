#include "board_config_server.h"

#include "global.h"

#include <ArduinoJson.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <WiFi.h>

#ifndef BOARD_CONFIG_AP_SSID
#define BOARD_CONFIG_AP_SSID "HERA-Board-Config"
#endif

#ifndef BOARD_CONFIG_AP_PASS
#define BOARD_CONFIG_AP_PASS "12345678"
#endif

namespace {
constexpr uint16_t WEB_PORT = 80;
constexpr char PREF_NAMESPACE[] = "hera_cfg";
constexpr char WS_PATH[] = "/ws";

AsyncWebServer server(WEB_PORT);
AsyncWebSocket ws(WS_PATH);
Preferences prefs;
bool serverStarted = false;
unsigned long restartAtMs = 0;

String jsonString(const JsonVariantConst value, const String &fallback = "") {
	if (value.isNull()) {
		return fallback;
	}

	String result = value.as<String>();
	result.trim();
	return result.length() > 0 ? result : fallback;
}

uint16_t jsonPort(const JsonVariantConst value, const String &fallback) {
	if (value.is<int>()) {
		int port = value.as<int>();
		if (port > 0 && port <= 65535) {
			return static_cast<uint16_t>(port);
		}
	}

	String portString = jsonString(value, fallback);
	int port = portString.toInt();
	if (port > 0 && port <= 65535) {
		return static_cast<uint16_t>(port);
	}

	return 1883;
}

void sendCurrentConfig(AsyncWebSocketClient *client) {
	StaticJsonDocument<384> doc;
	doc["type"] = "sys_info";
	doc["wifi_ssid"] = WIFI_SSID;
	doc["wifi_pass"] = WIFI_PASS;
	doc["mqtt_broker"] = CORE_IOT_SERVER;
	doc["mqtt_port"] = CORE_IOT_PORT.toInt();
	doc["sys_token"] = CORE_IOT_TOKEN;

	String payload;
	serializeJson(doc, payload);

	if (client != nullptr) {
		client->text(payload);
	} else {
		ws.textAll(payload);
	}
}

void sendAck(AsyncWebSocketClient *client, bool ok, const char *message) {
	StaticJsonDocument<192> doc;
	doc["type"] = "setting_ack";
	doc["ok"] = ok;
	doc["message"] = message;

	String payload;
	serializeJson(doc, payload);

	if (client != nullptr) {
		client->text(payload);
	}
}

void applySettingPayload(JsonVariantConst root, AsyncWebSocketClient *client) {
	JsonVariantConst value = root["value"].is<JsonObjectConst>() ? root["value"] : root;

	WIFI_SSID = jsonString(value["wifi_ssid"], WIFI_SSID);
	WIFI_PASS = jsonString(value["wifi_pass"], WIFI_PASS);
	CORE_IOT_SERVER = jsonString(value["mqtt_broker"], CORE_IOT_SERVER);
	CORE_IOT_PORT = String(jsonPort(value["mqtt_port"], CORE_IOT_PORT));
	CORE_IOT_TOKEN = jsonString(value["sys_token"], CORE_IOT_TOKEN);

	save_board_config_to_storage();

	Serial.println("[BOARD CONFIG] Updated from web payload:");
	Serial.println("  WIFI_SSID=" + WIFI_SSID);
	Serial.println("  MQTT_SERVER=" + CORE_IOT_SERVER);
	Serial.println("  MQTT_PORT=" + CORE_IOT_PORT);

	sendAck(client, true, "Configuration saved");
	sendCurrentConfig(client);
	restartAtMs = millis() + 1500;
}

void handleTextMessage(AsyncWebSocketClient *client, const uint8_t *data, size_t len) {
	StaticJsonDocument<768> doc;
	DeserializationError error = deserializeJson(doc, data, len);

	if (error) {
		Serial.print("[BOARD CONFIG] Invalid JSON: ");
		Serial.println(error.c_str());
		sendAck(client, false, "Invalid JSON");
		return;
	}

	const String type = doc["type"].as<String>();
	const String page = doc["page"].as<String>();

	if (type == "setting" || page == "setting") {
		applySettingPayload(doc.as<JsonVariantConst>(), client);
		return;
	}

	sendAck(client, false, "Unsupported payload type");
}

void onWsEvent(
	AsyncWebSocket *server,
	AsyncWebSocketClient *client,
	AwsEventType type,
	void *arg,
	uint8_t *data,
	size_t len
) {
	(void)server;

	if (type == WS_EVT_CONNECT) {
		Serial.printf("[BOARD CONFIG] WebSocket client #%u connected\n", client->id());
		sendCurrentConfig(client);
		return;
	}

	if (type == WS_EVT_DISCONNECT) {
		Serial.printf("[BOARD CONFIG] WebSocket client #%u disconnected\n", client->id());
		return;
	}

	if (type != WS_EVT_DATA) {
		return;
	}

	AwsFrameInfo *info = static_cast<AwsFrameInfo *>(arg);
	if (info->opcode != WS_TEXT || info->final == 0 || info->index != 0 || info->len != len) {
		sendAck(client, false, "Only single-frame text JSON is supported");
		return;
	}

	handleTextMessage(client, data, len);
}

void startAccessPoint() {
	WiFi.mode(WIFI_AP_STA);
	WiFi.softAP(BOARD_CONFIG_AP_SSID, BOARD_CONFIG_AP_PASS);

	Serial.print("[BOARD CONFIG] AP SSID: ");
	Serial.println(BOARD_CONFIG_AP_SSID);
	Serial.print("[BOARD CONFIG] AP IP: ");
	Serial.println(WiFi.softAPIP());
}

void startHttpServer() {
	if (serverStarted) {
		return;
	}

	if (LittleFS.begin(true)) {
		server.serveStatic("/", LittleFS, "/").setDefaultFile("index.html");
	} else {
		Serial.println("[BOARD CONFIG] LittleFS mount failed; serving text fallback only");
	}

	server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
		if (LittleFS.exists("/index.html")) {
			request->send(LittleFS, "/index.html", "text/html");
			return;
		}

		request->send(
			200,
			"text/plain",
			"H.E.R.A board config server is running. Upload firmware/data files to LittleFS."
		);
	});

	server.on("/config", HTTP_GET, [](AsyncWebServerRequest *request) {
		StaticJsonDocument<384> doc;
		doc["type"] = "sys_info";
		doc["wifi_ssid"] = WIFI_SSID;
		doc["wifi_pass"] = WIFI_PASS;
		doc["mqtt_broker"] = CORE_IOT_SERVER;
		doc["mqtt_port"] = CORE_IOT_PORT.toInt();
		doc["sys_token"] = CORE_IOT_TOKEN;

		String payload;
		serializeJson(doc, payload);
		request->send(200, "application/json", payload);
	});

	ws.onEvent(onWsEvent);
	server.addHandler(&ws);
	server.begin();
	serverStarted = true;

	Serial.printf("[BOARD CONFIG] HTTP/WebSocket server started on port %u, ws path %s\n", WEB_PORT, WS_PATH);
}
} // namespace

void load_board_config_from_storage() {
	if (!prefs.begin(PREF_NAMESPACE, true)) {
		Serial.println("[BOARD CONFIG] Preferences read open failed; using defaults");
		return;
	}

	WIFI_SSID = prefs.getString("wifi_ssid", WIFI_SSID);
	WIFI_PASS = prefs.getString("wifi_pass", WIFI_PASS);
	CORE_IOT_SERVER = prefs.getString("mqtt_host", CORE_IOT_SERVER);
	CORE_IOT_PORT = prefs.getString("mqtt_port", CORE_IOT_PORT);
	CORE_IOT_TOKEN = prefs.getString("token", CORE_IOT_TOKEN);
	prefs.end();

	Serial.println("[BOARD CONFIG] Loaded config from Preferences");
}

void save_board_config_to_storage() {
	if (!prefs.begin(PREF_NAMESPACE, false)) {
		Serial.println("[BOARD CONFIG] Preferences write open failed");
		return;
	}

	prefs.putString("wifi_ssid", WIFI_SSID);
	prefs.putString("wifi_pass", WIFI_PASS);
	prefs.putString("mqtt_host", CORE_IOT_SERVER);
	prefs.putString("mqtt_port", CORE_IOT_PORT);
	prefs.putString("token", CORE_IOT_TOKEN);
	prefs.end();
}

void board_config_server_task(void *pvParameters) {
	(void)pvParameters;

	Serial.println("[Task] Starting Board Config Server...");
	load_board_config_from_storage();
	startAccessPoint();
	startHttpServer();

	while (true) {
		ws.cleanupClients();
		if (restartAtMs > 0 && millis() >= restartAtMs) {
			Serial.println("[BOARD CONFIG] Restarting to apply network settings...");
			ESP.restart();
		}
		vTaskDelay(pdMS_TO_TICKS(1000));
	}
}
