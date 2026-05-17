#include "mqtt_handle.h"
#include "digital_manager.h"
#include "led_display.h"
#include "WiFi.h"

void forceConnectWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);          // Keep WiFi connection more stable
    WiFi.disconnect(true, true);   // Clear old connections
    delay(1000);

	Serial.println("[WIFI] Starting connection...");
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    int retry = 0;
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
        retry++;

        // After 20 attempts (~10s) without connection, restart connection from the beginning
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












const char *TOPIC_TELEMETRY	   = "v1/devices/me/telemetry";
const char *TOPIC_RPC_REQUEST  = "v1/devices/me/rpc/request/+";
const char *TOPIC_RPC_RESPONSE = "v1/devices/me/rpc/response/";
const char *TOPIC_ATTRIBUTES   = "v1/devices/me/attributes";

// extern WiFiClient espClient; // Get WiFi connection from main.cpp
WiFiClient	 espClient;
PubSubClient client(espClient);

String method_led_blinky		= "setValueLedBlinky";
String method_led_brightness	= "setLedBrightness";
String method_neo_led			= "setValueNeoLed";
String method_ws2812			= "setValueWS2812";
String method_ws2812_brightness	= "setWS2812Brightness";
String method_ws2812_color		= "setWS2812Color";
String method_strip_brightness	= "setStripBrightness";
String method_relay				= "setValueRelay";
String method_mini_fan			= "setValueMiniFan";
String method_fan_speed			= "setFanSpeed";

static bool setActuatorState(SemaphoreHandle_t mutex, boolean &stateRef, bool state, uint8_t pin) {
	if (mutex == NULL) {
		return false;
	}

	if (xSemaphoreTake(mutex, portMAX_DELAY) != pdTRUE) {
		return false;
	}

	stateRef = state ? true : false;
	uint16_t ledPwm = (pin == LED_PIN && state) ? (led_brightness > 1023 ? 1023 : led_brightness) : 0;
	xSemaphoreGive(mutex);

	pinMode(pin, OUTPUT);
	if (pin == LED_PIN) {
		analogWrite(pin, ledPwm);
	}
	else {
		digitalWrite(pin, state ? HIGH : LOW);
	}
	return true;
}

static String formatWs2812Color(uint8_t red, uint8_t green, uint8_t blue) {
	char buffer[8];
	snprintf(buffer, sizeof(buffer), "#%02X%02X%02X", red, green, blue);
	return String(buffer);
}

static bool parseWs2812ColorHex(String value, uint8_t &red, uint8_t &green, uint8_t &blue) {
	value.trim();
	if (value.startsWith("#")) {
		value.remove(0, 1);
	}
	if (value.startsWith("0x") || value.startsWith("0X")) {
		value.remove(0, 2);
	}
	if (value.length() != 6) {
		return false;
	}

	char *endPtr = nullptr;
	unsigned long raw = strtoul(value.c_str(), &endPtr, 16);
	if (endPtr == value.c_str() || *endPtr != '\0') {
		return false;
	}

	red   = (raw >> 16) & 0xFF;
	green = (raw >> 8) & 0xFF;
	blue  = raw & 0xFF;
	return true;
}

static bool parseWs2812ColorParams(JsonVariantConst params, uint8_t &red, uint8_t &green, uint8_t &blue) {
	if (params.is<JsonObjectConst>()) {
		JsonObjectConst color = params.as<JsonObjectConst>();
		if (!color["r"].is<int>() || !color["g"].is<int>() || !color["b"].is<int>()) {
			return false;
		}

		red   = constrain(color["r"].as<int>(), 0, 255);
		green = constrain(color["g"].as<int>(), 0, 255);
		blue  = constrain(color["b"].as<int>(), 0, 255);
		return true;
	}

	if (params.is<const char*>()) {
		return parseWs2812ColorHex(String(params.as<const char*>()), red, green, blue);
	}

	if (params.is<String>()) {
		return parseWs2812ColorHex(params.as<String>(), red, green, blue);
	}

	return false;
}

void callback(char *topic, byte *payload, unsigned int length) {

	// Convert payload to String for easier processing
	String message = "";
	for (unsigned int i = 0; i < length; i++) {
		message += (char)payload[i];
	}

	Serial.println("[MQTT] Received message from topic: " + String(topic));

	// Use ArduinoJson to parse commands from HERA Bot
	StaticJsonDocument<512> doc;
	DeserializationError	error = deserializeJson(doc, message);

	if (error) {
		Serial.println("[MQTT] Error JSON!");
		return;
	}

	// Get method and param from HERA
	String method = doc["method"].as<String>();

	// Get request_id from topic (Ex: ".../request/1" -> "1")
	String topicStr	 = String(topic);
	int	   lastSlash = topicStr.lastIndexOf('/');
	String requestId = topicStr.substring(lastSlash + 1);

	// Handling device on/off based on method
	StaticJsonDocument<512> responseDoc;

	// ========================================
	// Group 1: Commands with boolean parameters
	// ========================================
	if (method == method_led_blinky.c_str() ||
		method == method_neo_led.c_str()    ||
		method == method_ws2812.c_str()     ||
		method == method_relay.c_str()      ||
		method == method_mini_fan.c_str()) {

		if (!doc["params"].is<bool>()) {
			Serial.println("[MQTT] params is not bool!");
			responseDoc["error"] = "params must be bool";
		}
		else {
			bool params = doc["params"].as<bool>();

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
				// Boolean fan ON should use full PWM so the motor has enough starting torque.
				int16_t spd = params ? FAN_PWM_MAX : 0;
				if (xSemaphoreTake(xFanStateSemaphore, portMAX_DELAY) == pdTRUE) {
					fan_speed      = spd;
					is_mini_fan_on = (spd > 0);
					xSemaphoreGive(xFanStateSemaphore);
				}
				responseDoc["Fan_Status"] = params;
				responseDoc["Fan_Speed"]  = spd;
				if (IS_SHOW_PAYLOAD) {
					Serial.printf("[ACTION] Fan %s (speed=%u)\n", params ? "ON" : "OFF", spd);
				}
			}
		}
	}

	// ========================================
	// Group 2: LED brightness adjustment commands (int 0..1023)
	// ========================================
	else if (method == method_led_brightness.c_str()) {
		if (!doc["params"].is<int>()) {
			Serial.println("[MQTT] params is not int!");
			responseDoc["error"] = "params must be int (0..1023)";
		}
		else {
			int val = doc["params"].as<int>();
			if (val < 0)    val = 0;
			if (val > 1023) val = 1023;

			led_set_brightness((uint16_t)val);
			responseDoc["Led_Brightness"] = val;
			responseDoc["Led_Status"]     = (val > 0);
			Serial.printf("[ACTION] LED brightness -> %d\n", val);
		}
	}

	// ========================================
	// Group 3: WS2812 brightness adjustment commands (int 0..255)
	// ========================================
	else if (method == method_ws2812_brightness.c_str()) {
		if (!doc["params"].is<int>()) {
			Serial.println("[MQTT] params is not int!");
			responseDoc["error"] = "params must be int (0..255)";
		}
		else {
			int val = doc["params"].as<int>();
			if (val < 0)   val = 0;
			if (val > 255) val = 255;

			if (xSemaphoreTake(xWS2812StateSemaphore, portMAX_DELAY) == pdTRUE) {
				ws2812_brightness = (uint8_t)val;
				is_ws2812_on      = (val > 0);
				xSemaphoreGive(xWS2812StateSemaphore);
			}
			responseDoc["WS2812_Brightness"] = val;
			Serial.printf("[ACTION] WS2812 brightness -> %d\n", val);
		}
	}

	// ========================================
	// Group 4: WS2812 color adjustment commands (hex #RRGGBB or {r,g,b} object)
	// ========================================
	else if (method == method_ws2812_color.c_str()) {
		JsonVariantConst params = doc["params"];
		uint8_t red   = 0;
		uint8_t green = 0;
		uint8_t blue  = 0;

		if (!parseWs2812ColorParams(params, red, green, blue)) {
			Serial.println("[MQTT] params is not a valid color!");
			responseDoc["error"] = "params must be #RRGGBB or {r,g,b}";
		}
		else {
			String colorHex = formatWs2812Color(red, green, blue);
			ws2812_set_color(red, green, blue);
			responseDoc["WS2812_Color"] = colorHex;
			Serial.println("[ACTION] WS2812 color -> " + colorHex);
		}
	}

	// ========================================
	// Group 5: Fan speed adjustment commands (int 0..1023)
	// ========================================
	else if (method == method_fan_speed.c_str()) {
		if (!doc["params"].is<int>()) {
			Serial.println("[MQTT] params is not int!");
			responseDoc["error"] = "params must be int (0..1023)";
		}
		else {
			int16_t val = doc["params"].as<int>();
			if (val < 0)   val = 0;
			if (val > FAN_PWM_MAX) val = FAN_PWM_MAX;

			if (xSemaphoreTake(xFanStateSemaphore, portMAX_DELAY) == pdTRUE) {
				fan_speed      = (uint16_t)val;
				is_mini_fan_on = (val > 0);
				xSemaphoreGive(xFanStateSemaphore);
			}
			responseDoc["Fan_Speed"]  = val;
			responseDoc["Fan_Status"] = (val > 0);
			Serial.printf("[ACTION] Fan speed -> %d (0-1023)\n", val);
		}
	}

	// ========================================
	// Group 6: Strip brightness adjustment commands (int 0..255)
	// ========================================
	else if (method == method_strip_brightness.c_str()) {
		if (!doc["params"].is<int>()) {
			Serial.println("[MQTT] params is not int!");
			responseDoc["error"] = "params must be int (0..255)";
		}
		else {
			int val = doc["params"].as<int>();
			if (val < 0)   val = 0;
			if (val > 255) val = 255;

			if (xSemaphoreTake(xNeoLedStateSemaphore, portMAX_DELAY) == pdTRUE) {
				strip_brightness = (uint8_t)val;
				xSemaphoreGive(xNeoLedStateSemaphore);
			}
			neoLED_set_brightness((uint8_t)val);
			responseDoc["Strip_Brightness"] = val;
			Serial.printf("[ACTION] Strip brightness -> %d\n", val);
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
        Serial.print(CORE_IOT_SERVER);
        Serial.print(":");
        Serial.print(CORE_IOT_PORT);
        Serial.println(" ...");

        String clientId = "ESP32_AIoT_Core-";
        clientId += String(random(0xffff), HEX);

		if (client.connect(clientId.c_str())) {
			Serial.println(" Success !");

			// Subscribe to RPC commands
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
	client.setBufferSize(2048);

	// while (1) {
	// 	// if (WiFi.status() == WL_CONNECTED) {
	// 	if (xSemaphoreTake(xBinarySemaphoreInternet, portMAX_DELAY) == pdTRUE) {
	// 		break;
	// 	}

	// 	delay(500);
	// 	Serial.print(".");
	// }

	client.setServer(CORE_IOT_SERVER.c_str(), CORE_IOT_PORT.toInt());
	client.setCallback(callback);
}

void publish_telemetry(float temp, float hum, float light, float gas, float anomaly, bool led_state, bool neo_state) {
	if (!client.connected())
		return;

	StaticJsonDocument<2048> doc;
	const unsigned long now = millis();

	// // Flattened fields for compatibility with current backend parsing
	// doc["temperature"] = temp;
	// doc["humidity"] = hum;
	// doc["inference_result"] = anomaly;
	// doc["timestamp"] = now;

	// doc["led_status"] = is_LED_on;
	// doc["neo_led_status"] = is_NeoLED_on;
	// doc["ws2812_status"] = is_ws2812_on;
	// doc["relay_status"] = is_relay_on;
	// doc["fan_status"] = is_mini_fan_on;

	// // Additional network and runtime data
	// doc["wifi_connected"] = (WiFi.status() == WL_CONNECTED);
	// doc["wifi_rssi"] = WiFi.RSSI();
	// doc["wifi_ip"] = WiFi.localIP().toString();
	// doc["mqtt_connected"] = client.connected();
	// doc["uptime_ms"] = now;

	JsonObject network = doc.createNestedObject("network");
	network["wifi_connected"] = (WiFi.status() == WL_CONNECTED);
	network["wifi_rssi"] = WiFi.RSSI();
	network["wifi_ip"] = WiFi.localIP().toString();
	network["mqtt_connected"] = client.connected();
	network["uptime_ms"] = now;
	
	JsonObject devices = doc.createNestedObject("devices");
	JsonObject led = devices.createNestedObject("led");
	led["status"] = led_state;
	led["brightness"] = led_state ? led_brightness : 0;
	led["voltage"] = led_state ? (V_REF * led_brightness / 1023.0) : 0.0;

	JsonObject neo_led = devices.createNestedObject("neo_led");
	neo_led["status"] = neo_state;
	neo_led["brightness"] = strip_brightness;
	neo_led["color"] = getNeoLedColorFromHumidity(hum);
	neo_led["voltage"] = neo_state ? (V_REF * strip_brightness / 255.0) : 0.0;
	
	JsonObject ws2812 = devices.createNestedObject("ws2812");
	ws2812["status"] = is_ws2812_on;
	ws2812["brightness"] = ws2812_brightness;
	ws2812["color"] = ws2812_get_color_hex();
	ws2812["voltage"] = is_ws2812_on ? (V_REF * ws2812_brightness / 255.0) : 0.0;

	JsonObject relay = devices.createNestedObject("relay");
	relay["status"] = is_relay_on;
	relay["voltage"] = is_relay_on ? V_REF : 0.0;

	JsonObject mini_fan = devices.createNestedObject("mini_fan");
	mini_fan["status"] = is_mini_fan_on;
	mini_fan["speed"] = fan_speed;
	mini_fan["voltage"] = is_mini_fan_on ? (V_REF * fan_speed / FAN_PWM_MAX) : 0.0;
	
	JsonObject sensors = doc.createNestedObject("sensors");
	JsonObject dht20 = sensors.createNestedObject("dht20");
	dht20["temperature"] = temp;
	dht20["humidity"] = hum;
	dht20["voltage"] = V_REF;

	JsonObject light_sensor = sensors.createNestedObject("light");
	light_sensor["value"] = light;
	light_sensor["voltage"] = V_REF;

	JsonObject gas_sensor = sensors.createNestedObject("gas");
	gas_sensor["value"] = gas;
	gas_sensor["voltage"] = V_REF;
	
	// doc["lcd_screen"] = static_cast<int>(current_lcd_screen);
	// doc["anomaly"] = anomaly;

	String payload;
	serializeJson(doc, payload);

	String prettyPayload;
	serializeJsonPretty(doc, prettyPayload);

	client.publish(TOPIC_TELEMETRY, payload.c_str());
	// Serial.println("[MQTT] Send:");
	// Serial.println(prettyPayload);
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
			float light   = 0.0;
			float gas     = 0.0;
			float anomaly = 0.12; // Assuming TinyML model returns this value

			if (xSemaphoreTake(xDHT20Semaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
				temp = sensorData.temperature;
				hum	 = sensorData.humidity;
				xSemaphoreGive(xDHT20Semaphore);
			}

			if (xSemaphoreTake(xLightSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
				light = sensorData.light;
				xSemaphoreGive(xLightSemaphore);
			}

			if (xSemaphoreTake(xMQ2Semaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
				gas = sensorData.gas;
				xSemaphoreGive(xMQ2Semaphore);
			}

			publish_telemetry(temp, hum, light, gas, anomaly, is_LED_on, is_NeoLED_on);
		}

		// 3. Yield CPU to other tasks
		vTaskDelay(pdMS_TO_TICKS(10));
	}
}
