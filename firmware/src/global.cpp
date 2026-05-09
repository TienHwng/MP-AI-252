#include "global.h"

DHT20 dht20;

String WIFI_SSID = "Hung 2.4GHz";
String WIFI_PASS = "bat4glendi";

String CORE_IOT_TOKEN = "ehehehe";
String CORE_IOT_SERVER = "192.168.1.2";
String CORE_IOT_PORT = "1883";

boolean isWifiConnected = false;

boolean is_LED_on		= true;
uint16_t led_brightness	= 100;      // default normal LED PWM duty (0..1023)

boolean is_NeoLED_on	= true;
uint8_t strip_brightness	= 10;   // default strip brightness (0..255)

boolean is_ws2812_on	= true;
uint8_t ws2812_brightness	= 10;   // default brightness (0..255)

boolean is_mini_fan_on	= false;
int16_t fan_speed		= 500;      // default fan speed PWM duty (0..1023)

boolean is_relay_on		= true;

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
