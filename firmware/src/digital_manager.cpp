#include "digital_manager.h"
#include "neo_display.h"

// --- Biến cho nút Relay (Nút số 1) ---
static bool output1State = false;
static bool output2State = false;
static bool output3State = false;
static bool output4State = false;

static bool lastStableRead   = HIGH;
static bool lastInstantRead  = HIGH;
static TickType_t lastChange = 0;

// --- Biến cho nút lật trang LCD (Nút BOOT) ---
static bool bootLastStableRead   = HIGH;
static bool bootLastInstantRead  = HIGH;
static TickType_t bootLastChange = 0;

void setup_digital_manager() {
    Serial.println("[INIT] Digital manager task created successfully");

    // Khởi tạo nút số 1 (Nút điều khiển)
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    // Khởi tạo nút BOOT (Nút lật LCD)
    pinMode(BOOT_PIN, INPUT_PULLUP);

    // Khởi tạo các chân Output theo cấu hình cổng số
    pinMode(WS2812_PIN, OUTPUT);
    pinMode(MINI_FAN_PIN, OUTPUT);
    pinMode(IR_RECEIVE_PIN, OUTPUT);
    pinMode(RELAY_PIN, OUTPUT);

    digitalWrite(WS2812_PIN, LOW);
    digitalWrite(MINI_FAN_PIN, LOW);
    digitalWrite(IR_RECEIVE_PIN, LOW);
    digitalWrite(RELAY_PIN, LOW);

    // Chốt trạng thái ban đầu cho 2 nút
    lastStableRead      = digitalRead(BUTTON_PIN);
    lastInstantRead     = lastStableRead;
    lastChange          = xTaskGetTickCount();

    bootLastStableRead  = digitalRead(BOOT_PIN);
    bootLastInstantRead = bootLastStableRead;
    bootLastChange      = xTaskGetTickCount();
}

void digital_manager(void *pvParameters) {
    setup_digital_manager();

    while (1) {
        // ==========================================
        // 1. XỬ LÝ NÚT SỐ 1 (ĐIỀU KHIỂN THIẾT BỊ)
        // ==========================================
        const bool reading = digitalRead(BUTTON_PIN);

        if (reading != lastInstantRead) {
            lastInstantRead = reading;
            lastChange      = xTaskGetTickCount();
        }

        if ((xTaskGetTickCount() - lastChange) >= pdMS_TO_TICKS(DEBOUNCE_MS)) {
            if (reading != lastStableRead) {
                lastStableRead = reading;

                if (reading == LOW) { // Nhấn nút 1
                    is_LED_on = !is_LED_on;
                    is_NeoLED_on = !is_NeoLED_on;
                    is_ws2812_on = !is_ws2812_on;
                    is_mini_fan_on = !is_mini_fan_on;
                    is_relay_on = !is_relay_on;

                    // ws2812_toggle();
                    // digitalWrite(MINI_FAN_PIN,      is_mini_fan_on ? HIGH : LOW);
                    // digitalWrite(RELAY_PIN,         is_relay_on ? HIGH : LOW);
                    // digitalWrite(IR_RECEIVE_PIN,    output3State ? HIGH : LOW);
                }
            }
        }

        // ==========================================
        // 2. XỬ LÝ NÚT BOOT (LẬT TRANG LCD)
        // ==========================================
        const bool bootReading = digitalRead(BOOT_PIN);

        if (bootReading != bootLastInstantRead) {
            bootLastInstantRead = bootReading;
            bootLastChange      = xTaskGetTickCount();
        }

        if ((xTaskGetTickCount() - bootLastChange) >= pdMS_TO_TICKS(DEBOUNCE_MS)) {
            if (bootReading != bootLastStableRead) {
                bootLastStableRead = bootReading;

                if (bootReading == LOW) { // Nhấn nút BOOT
                    // Chuyển sang trang tiếp theo, nếu vượt quá số trang thì vòng lại 0
                    current_lcd_screen = (LcdScreen)((current_lcd_screen + 1) % SCREEN_COUNT);
                    
                    if (IS_DEBUG_MODE || IS_MONITOR_MODE) {
                        Serial.printf("[BUTTON] BOOT pressed -> LCD Screen %d\n", current_lcd_screen);
                    }
                }
            }
        }

        // Code tam thoi, se cap nhat lai sau
        if (xSemaphoreTake(xWS2812StateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {           
            ws2812_set(is_ws2812_on);
            xSemaphoreGive(xWS2812StateSemaphore);
        }

        if (xSemaphoreTake(xFanStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
            digitalWrite(MINI_FAN_PIN, is_mini_fan_on ? HIGH : LOW);
            xSemaphoreGive(xFanStateSemaphore);
        }

        if (xSemaphoreTake(xRelayStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
            digitalWrite(RELAY_PIN, is_relay_on ? HIGH : LOW);
            xSemaphoreGive(xRelayStateSemaphore);
        }

        vTaskDelay(pdMS_TO_TICKS(30)); // Luồng quét nút nhấn quét rất nhanh (10ms)
    }
}