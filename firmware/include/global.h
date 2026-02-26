#ifndef __GLOBAL_H__
#define __GLOBAL_H__

#include ".configuration.h"

#include "DHT20.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include <Arduino.h>

typedef struct {
    float temperature;
    float humidity;
} SensorData;

extern SemaphoreHandle_t xBinarySemaphoreInternet;

extern SemaphoreHandle_t xInferenceResultSemaphore;
extern SemaphoreHandle_t xLedStateSemaphore;
extern SemaphoreHandle_t xNeoLedStateSemaphore;
extern SemaphoreHandle_t xDHT20Semaphore;
extern SemaphoreHandle_t xI2CMutex;
extern SemaphoreHandle_t xSensorDataMutex;

extern String WIFI_SSID;
extern String WIFI_PASS;

extern DHT20 dht20;

extern String CORE_IOT_TOKEN;
extern String CORE_IOT_SERVER;
extern String CORE_IOT_PORT;

extern boolean isWifiConnected;
extern boolean is_LED_on;
extern boolean is_NeoLED_on;

extern float glob_inference_result;

extern void sensor_dht20(void *pvParameters);

extern SensorData sensorData;

#endif // __GLOBAL_H__