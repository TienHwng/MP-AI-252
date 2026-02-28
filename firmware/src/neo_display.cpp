#include "neo_display.h"

Adafruit_NeoPixel strip(NEO_LED_NUMBER, NEO_LED_PIN, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel WS2812(4, OUTPUT_GPIO_2, NEO_GRB + NEO_KHZ800);

static boolean neoLedStateLocal = true;
static boolean ws2812StateLocal = false;
static bool wsBtnStable = HIGH;
static bool wsBtnInstant = HIGH;
static TickType_t wsBtnLastChange = 0;

// ---- Bảng màu ----
uint32_t color_map[] = {
    strip.Color(	255, 	0, 		0	),      // Red 		- Đỏ
    strip.Color(	255, 	127, 	0	),    	// Orange 	- Cam
    strip.Color(	255, 	255, 	0	),    	// Yellow 	- Vàng
    strip.Color(	0, 		255,	0	),      // Green 	- Lục
    strip.Color(	0, 		0, 		255	),      // Blue 	- Lam
    strip.Color(	75, 	0, 		130	),     	// Indigo 	- Chàm
    strip.Color(	148, 	0, 		211	),     	// Violet 	- Tím
	strip.Color(	255, 	255, 	255	)   	// White 	- Trắng
	// strip.Color(	0, 		0, 		0	)		// Black 	- Đen
};

String string_color[] = {
    "RED",
    "ORANGE",
    "YELLOW",
    "GREEN",
    "BLUE",
    "INDIGO",
    "VIOLET",
    "WHITE"
};

void update_NEO_LED(uint32_t index) {
    if (xSemaphoreTake(xNeoLedStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
        neoLedStateLocal = is_NeoLED_on;
        xSemaphoreGive(xNeoLedStateSemaphore);
    }
    
    if (!neoLedStateLocal) 	strip.fill(0);  // Turn off LEDs
    else				    strip.fill(color_map[index]);

    strip.show();

    // Debug print
    if (IS_DEBUG_MODE || IS_SHOW_NEO_STATUS) {
        Serial.println("[NEO LED] " + String(string_color[index]));
    }
}

void neo_display(void *pvParameters) {
    setup_neo_display();

    while (1) {
        static float currentHumid = 0.0f;

        if (xSemaphoreTake(xSensorDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
            currentHumid = sensorData.humidity;
            xSemaphoreGive(xSensorDataMutex);
        }

        // Change NEO LED color based on humidity
        if 	(currentHumid <   30) 	update_NEO_LED(0);
        else if (currentHumid <   40) 	update_NEO_LED(1);
        else if (currentHumid <   50) 	update_NEO_LED(2);
        else if (currentHumid <   60) 	update_NEO_LED(3);
        else if (currentHumid <   70) 	update_NEO_LED(4);
        else if (currentHumid <   85) 	update_NEO_LED(5);
        else if (currentHumid <= 100) 	update_NEO_LED(6);
        else {
            // White color for error
            strip.fill(color_map[7]);
            if (IS_DEBUG_MODE || IS_SHOW_NEO_STATUS) {
                Serial.println("[LED] " + String(string_color[7]) + " - ERROR");
            }
        }

        vTaskDelay(pdMS_TO_TICKS(NEO_DISPLAY_DELAY_MS));
    }
}

void ws2812_set(bool on) {
    ws2812StateLocal = on;

    if (on) {
        WS2812.fill(WS2812.Color(0, 64, 255)); // cool blue when ON
        WS2812.setPixelColor(0, WS2812.Color(255, 0, 0)); // Red for pixel 0
    }
    else {
        WS2812.clear();
    }

    WS2812.show();


    if (IS_DEBUG_MODE || IS_SHOW_NEO_STATUS) {
        Serial.printf("[WS2812] %s\n", on ? "ON" : "OFF");
    }
}

void ws2812_toggle() {
    ws2812_set(!ws2812StateLocal);
}

void setup_neo_display() {
    // TODO
    Serial.println("[INIT] Neo Display task created successfully");

    strip.begin();
    strip.setBrightness(100);
    strip.show();

    pinMode(BUTTON_PIN, INPUT_PULLUP);

    WS2812.begin();
    WS2812.setBrightness(100);
    WS2812.clear();
    WS2812.show();
}
