#include "button_handler.h"

// --- Variables for LCD page flip button (BOOT button) ---
static bool bootLastStableRead   = HIGH;
static bool bootLastInstantRead  = HIGH;
static TickType_t bootLastChange = 0;

void setup_button_handler() {
    Serial.println("[INIT] Button handler task created successfully");

    // Initialize BOOT button (LCD page flip button)
    pinMode(BOOT_PIN, INPUT_PULLUP);

    // Lock initial state for BOOT button
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

                if (bootReading == LOW) { // BOOT button pressed
                    // Switch to next page, if exceeds total pages wrap back to 0
                    current_lcd_screen = (LcdScreen)((current_lcd_screen + 1) % SCREEN_COUNT);
                    
                    if (IS_DEBUG_MODE || IS_SHOW_BUTTON_STATUS) {
                        Serial.printf("[BUTTON] BOOT pressed -> LCD Screen %d\n", current_lcd_screen);
                    }
                }
            }
        }

        vTaskDelay(pdMS_TO_TICKS(20)); // Poll button every 20ms
    }
}
