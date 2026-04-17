#include "global.h"

DHT20 dht20;

String WIFI_SSID = "Tri Tan Lau 1";
String WIFI_PASS = "0933007857";

String CORE_IOT_TOKEN;
String CORE_IOT_SERVER;
String CORE_IOT_PORT;

boolean isWifiConnected = false;

boolean is_LED_on		= true;
boolean is_NeoLED_on	= true;
boolean is_ws2812_on	= true;
boolean is_relay_on		= false;
boolean is_mini_fan_on	= false;

LcdScreen current_lcd_screen = SCREEN_ENV;

float glob_inference_result;

SensorData sensorData;

SemaphoreHandle_t xDHT20Semaphore           = NULL;
SemaphoreHandle_t xI2CMutex		            = NULL;
SemaphoreHandle_t xSensorDataMutex          = NULL;

SemaphoreHandle_t xBinarySemaphoreInternet  = NULL;

SemaphoreHandle_t xInferenceResultSemaphore = NULL;

SemaphoreHandle_t xLedStateSemaphore		= NULL;
SemaphoreHandle_t xNeoLedStateSemaphore		= NULL;
SemaphoreHandle_t xWS2812StateSemaphore	    = NULL;

SemaphoreHandle_t xRelayStateSemaphore		= NULL;
SemaphoreHandle_t xFanStateSemaphore		= NULL;