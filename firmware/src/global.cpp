#include "global.h"

DHT20 dht20;

String WIFI_SSID = "Hung 2.4GHz";
String WIFI_PASS = "bat4glendi";

String CORE_IOT_TOKEN;
String CORE_IOT_SERVER;
String CORE_IOT_PORT;

boolean isWifiConnected = false;

boolean is_LED_on		= true;
boolean is_NeoLED_on	= true;
uint8_t strip_brightness	= 10;   // default strip brightness (0..255)
boolean is_ws2812_on	= true;
uint8_t ws2812_brightness	= 10;   // default brightness (0..255)

boolean is_relay_on		= true;

boolean is_mini_fan_on	= true;
int16_t fan_speed		= 500;     // default fan speed (0..4095, PWM duty)

LcdScreen current_lcd_screen = SCREEN_ENV;

float glob_inference_result;

SensorData sensorData;

SemaphoreHandle_t xLCDSemaphore		        = NULL;

SemaphoreHandle_t xDHT20Semaphore           = NULL;
SemaphoreHandle_t xLightSemaphore           = NULL;
SemaphoreHandle_t xMQ2Semaphore             = NULL;

SemaphoreHandle_t xBinarySemaphoreInternet  = NULL;

SemaphoreHandle_t xInferenceResultSemaphore = NULL;

SemaphoreHandle_t xLedStateSemaphore		= NULL;
SemaphoreHandle_t xNeoLedStateSemaphore		= NULL;
SemaphoreHandle_t xWS2812StateSemaphore	    = NULL;

SemaphoreHandle_t xRelayStateSemaphore		= NULL;
SemaphoreHandle_t xFanStateSemaphore		= NULL;