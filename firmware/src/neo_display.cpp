#include "neo_display.h"

Adafruit_NeoPixel neoLED(NEO_LED_NUMBER, NEO_LED_PIN, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel WS2812(WS2812_NUMBER, WS2812_PIN, NEO_GRB + NEO_KHZ800);

static boolean neoLedStateLocal = true;
static boolean ws2812StateLocal = false;
static uint8_t ws2812RedLocal = 0;
static uint8_t ws2812GreenLocal = 64;
static uint8_t ws2812BlueLocal = 255;
static bool wsBtnStable = HIGH;
static bool wsBtnInstant = HIGH;
static TickType_t wsBtnLastChange = 0;

struct NeoHumidityColorStep {
    float upperBound;
    uint8_t red;
    uint8_t green;
    uint8_t blue;
    const char *label;
};

// clang-format off
static const NeoHumidityColorStep kNeoHumidityColorSteps[] = {
    {   30.0f,     255,    0,      0,      "RED"       },
    {   40.0f,     255,    127,    0,      "ORANGE"    },
    {   50.0f,     255,    255,    0,      "YELLOW"    },
    {   60.0f,     0,      255,    0,      "GREEN"     },
    {   70.0f,     0,      0,      255,    "BLUE"      },
    {   85.0f,     75,     0,      130,    "INDIGO"    },
    {   101.0f,    148,    0,      211,    "VIOLET"    },
    {   9999.0f,   255,    255,    255,    "WHITE"     }
};
// clang-format on

static String rgbToHex(uint8_t red, uint8_t green, uint8_t blue) {
    char buffer[8];
    snprintf(buffer, sizeof(buffer), "#%02X%02X%02X", red, green, blue);
    return String(buffer);
}

static size_t getNeoHumidityColorIndex(float humidity) {
    for (size_t i = 0; i < (sizeof(kNeoHumidityColorSteps) / sizeof(kNeoHumidityColorSteps[0])); ++i) {
        if (humidity < kNeoHumidityColorSteps[i].upperBound) {
            return i;
        }
    }

    return (sizeof(kNeoHumidityColorSteps) / sizeof(kNeoHumidityColorSteps[0])) - 1;
}

static void render_ws2812_state() {
    if (ws2812StateLocal) {
        WS2812.setBrightness(ws2812_brightness > 0 ? ws2812_brightness : 1);
        WS2812.fill(WS2812.Color(ws2812RedLocal, ws2812GreenLocal, ws2812BlueLocal));
    }
    else {
        WS2812.clear();
    }

    WS2812.show();
}

void update_NEO_LED(uint32_t index) {
    const size_t colorCount = sizeof(kNeoHumidityColorSteps) / sizeof(kNeoHumidityColorSteps[0]);
    const size_t safeIndex = (index < colorCount) ? index : (colorCount - 1);

    if (xSemaphoreTake(xNeoLedStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
        neoLedStateLocal = is_NeoLED_on;
        xSemaphoreGive(xNeoLedStateSemaphore);
    }
    
    if (!neoLedStateLocal) 	neoLED.fill(0);  // Turn off LEDs
    else {
        neoLED.setBrightness(strip_brightness > 0 ? strip_brightness : 1);
        const NeoHumidityColorStep &step = kNeoHumidityColorSteps[safeIndex];
        neoLED.fill(neoLED.Color(step.red, step.green, step.blue));
    }

    neoLED.show();

    // Debug print
    if (IS_DEBUG_MODE || IS_SHOW_NEO_STATUS) {
        Serial.println("[NEO LED] " + String(kNeoHumidityColorSteps[safeIndex].label));
    }
}

void neo_display(void *pvParameters) {
    setup_neo_display();

    while (1) {
        static float currentHumid = 0.0f;

        if (xSemaphoreTake(xDHT20Semaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
            currentHumid = sensorData.humidity;
            xSemaphoreGive(xDHT20Semaphore);
        }

        // Change NEO LED color based on humidity using the shared palette
        update_NEO_LED(getNeoHumidityColorIndex(currentHumid));

        vTaskDelay(pdMS_TO_TICKS(NEO_DISPLAY_DELAY_MS));
    }
}

void ws2812_set(bool on) {
    ws2812StateLocal = on;

    render_ws2812_state();

    if (IS_DEBUG_MODE || IS_SHOW_NEO_STATUS) {
        Serial.printf("[WS2812] %s brightness=%u color=%s\n",
                      on ? "ON" : "OFF",
                      ws2812_brightness,
                      ws2812_get_color_hex().c_str());
    }
}

void ws2812_set_color(int red, int green, int blue) {
    ws2812RedLocal = constrain(red, 0, 255);
    ws2812GreenLocal = constrain(green, 0, 255);
    ws2812BlueLocal = constrain(blue, 0, 255);

    render_ws2812_state();

    if (IS_DEBUG_MODE || IS_SHOW_NEO_STATUS) {
        Serial.printf("[WS2812] Color set to %s\n", ws2812_get_color_hex().c_str());
    }
}

void ws2812_set_brightness(uint8_t brightness) {
    ws2812_brightness = brightness;

    render_ws2812_state();

    if (IS_DEBUG_MODE || IS_SHOW_NEO_STATUS) {
        Serial.printf("[WS2812] Brightness set to %u\n", brightness);
    }
}

void ws2812_toggle() {
    ws2812_set(!ws2812StateLocal);
}

void neoLED_set_brightness(uint8_t brightness) {
    strip_brightness = brightness;

    neoLED.setBrightness(brightness > 0 ? brightness : 0);

    // Re-render ngay lập tức nếu đèn đang bật
    if (neoLedStateLocal) {
        neoLED.show();
    }

    if (IS_DEBUG_MODE || IS_SHOW_NEO_STATUS) {
        Serial.printf("[STRIP] Brightness set to %u\n", brightness);
    }
}

String ws2812_get_color_hex() {
    char buffer[8];
    snprintf(buffer, sizeof(buffer), "#%02X%02X%02X", ws2812RedLocal, ws2812GreenLocal, ws2812BlueLocal);
    return String(buffer);
}

String getNeoLedColorFromHumidity(float humidity) {
    const size_t safeIndex = getNeoHumidityColorIndex(humidity);
    const NeoHumidityColorStep &step = kNeoHumidityColorSteps[safeIndex];
    return rgbToHex(step.red, step.green, step.blue);
}

void setup_neo_display() {
    // TODO
    Serial.println("[INIT] Neo Display task created successfully");

    neoLED.begin();
    neoLED.setBrightness(strip_brightness);
    neoLED.show();

    pinMode(BUTTON_PIN, INPUT_PULLUP);

    WS2812.begin();
    WS2812.setBrightness(ws2812_brightness);
    // WS2812.clear();
    WS2812.show();
}
