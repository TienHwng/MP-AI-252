#include "mqtt_handle.h"

const char* mqtt_server = "172.0.0.1"; //IP cua may chay Mosquitto
const int mqtt_port = 1883;
const char *coreIOT_Token  = "ehehehe"; //device access Token

const char* TOPIC_TELEMETRY = "v1/devices/me/telemetry";
const char* TOPIC_RPC_REQUEST = "v1/devices/me/rpc/request/+";
const char* TOPIC_RPC_RESPONSE = "v1/devices/me/rpc/response/";
const char* TOPIC_ATTRIBUTES = "v1/devices/me/attributes";

extern WiFiClient espClient; // Lấy kết nối WiFi từ main.cpp
PubSubClient client(espClient);

String method_led_blinky = "setValueLedBlinky";
String method_neo_led	 = "setValueNeoLed";


void callback(char* topic, byte* payload, unsigned int length){
  
// Chuyển payload thành chuỗi String để dễ xử lý
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  Serial.println("[MQTT] Nhận được tin nhắn từ topic: " + String(topic));
  
  // Dùng ArduinoJson để đọc hiểu lệnh từ HERA Bot
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, message);
  
  if (error) {
    Serial.println("[MQTT] Lỗi đọc JSON!");
    return;
  }

  // Get method and param from HERA
  String method = doc["method"].as<String>();
  bool params;
  if (!doc["params"].is<bool>()) {
		  Serial.println("params is not bool!");
			return;
		}
  else {
    params = doc["params"].as<bool>();
  }  

  // Get request_id from topic (Ex: ".../request/1" -> "1")
  String topicStr = String(topic);
  int lastSlash = topicStr.lastIndexOf('/');
  String requestId = topicStr.substring(lastSlash + 1);

  // Handling device on/off based on method
  StaticJsonDocument<200> responseDoc;
  if (method == method_led_blinky.c_str()) {
    // Gọi hàm bật/tắt LED thật ở đây (vd: digitalWrite(LED_PIN, params))
    
    // if (xSemaphoreTake(xLedStateSemaphore, portMAX_DELAY) == pdTRUE) {
		// 		is_LED_on = state ? true : false;
		// 		xSemaphoreGive(xLedStateSemaphore);
		//}
    
    Serial.println(params ? "💡 Bật LED thường" : "💡 Tắt LED thường");
    responseDoc["LedState"] = params;
  } 
  else if (method == method_neo_led.c_str()) {
    // Gọi hàm bật/tắt NeoPixel thật ở đây

    // if (xSemaphoreTake(xNeoLedStateSemaphore, portMAX_DELAY) == pdTRUE) {
		// 		is_NeoLED_on = state ? true : false;
		// 		xSemaphoreGive(xNeoLedStateSemaphore);
		// }

    Serial.println(params ? "🌈 Bật NeoPixel" : "🌈 Tắt NeoPixel");
    responseDoc["NeoLedState"] = params;
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
    Serial.print("[MQTT] Attemping connect  to Broker...");
    if (client.connect("ESP32_AIoT_Core")) {
      Serial.println(" Success !");

      // Đăng ký nhận lệnh RPC
      client.subscribe(TOPIC_RPC_REQUEST);
    } else {
      Serial.print(" Failed, error code =");
      Serial.print(client.state());
      Serial.println(" Try again after 5s ...");
      delay(5000);
    }
  }
}

void setup_mqtt(){
    Serial.println("[INIT] CoreIOT task created successfully."); 

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

void publish_telemetry(float temp, float hum, float anomaly, bool led_state, bool neo_state){
    if (!client.connected()) return;

    StaticJsonDocument<256> doc;
    doc["temperature"] = temp;
    doc["huminity"] = hum;
    doc["ìnerence_result"] = anomaly;
    doc["led_state"] = led_state;
    doc["neo_led_state"] = neo_state;

    String payload;
    serializeJson(doc, payload);

    client.publish(TOPIC_TELEMETRY, payload.c_str());
    Serial.println("[MQTT] Send: " + payload);
}

void mqtt_task(void *pvParameters){
  Serial.println("[Task] Starting MQTT Task...");
  setup_mqtt();

  unsigned long lastTelemetry = 0;
  const unsigned long INTERVAL = 5000; 

 
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

      float temp = 0.0;
      float hum = 0.0;
      float anomaly = 0.12; // Giả sử model TinyML trả về

      if (xSemaphoreTake(xDHT20Semaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
        temp = sensorData.temperature;
        hum = sensorData.humidity;
        xSemaphoreGive(xDHT20Semaphore); 
      }

      publish_telemetry(temp, hum, anomaly, is_LED_on, is_NeoLED_on);
    }

    // 3. NHƯỜNG CPU
    vTaskDelay(pdMS_TO_TICKS(10)); 
  }
}