#include "analog_manager.h"

void setup_analog_manager() {
    Serial.println("[INIT] Analog manager task created successfully");

    pinMode(LIGHT_SENSOR_PIN, INPUT);

    analogReadResolution(12);
    analogSetPinAttenuation(LIGHT_SENSOR_PIN, ADC_11db);

    const uint16_t bootRead = analogRead(LIGHT_SENSOR_PIN);

    if (IS_DEBUG_MODE || IS_SHOW_ANALOG_STATUS) {
        Serial.printf("[ANALOG] GPIO %d init raw=%u\n", LIGHT_SENSOR_PIN, bootRead);
    }
}

void analog_manager(void *pvParameters) {
    setup_analog_manager();

    while (1) {
        const uint16_t rawValue = analogRead(LIGHT_SENSOR_PIN);
        const float lightPercent = ((float)rawValue / 4095.0f) * 100.0f;

        if (xLightSemaphore != NULL &&
            xSemaphoreTake(xLightSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
            sensorData.light = lightPercent;
            xSemaphoreGive(xLightSemaphore);
        }

        if (IS_DEBUG_MODE || IS_SHOW_ANALOG_STATUS) {
            const float voltage = (3.3f * (float)rawValue) / 4095.0f;
            Serial.printf("[ANALOG] GPIO %d raw=%u voltage=%.2fV light=%.2f%%\n",
                          LIGHT_SENSOR_PIN,
                          rawValue,
                          voltage,
                          lightPercent);
        }

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
