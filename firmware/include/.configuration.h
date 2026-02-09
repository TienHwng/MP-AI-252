#ifndef __CONFIGURATION_H__
#define __CONFIGURATION_H__

// clang-format off

// ===============================================================
//            Configuration Header File for MP-AI-252
// ===============================================================

// Mode Settings
#define IS_DEBUG_MODE               false
#define IS_SHOW_DHT20_STATUS        false
#define IS_SHOW_LED_STATUS          false
#define IS_SHOW_NEO_STATUS          false
#define IS_SHOW_LCD_STATUS          false
#define IS_SHOW_PAYLOAD             false
#define IS_SHOW_INFERENCE_RESULT    false

#define IS_SHOW_BOT_STATUS          false
#define IS_SHOW_SENSOR_LOG          false

// Time Delays (in milliseconds)
#define LED_BLINKY_DELAY_MS         1000
#define NEO_BLINKY_DELAY_MS         1000
#define TEMP_HUMI_DELAY_MS          1000
#define MAIN_SERVER_DELAY_MS        1000
#define TINY_ML_DELAY_MS            5000
#define POLL_FROM_SERVER_DELAY_MS   1000
#define CORE_IOT_DELAY_MS           10000

#define LED_READER_DELAY_MS         1000
#define HUMID_READER_DELAY_MS       1000

#define LONG_PRESS_MS               3000
#define DEBOUNCE_MS                 50

#define WIFI_CONNECT_TIMEOUT_MS     10000
#define WIFI_RETRY_INTERVAL_MS      5000
#define MQTT_RETRY_INTERVAL_MS      5000
#define SENSOR_LOG_DELAY_MS         2000

// GPIO Pins Definitions
#define BOOT_PIN                    0
#define LED_PIN                     48
#define NEO_LED_PIN                 45
#define NEO_LED_NUMBER              8

// I2C Pins
#define I2C_SDA_PIN                 11
#define I2C_SCL_PIN                 12

// clang-format on

#endif // __CONFIGURATION_H__