#include "analog_manager.h"

enum AnalogLevel : int8_t {
    ANALOG_UNKNOWN = -1,
    ANALOG_LEVEL_0 = 0,
    ANALOG_LEVEL_1 = 1,
    ANALOG_LEVEL_2 = 2,
    ANALOG_LEVEL_3 = 3,
};

static AnalogLevel lastStableLevel = ANALOG_UNKNOWN;
static AnalogLevel lastInstantLevel = ANALOG_UNKNOWN;
static TickType_t  lastChange       = 0;

static AnalogLevel decode_analog_level(uint16_t rawValue) {
    if (rawValue <= ANALOG_LEVEL_0_MAX) {
        return ANALOG_LEVEL_0;
    }
    if (rawValue <= ANALOG_LEVEL_1_MAX) {
        return ANALOG_LEVEL_1;
    }
    if (rawValue <= ANALOG_LEVEL_2_MAX) {
        return ANALOG_LEVEL_2;
    }
    return ANALOG_LEVEL_3;
}

void setup_analog_manager() {
    Serial.println("[INIT] Analog manager task created successfully");

    pinMode(ANALOG_GPIO_PIN, INPUT);

    analogReadResolution(12);
    analogSetPinAttenuation(ANALOG_GPIO_PIN, ADC_11db);

    const uint16_t bootRead = analogRead(ANALOG_GPIO_PIN);

    lastStableLevel = decode_analog_level(bootRead);
    lastInstantLevel = lastStableLevel;
    lastChange = xTaskGetTickCount();

    if (IS_DEBUG_MODE || IS_MONITOR_MODE || 1) {
        Serial.printf("[ANALOG] GPIO %d init raw=%u level=%d\n", ANALOG_GPIO_PIN, bootRead, (int)lastStableLevel);
    }
}

void analog_manager(void *pvParameters) {
    setup_analog_manager();

    while (1) {
        const uint16_t rawValue = analogRead(ANALOG_GPIO_PIN);
        const AnalogLevel level = decode_analog_level(rawValue);

        if (level != lastInstantLevel) {
            lastInstantLevel = level;
            lastChange = xTaskGetTickCount();
        }

        if ((xTaskGetTickCount() - lastChange) >= pdMS_TO_TICKS(ANALOG_DEBOUNCE_MS)) {
            if (level != lastStableLevel) {
                lastStableLevel = level;

                if (IS_DEBUG_MODE || IS_MONITOR_MODE || 1) {
                    const float voltage = (3.3f * (float)rawValue) / 4095.0f;
                    Serial.printf("[ANALOG] GPIO %d raw=%u voltage=%.2fV decoded=%d\n",
                                  ANALOG_GPIO_PIN,
                                  rawValue,
                                  voltage,
                                  (int)lastStableLevel);
                }
            }
        }

        vTaskDelay(pdMS_TO_TICKS(ANALOG_READ_DELAY_MS));
    }
}
