#include "digital_manager.h"
#include "neo_display.h"

// Lưu giá trị trước đó để chỉ ghi khi thay đổi
static uint8_t lastFanSpeed        = 0;
static uint8_t lastWs2812Brightness = 0;
static bool    lastWs2812On         = false;

void setup_digital_manager() {
    Serial.println("[INIT] Digital manager task created successfully");

    // Khởi tạo các chân Output theo cấu hình cổng số
    pinMode(WS2812_PIN, OUTPUT);
    pinMode(IR_RECEIVE_PIN, OUTPUT);
    pinMode(RELAY_PIN, OUTPUT);

    digitalWrite(WS2812_PIN, LOW);
    digitalWrite(IR_RECEIVE_PIN, LOW);
    digitalWrite(RELAY_PIN, LOW);

    // Khởi tạo LEDC PWM cho quạt mini
    ledcSetup(FAN_PWM_CHANNEL, FAN_PWM_FREQ, FAN_PWM_RESOLUTION);
    ledcAttachPin(MINI_FAN_PIN, FAN_PWM_CHANNEL);
    ledcWrite(FAN_PWM_CHANNEL, 0);   // Tắt quạt ban đầu
}

void fan_set_speed(uint8_t speed) {
    fan_speed      = speed;
    is_mini_fan_on = (speed > 0);

    ledcWrite(FAN_PWM_CHANNEL, speed);

    if (IS_DEBUG_MODE || IS_MONITOR_MODE) {
        Serial.printf("[FAN] Speed set to %u / 255\n", speed);
    }
}

void digital_manager(void *pvParameters) {
    setup_digital_manager();

    while (1) {
        // ==========================================
        // ĐIỀU KHIỂN THIẾT BỊ THEO BIẾN GLOBAL
        //    (Được set từ MQTT hoặc các task khác)
        // ==========================================

        // --- WS2812: kiểm tra cả on/off lẫn brightness ---
        if (xSemaphoreTake(xWS2812StateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
            bool    curOn   = is_ws2812_on;
            uint8_t curBrt  = ws2812_brightness;
            xSemaphoreGive(xWS2812StateSemaphore);

            if (curOn != lastWs2812On) {
                ws2812_set(curOn);
                lastWs2812On = curOn;
                lastWs2812Brightness = curBrt;
            }
            else if (curBrt != lastWs2812Brightness) {
                ws2812_set_brightness(curBrt);
                lastWs2812Brightness = curBrt;
            }
        }

        // --- Quạt mini: điều chỉnh tốc độ bằng PWM ---
        if (xSemaphoreTake(xFanStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
            uint8_t curSpeed = fan_speed;
            xSemaphoreGive(xFanStateSemaphore);

            if (curSpeed != lastFanSpeed) {
                fan_set_speed(curSpeed);
                lastFanSpeed = curSpeed;
            }
        }

        // --- Relay: vẫn giữ bật/tắt đơn giản ---
        if (xSemaphoreTake(xRelayStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
            digitalWrite(RELAY_PIN, is_relay_on ? HIGH : LOW);
            xSemaphoreGive(xRelayStateSemaphore);
        }

        vTaskDelay(pdMS_TO_TICKS(30));
    }
}