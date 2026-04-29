#include "digital_manager.h"
#include "neo_display.h"

typedef enum {
    FAN_DIR_STOP = 0,
    FAN_DIR_FORWARD,
    FAN_DIR_REVERSE
} FanDirection_t;

// Save previous values to only write when changed
static int16_t lastFanSpeed        = 0;
static FanDirection_t lastFanDirection   = FAN_DIR_STOP;
static uint8_t lastWs2812Brightness = 0;
static bool    lastWs2812On         = false;

static inline uint16_t clamp_pwm_10bit_abs(int16_t speed) {
    int32_t val = speed;

    if (val < 0) val = -val;
    if (val > 1023) val = 1023;

    return (uint16_t)val;
}

void setup_digital_manager() {
    Serial.println("[INIT] Digital manager task created successfully");

    // Initialize output pins according to digital port configuration
    pinMode(WS2812_PIN, OUTPUT);
    pinMode(IR_RECEIVE_PIN, OUTPUT);
    pinMode(RELAY_PIN, OUTPUT);

    digitalWrite(WS2812_PIN, LOW);
    digitalWrite(IR_RECEIVE_PIN, LOW);
    digitalWrite(RELAY_PIN, LOW);

    pinMode(MINI_FAN_PIN, OUTPUT);
    pinMode(DIGITAL_PORT_3_SUB_PIN, OUTPUT);

    // Global PWM configuration for all analogWrite operations
    analogWriteResolution(10);     // 0..1023
    analogWriteFrequency(20000);   // 20 kHz

    analogWrite(MINI_FAN_PIN, 100);
    // analogWrite(DIGITAL_PORT_3_SUB_PIN, 0);
}

void fan_set_speed(int16_t speed) {
    uint16_t pwm = clamp_pwm_10bit_abs(speed);

    fan_speed      = speed;
    is_mini_fan_on = (speed != 0);

    if (speed > 0) {
        // Forward rotation
        // analogWrite(DIGITAL_PORT_3_SUB_PIN, 0);
        analogWrite(MINI_FAN_PIN, pwm);

        if (IS_DEBUG_MODE || IS_SHOW_DIGITAL_STATUS) {
            Serial.printf("[FAN] Forward | Speed = %d | PWM = %u / 1023\n", speed, pwm);
        }
    }
    else if (speed < 0) {
        // Reverse rotation
        analogWrite(MINI_FAN_PIN, 0);
        // analogWrite(DIGITAL_PORT_3_SUB_PIN, pwm);

        if (IS_DEBUG_MODE || IS_SHOW_DIGITAL_STATUS) {
            Serial.printf("[FAN] Reverse | Speed = %d | PWM = %u / 1023\n", speed, pwm);
        }
    }
    else {
        // Stop
        analogWrite(MINI_FAN_PIN, 0);
        // analogWrite(DIGITAL_PORT_3_SUB_PIN, 0);

        if (IS_DEBUG_MODE || IS_SHOW_DIGITAL_STATUS) {
            Serial.println("[FAN] Stop");
        }
    }
}

void digital_manager(void *pvParameters) {
    setup_digital_manager();

    while (1) {
        // ==========================================
        // CONTROL DEVICES BASED ON GLOBAL VARIABLES
        //    (Set from MQTT or other tasks)
        // ==========================================

        // --- WS2812: Check both on/off and brightness states ---
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

        // --- Mini fan: Adjust speed using PWM ---
        if (xSemaphoreTake(xFanStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
            int16_t curSpeed = fan_speed;
            xSemaphoreGive(xFanStateSemaphore);

            if (curSpeed != lastFanSpeed) {
                fan_set_speed(curSpeed);
                lastFanSpeed = curSpeed;
            }
        }

        // --- Relay: Keep simple on/off control ---
        if (xSemaphoreTake(xRelayStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
            digitalWrite(RELAY_PIN, is_relay_on ? HIGH : LOW);
            xSemaphoreGive(xRelayStateSemaphore);
        }

        vTaskDelay(pdMS_TO_TICKS(30));
    }
}