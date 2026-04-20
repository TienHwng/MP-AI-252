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

#define IS_SHOW_MQ2_STATUS          false
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
#define GAS_MONITOR_DELAY_MS        2000
// ----- END General Settings -----



// ----- Board default ports mapping -----
// Digital Ports
#define DIGITAL_PORT_1_PIN          18      // D9
#define DIGITAL_PORT_2_PIN          10      // D7
#define DIGITAL_PORT_3_PIN          8       // D5
#define DIGITAL_PORT_4_PIN          6       // D3

// Analog Ports
#define ANALOG_PORT_1_PIN           4       // A3
#define ANALOG_PORT_2_PIN           3       // A2
#define ANALOG_PORT_3_PIN           2       // A1
#define ANALOG_PORT_4_PIN           1       // A0

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
#define MINI_FAN_PIN                DIGITAL_PORT_3_PIN
#define RELAY_PIN                   DIGITAL_PORT_4_PIN
#define IR_RECEIVE_PIN              DIGITAL_PORT_2_PIN

#define ANALOG_GPIO_PIN             ANALOG_PORT_1_PIN
#define LIGHT_SENSOR_PIN            ANALOG_PORT_2_PIN
#define MQ2_SENSOR_PIN              ANALOG_PORT_3_PIN
#define SOIL_MOISTURE_PIN           ANALOG_PORT_4_PIN

// GPIO ports
#define LED_PIN                     48

#define NEO_LED_PIN                 45
#define NEO_LED_NUMBER              8

#define WS2812_NUMBER               4

// Fan PWM (LEDC) settings
#define FAN_PWM_CHANNEL             0
#define FAN_PWM_FREQ                25000   // 25 kHz
#define FAN_PWM_RESOLUTION          12       // 8-bit -> 0..255
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



// Analog gas sensor (MQ2) pin
#define MQ2_ANALOG_PIN              2

// MQ2 thresholds (ppm)
#define MQ2_WARN_PPM_DEFAULT        500.0f
#define MQ2_CRIT_PPM_DEFAULT        1000.0f

// MQ2 constants (based on datasheet)
#define MQ2_RL_KOHM                 1.0f      // Load resistor value in kOhm
#define MQ2_CLEAN_AIR_FACTOR        9.83f     // Rs/R0 ratio in clean air
#define MQ2_CURVE_A                 565.46f   // Curve constant A (LPG/Smoke)
#define MQ2_CURVE_B                 -2.203f   // Curve constant B
#define MQ2_ADC_MAX                 4095.0f   // 12-bit ADC max value
#define MQ2_VREF                    3.3f      // Reference voltage for ADC
#define MQ2_DEFAULT_R0              10.0f     // Fallback R0 if calibration fails (kOhm)
#define MQ2_CALIBRATION_SAMPLES     50        // Samples for R0 calibration
#define MQ2_CALIBRATION_DELAY_MS    50        // Delay between calibration samples


// clang-format on

#endif // __CONFIGURATION_H__