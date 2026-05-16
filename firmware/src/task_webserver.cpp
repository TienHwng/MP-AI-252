#include "task_webserver.h"

#include "task_check_info.h"

AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

bool webserver_isrunning = false;

namespace {
bool		  handlersRegistered = false;
unsigned long restartAtMs		 = 0;

String jsonString(JsonVariantConst value, const String &fallback = "") {
	if (value.isNull()) {
		return fallback;
	}

	String result = value.as<String>();
	result.trim();
	return result.length() > 0 ? result : fallback;
}

String readField(JsonVariantConst object, const char *key1, const char *key2,
				 const char *key3, const String &fallback,
				 bool allowEmpty = false) {
	const char *keys[] = {key1, key2, key3};

	for (const char *key : keys) {
		if (key == nullptr || object[key].isNull()) {
			continue;
		}

		String result = object[key].as<String>();
		result.trim();
		if (allowEmpty || result.length() > 0) {
			return result;
		}
	}

	return fallback;
}

uint16_t jsonPort(JsonVariantConst value, const String &fallback) {
	if (value.is<int>()) {
		const int port = value.as<int>();
		if (port > 0 && port <= 65535) {
			return static_cast<uint16_t>(port);
		}
	}

	const int port = jsonString(value, fallback).toInt();
	if (port > 0 && port <= 65535) {
		return static_cast<uint16_t>(port);
	}

	return 1883;
}

void sendCurrentConfig(AsyncWebSocketClient *client) {
	StaticJsonDocument<512> doc;
	doc["type"]		   = "sys_info";
	doc["wifi_ssid"]   = WIFI_SSID;
	doc["wifi_pass"]   = WIFI_PASS;
	doc["mqtt_broker"] = CORE_IOT_SERVER;
	doc["mqtt_port"]   = CORE_IOT_PORT.toInt();
	doc["sys_token"]   = CORE_IOT_TOKEN;
	doc["ip"]		   = WiFi.localIP().toString();

	String payload;
	serializeJson(doc, payload);

	if (client != nullptr) {
		client->text(payload);
	}
	else {
		ws.textAll(payload);
	}
}

void sendAck(AsyncWebSocketClient *client, bool ok, const char *message) {
	if (client == nullptr) {
		return;
	}

	StaticJsonDocument<192> doc;
	doc["type"]	   = "setting_ack";
	doc["ok"]	   = ok;
	doc["message"] = message;

	String payload;
	serializeJson(doc, payload);
	client->text(payload);
}

void applySettingPayload(JsonVariantConst root, AsyncWebSocketClient *client) {
	JsonVariantConst value =
		root["value"].is<JsonObjectConst>() ? root["value"] : root;

	const String wifiSsid =
		readField(value, "wifi_ssid", "ssid", "WIFI_SSID", WIFI_SSID);
	const String wifiPass =
		readField(value, "wifi_pass", "pass", "WIFI_PASS", WIFI_PASS, true);
	const String mqttBroker = readField(
		value, "mqtt_broker", "mqtt_server", "CORE_IOT_SERVER", CORE_IOT_SERVER);
	const String mqttPort = String(jsonPort(
		value["mqtt_port"],
		readField(value, "port", "CORE_IOT_PORT", nullptr, CORE_IOT_PORT)));
	const String sysToken =
		readField(value, "sys_token", "token", "CORE_IOT_TOKEN", CORE_IOT_TOKEN, true);

	if (wifiSsid.length() == 0 || mqttBroker.length() == 0 ||
		mqttPort.toInt() <= 0) {
		sendAck(client, false, "Missing WiFi SSID, MQTT broker, or MQTT port");
		return;
	}

	Save_info_File(wifiSsid, wifiPass, sysToken, mqttBroker, mqttPort);

	sendAck(client, true, "Configuration saved");
	sendCurrentConfig(client);
	restartAtMs = millis() + 1500;
}

void handleWebSocketMessage(const String &message, AsyncWebSocketClient *client) {
	StaticJsonDocument<768> doc;
	const DeserializationError error = deserializeJson(doc, message);

	if (error) {
		Serial.print("[WEBSERVER] Invalid JSON: ");
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

	if (type == "get_config") {
		sendCurrentConfig(client);
		return;
	}

	sendAck(client, false, "Unsupported payload type");
}
} // namespace

void Webserver_senddata(String data) {
	if (ws.count() > 0) {
		ws.textAll(data);
		Serial.println("[WEBSERVER] Sent WebSocket data: " + data);
	}
	else {
		Serial.println("[WEBSERVER] No WebSocket client connected.");
	}
}

void onEvent(AsyncWebSocket *server, AsyncWebSocketClient *client,
			 AwsEventType type, void *arg, uint8_t *data, size_t len) {
	(void)server;

	if (type == WS_EVT_CONNECT) {
		Serial.printf("[WEBSERVER] WebSocket client #%u connected from %s\n",
					  client->id(), client->remoteIP().toString().c_str());
		sendCurrentConfig(client);
	}
	else if (type == WS_EVT_DISCONNECT) {
		Serial.printf("[WEBSERVER] WebSocket client #%u disconnected\n",
					  client->id());
	}
	else if (type == WS_EVT_DATA) {
		AwsFrameInfo *info = (AwsFrameInfo *)arg;

		if (info->opcode == WS_TEXT && info->final && info->index == 0 &&
			info->len == len) {
			String message;
			message.reserve(len);
			for (size_t i = 0; i < len; i++) {
				message += static_cast<char>(data[i]);
			}

			handleWebSocketMessage(message, client);
		}
		else {
			sendAck(client, false, "Only single-frame text JSON is supported");
		}
	}
}

void connectWSV() {
	if (webserver_isrunning) {
		return;
	}

	if (!LittleFS.begin(true)) {
		Serial.println("[WEBSERVER] LittleFS mount failed; serving fallback text only.");
	}

	if (!handlersRegistered) {
		ws.onEvent(onEvent);
		server.addHandler(&ws);

		server.serveStatic("/", LittleFS, "/").setDefaultFile("index.html");

		server.on("/config", HTTP_GET, [](AsyncWebServerRequest *request) {
			StaticJsonDocument<512> doc;
			doc["type"]		   = "sys_info";
			doc["wifi_ssid"]   = WIFI_SSID;
			doc["wifi_pass"]   = WIFI_PASS;
			doc["mqtt_broker"] = CORE_IOT_SERVER;
			doc["mqtt_port"]   = CORE_IOT_PORT.toInt();
			doc["sys_token"]   = CORE_IOT_TOKEN;

			String payload;
			serializeJson(doc, payload);
			request->send(200, "application/json", payload);
		});

		server.onNotFound([](AsyncWebServerRequest *request) {
			request->send(
				200, "text/plain",
				"H.E.R.A board config server is running. Upload frontend/data files to LittleFS.");
		});

		handlersRegistered = true;
	}

	server.begin();
	webserver_isrunning = true;

	Serial.println("[WEBSERVER] HTTP/WebSocket config portal started on port 80.");
}

void connnectWSV() {
	connectWSV();
}

void Webserver_stop() {
	ws.closeAll();
	server.end();
	webserver_isrunning = false;
}

void Webserver_reconnect() {
	if (!webserver_isrunning) {
		connectWSV();
	}

	ws.cleanupClients();

	if (restartAtMs > 0 && millis() >= restartAtMs) {
		Serial.println("[WEBSERVER] Restarting to apply configuration...");
		ESP.restart();
	}
}
