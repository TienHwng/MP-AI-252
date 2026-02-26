#include "global.h"

DHT20 dht20;

String WIFI_SSID;
String WIFI_PASS;

String CORE_IOT_TOKEN;
String CORE_IOT_SERVER;
String CORE_IOT_PORT;

boolean isWifiConnected = false;
boolean is_LED_on		= true;
boolean is_NeoLED_on	= true;

float glob_inference_result;

SensorData sensorData;

SemaphoreHandle_t xDHT20Semaphore           = NULL;
SemaphoreHandle_t xI2CMutex		            = NULL;
SemaphoreHandle_t xSensorDataMutex          = NULL;

SemaphoreHandle_t xBinarySemaphoreInternet  = NULL;

SemaphoreHandle_t xInferenceResultSemaphore = NULL;
SemaphoreHandle_t xLedStateSemaphore		= NULL;
SemaphoreHandle_t xNeoLedStateSemaphore		= NULL;