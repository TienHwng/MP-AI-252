#include "mqtt_handle.h"
#include "WiFi.h"

void forceConnectWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);          // giữ WiFi ổn định hơn
    WiFi.disconnect(true, true);   // xóa kết nối cũ
    delay(1000);

	Serial.println("[WIFI] Starting connection...");
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    int retry = 0;
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
        retry++;

        // cứ 20 lần (~10s) chưa vào được thì connect lại từ đầu
        if (retry >= 20) {
			Serial.println("\n[WIFI] Retrying...");
            WiFi.disconnect(true, true);
            delay(1000);
            WiFi.begin(WIFI_SSID, WIFI_PASS);
            retry = 0;
        }
    }

	Serial.println("\n[WIFI] Connected!");
	Serial.print("[WIFI] IP: ");
    Serial.println(WiFi.localIP());
}












const char *mqtt_server	  = "172.20.10.2"; // IP cua may chay Mosquitto
const int	mqtt_port	  = 1883;
const char *coreIOT_Token = "ehehehe"; // device access Token

const char *TOPIC_TELEMETRY	   = "v1/devices/me/telemetry";
const char *TOPIC_RPC_REQUEST  = "v1/devices/me/rpc/request/+";
const char *TOPIC_RPC_RESPONSE = "v1/devices/me/rpc/response/";
const char *TOPIC_ATTRIBUTES   = "v1/devices/me/attributes";

// extern WiFiClient espClient; // Lấy kết nối WiFi từ main.cpp
WiFiClient	 espClient;
PubSubClient client(espClient);

String method_led_blinky = "setValueLedBlinky";
String method_neo_led	 = "setValueNeoLed";
String method_ws2812	 = "setValueWS2812";
String method_relay		 = "setValueRelay";
String method_mini_fan	 = "setValueMiniFan";

static bool setActuatorState(SemaphoreHandle_t mutex, boolean &stateRef, bool state, uint8_t pin) {
	if (mutex == NULL) {
		return false;
	}

	if (xSemaphoreTake(mutex, portMAX_DELAY) != pdTRUE) {
		return false;
	}

	stateRef = state ? true : false;
	xSemaphoreGive(mutex);

	pinMode(pin, OUTPUT);
	digitalWrite(pin, state ? HIGH : LOW);
	return true;
}

void callback(char *topic, byte *payload, unsigned int length) {

	// Chuyển payload thành chuỗi String để dễ xử lý
	String message = "";
	for (unsigned int i = 0; i < length; i++) {
		message += (char)payload[i];
	}

	Serial.println("[MQTT] Received message from topic: " + String(topic));

	// Dùng ArduinoJson để đọc hiểu lệnh từ HERA Bot
	StaticJsonDocument<512> doc;
	DeserializationError	error = deserializeJson(doc, message);

	if (error) {
		Serial.println("[MQTT] Error JSON!");
		return;
	}

	// Get method and param from HERA
	String method = doc["method"].as<String>();
	bool   params;
	if (!doc["params"].is<bool>()) {
		Serial.println("params is not bool!");
		return;
	}
	else {
		params = doc["params"].as<bool>();
	}

	// Get request_id from topic (Ex: ".../request/1" -> "1")
	String topicStr	 = String(topic);
	int	   lastSlash = topicStr.lastIndexOf('/');
	String requestId = topicStr.substring(lastSlash + 1);

	// Handling device on/off based on method
	StaticJsonDocument<512> responseDoc;
	if (method == method_led_blinky.c_str()) {
		setActuatorState(xLedStateSemaphore, is_LED_on, params, LED_PIN);
		responseDoc["Led_Status"] = params;
		
		if (IS_SHOW_PAYLOAD) {
			Serial.println(params ? "[ACTION] Turning on normal LED" : "[ACTION] Turning off normal LED");
		}
	}

	else if (method == method_neo_led.c_str()) {
		setActuatorState(xNeoLedStateSemaphore, is_NeoLED_on, params, NEO_LED_PIN);
		responseDoc["NeoLed_Status"] = params;
		
		if (IS_SHOW_PAYLOAD) {
			Serial.println(params ? "[ACTION] Turning on NeoPixel" : "[ACTION] Turning off NeoPixel");
		}
	}

	else if (method == method_ws2812.c_str()) {
		setActuatorState(xWS2812StateSemaphore, is_ws2812_on, params, WS2812_PIN);
		responseDoc["WS2812_Status"] = params;
		
		if (IS_SHOW_PAYLOAD) {
			Serial.println(params ? "[ACTION] Turning on WS2812" : "[ACTION] Turning off WS2812");
		}
	}

	else if (method == method_relay.c_str()) {
		setActuatorState(xRelayStateSemaphore, is_relay_on, params, RELAY_PIN);
		responseDoc["Relay_Status"] = params;
		
		if (IS_SHOW_PAYLOAD) {
			Serial.println(params ? "[ACTION] Turning on Relay" : "[ACTION] Turning off Relay");
		}
	}

	else if (method == method_mini_fan.c_str()) {
		setActuatorState(xFanStateSemaphore, is_mini_fan_on, params, MINI_FAN_PIN);
		responseDoc["Fan_Status"] = params;

		if (IS_SHOW_PAYLOAD) {
			Serial.println(params ? "[ACTION] Turning on Fan" : "[ACTION] Turning off Fan");
		}
	}

	else {
		Serial.println("[MQTT] Unknown method: " + method);
		responseDoc["error"] = "Unknown method";
	}

	// Respone to HERA
	String responseString;
	serializeJson(responseDoc, responseString);

	String responseTopic = String(TOPIC_RPC_RESPONSE) + requestId;
	client.publish(responseTopic.c_str(), responseString.c_str());
	client.publish(TOPIC_ATTRIBUTES, responseString.c_str());
}

void reconnect() {
	while (!client.connected()) {
		Serial.print("[MQTT] Attempting to connect to Broker ");
        Serial.print(mqtt_server);
        Serial.print(":");
        Serial.print(mqtt_port);
        Serial.println(" ...");

        String clientId = "ESP32_AIoT_Core-";
        clientId += String(random(0xffff), HEX);

		if (client.connect(clientId.c_str())) {
			Serial.println(" Success !");

			// Đăng ký nhận lệnh RPC
			client.subscribe(TOPIC_RPC_REQUEST);
		}
		else {
			Serial.print("[MQTT] Failed, state = ");
            Serial.println(client.state());

            switch (client.state()) {
                case -4: Serial.println("MQTT_CONNECTION_TIMEOUT"); break;
                case -3: Serial.println("MQTT_CONNECTION_LOST"); break;
                case -2: Serial.println("MQTT_CONNECT_FAILED"); break;
                case -1: Serial.println("MQTT_DISCONNECTED"); break;
                case 1:  Serial.println("MQTT_CONNECT_BAD_PROTOCOL"); break;
                case 2:  Serial.println("MQTT_CONNECT_BAD_CLIENT_ID"); break;
                case 3:  Serial.println("MQTT_CONNECT_UNAVAILABLE"); break;
                case 4:  Serial.println("MQTT_CONNECT_BAD_CREDENTIALS"); break;
                case 5:  Serial.println("MQTT_CONNECT_UNAUTHORIZED"); break;
            }
			Serial.println(" Try again after 5s ...");
			delay(5000);
		}
	}
}

void setup_mqtt() {
	forceConnectWiFi();
	Serial.println("[INIT] CoreIOT task created successfully.");
	client.setBufferSize(1024);

	// while (1) {
	// 	// if (WiFi.status() == WL_CONNECTED) {
	// 	if (xSemaphoreTake(xBinarySemaphoreInternet, portMAX_DELAY) == pdTRUE) {
	// 		break;
	// 	}

	// 	delay(500);
	// 	Serial.print(".");
	// }

	client.setServer(mqtt_server, mqtt_port);
	client.setCallback(callback);
}

void publish_telemetry(float temp, float hum, float anomaly, bool led_state, bool neo_state) {
	if (!client.connected())
		return;

	StaticJsonDocument<1024> doc;
	const unsigned long now = millis();

	// Flattened fields for compatibility with current backend parsing
	doc["temperature"] = temp;
	doc["humidity"] = hum;
	doc["inference_result"] = anomaly;
	doc["timestamp"] = now;

	doc["led_status"] = is_LED_on;
	doc["neo_led_status"] = is_NeoLED_on;
	doc["ws2812_status"] = is_ws2812_on;
	doc["relay_status"] = is_relay_on;
	doc["fan_status"] = is_mini_fan_on;

	// Additional network and runtime data
	doc["wifi_connected"] = (WiFi.status() == WL_CONNECTED);
	doc["wifi_rssi"] = WiFi.RSSI();
	doc["wifi_ip"] = WiFi.localIP().toString();
	doc["mqtt_connected"] = client.connected();
	doc["uptime_ms"] = now;

	JsonObject network = doc.createNestedObject("network");
	network["wifi_connected"] = (WiFi.status() == WL_CONNECTED);
	network["wifi_rssi"] = WiFi.RSSI();
	network["wifi_ip"] = WiFi.localIP().toString();
	network["mqtt_connected"] = client.connected();
	network["uptime_ms"] = now;
	
	JsonObject devices = doc.createNestedObject("devices");
	devices["led_status"] = is_LED_on;
	devices["neo_led_status"] = is_NeoLED_on;
	devices["ws2812_status"] = is_ws2812_on;
	devices["relay_status"] = is_relay_on;
	devices["mini_fan_status"] = is_mini_fan_on;
	
	JsonObject sensors = doc.createNestedObject("sensors");
	sensors["temperature"] = temp;
	sensors["humidity"] = hum;
	sensors["light"] = 90.0; // Placeholder for light sensor
	
	// doc["lcd_screen"] = static_cast<int>(current_lcd_screen);
	// doc["anomaly"] = anomaly;

	String payload;
	serializeJson(doc, payload);

	client.publish(TOPIC_TELEMETRY, payload.c_str());
	Serial.println("[MQTT] Send: " + payload);
}

void mqtt_task(void *pvParameters) {
	Serial.println("[Task] Starting MQTT Task...");
	setup_mqtt();

	unsigned long		lastTelemetry = 0;
	const unsigned long INTERVAL	  = 5000;

	while (1) {
		if (!client.connected() && WiFi.status() == WL_CONNECTED) {
			reconnect();
		}

		// Listen from HERA
		client.loop();

		// check time to send data
		unsigned long now = millis();
		if (now - lastTelemetry >= INTERVAL) {
			lastTelemetry = now;

			float temp	  = 0.0;
			float hum	  = 0.0;
			float anomaly = 0.12; // Giả sử model TinyML trả về

			if (xSemaphoreTake(xSensorDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
				temp = sensorData.temperature;
				hum	 = sensorData.humidity;
				xSemaphoreGive(xSensorDataMutex);
			}

			publish_telemetry(temp, hum, anomaly, is_LED_on, is_NeoLED_on);
		}

		// 3. NHƯỜNG CPU
		vTaskDelay(pdMS_TO_TICKS(10));
	}
}
