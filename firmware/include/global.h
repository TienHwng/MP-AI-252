#ifndef __GLOBAL_H__
#define __GLOBAL_H__

#include ".configuration.h"

#include "DHT20.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include <Arduino.h>
#include <WiFi.h>

typedef struct {
    float temperature;
    float humidity;
    float light;
    float gas;
} SensorData;

enum LcdScreen {
    SCREEN_ENV = 0,
    SCREEN_ACTUATORS,
    SCREEN_COUNT
};

extern LcdScreen current_lcd_screen;

extern SemaphoreHandle_t xBinarySemaphoreInternet;

extern SemaphoreHandle_t xInferenceResultSemaphore;

extern SemaphoreHandle_t xLedStateSemaphore;
extern SemaphoreHandle_t xNeoLedStateSemaphore;
extern SemaphoreHandle_t xWS2812StateSemaphore;

extern SemaphoreHandle_t xRelayStateSemaphore;
extern SemaphoreHandle_t xFanStateSemaphore;

extern SemaphoreHandle_t xLCDSemaphore;

extern SemaphoreHandle_t xDHT20Semaphore;
extern SemaphoreHandle_t xLightSemaphore;
extern SemaphoreHandle_t xMQ2Semaphore;

extern String WIFI_SSID;
extern String WIFI_PASS;
extern WiFiClient espClient;

extern DHT20 dht20;

extern String CORE_IOT_TOKEN;
extern String CORE_IOT_SERVER;
extern String CORE_IOT_PORT;

extern boolean isWifiConnected;
extern boolean is_LED_on;
extern boolean is_NeoLED_on;
extern uint8_t strip_brightness;    // 0..255, NeoPixel strip brightness
extern boolean is_ws2812_on;
extern uint8_t ws2812_brightness;   // 0..255, 0 = off

extern boolean is_relay_on;

extern boolean is_mini_fan_on;
extern uint8_t fan_speed;           // 0..255, 0 = off (PWM duty)

extern float glob_inference_result;

extern void sensor_dht20(void *pvParameters);

extern SensorData sensorData;

#endif // __GLOBAL_H__
