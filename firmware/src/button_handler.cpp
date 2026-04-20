#include "button_handler.h"

// --- Biến cho nút lật trang LCD (Nút BOOT) ---
static bool bootLastStableRead   = HIGH;
static bool bootLastInstantRead  = HIGH;
static TickType_t bootLastChange = 0;

void setup_button_handler() {
    Serial.println("[INIT] Button handler task created successfully");

    // Khởi tạo nút BOOT (Nút lật LCD)
    pinMode(BOOT_PIN, INPUT_PULLUP);

    // Chốt trạng thái ban đầu cho nút BOOT
    bootLastStableRead  = digitalRead(BOOT_PIN);
    bootLastInstantRead = bootLastStableRead;
    bootLastChange      = xTaskGetTickCount();
}

void button_handler(void *pvParameters) {
    (void)pvParameters;
    setup_button_handler();

    while (1) {
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

        vTaskDelay(pdMS_TO_TICKS(20)); // Polling nút mỗi 20ms
    }
}
