#ifndef __CONFIGURATION_H__
#define __CONFIGURATION_H__

// clang-format off

// ===============================================================
//            Configuration Header File for MP-AI-252
// ===============================================================

// ----- General Settings -----
// Mode Settings
#define IS_DEBUG_MODE               false
#define IS_MONITOR_MODE             false
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
#define NEO_DISPLAY_DELAY_MS        1000
#define TEMP_HUMI_DELAY_MS          1000
#define MAIN_SERVER_DELAY_MS        1000
#define TINY_ML_DELAY_MS            5000
#define POLL_FROM_SERVER_DELAY_MS   1000
#define CORE_IOT_DELAY_MS           10000

#define LED_READER_DELAY_MS         1000
#define HUMID_READER_DELAY_MS       1000

#define LONG_PRESS_MS               3000
#define DEBOUNCE_MS                 50

#define ANALOG_READ_DELAY_MS        10
#define ANALOG_DEBOUNCE_MS          80

#define WIFI_CONNECT_TIMEOUT_MS     10000
#define WIFI_RETRY_INTERVAL_MS      5000
#define MQTT_RETRY_INTERVAL_MS      5000
#define SENSOR_LOG_DELAY_MS         2000
// ----- END General Settings -----



// ----- Board default ports mapping -----
// Digital Ports
#define DIGITAL_PORT_1_PIN          18      // D9
#define DIGITAL_PORT_2_PIN          10      // D7
#define DIGITAL_PORT_3_PIN          8       // D5
#define DIGITAL_PORT_4_PIN          6       // D3

// Analog Ports
#define ANALOG_PORT_1_PIN           3       // A3
#define ANALOG_PORT_2_PIN           4       // A2
#define ANALOG_PORT_3_PIN           5       // A1
#define ANALOG_PORT_4_PIN           6       // A0

// I2C Pins
#define I2C_SDA_PIN                 11      // A4
#define I2C_SCL_PIN                 12      // A5
// ----- END Board default ports mapping -----



// ----- GPIO Pins Definitions -----
// Buttons
#define BOOT_PIN                    0
#define BUTTON_PIN                  47

// Grove's port devices
#define WS2812_PIN                  DIGITAL_PORT_1_PIN
#define MINI_FAN_PIN                DIGITAL_PORT_2_PIN
#define IR_RECEIVE_PIN              DIGITAL_PORT_4_PIN
#define RELAY_PIN                   DIGITAL_PORT_3_PIN

#define ANALOG_GPIO_PIN             ANALOG_PORT_2_PIN
#define LIGHT_SENSOR_PIN            ANALOG_PORT_2_PIN
#define MQ2_SENSOR_PIN              ANALOG_PORT_3_PIN
#define SOIL_MOISTURE_PIN           ANALOG_PORT_4_PIN

// GPIO ports
#define LED_PIN                     48

#define NEO_LED_PIN                 45
#define NEO_LED_NUMBER              8

#define WS2812_NUMBER               4
// ----- END GPIO Pins Definitions -----



// ----- Thresholds & Constants -----
#define ANALOG_LEVEL_0_MAX          900
#define ANALOG_LEVEL_1_MAX          1900
#define ANALOG_LEVEL_2_MAX          3000
// ----- END Thresholds & Constants -----



typedef enum {
    DIGITAL_PORT_1 = 0,
    DIGITAL_PORT_2,
    DIGITAL_PORT_3,
    DIGITAL_PORT_4,
    
    NUM_DEVICES 
} DeviceID;

// clang-format on

#endif // __CONFIGURATION_H__