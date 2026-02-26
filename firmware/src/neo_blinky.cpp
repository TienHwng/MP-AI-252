#include "neo_blinky.h"

Adafruit_NeoPixel strip(NEO_LED_NUMBER, NEO_LED_PIN, NEO_GRB + NEO_KHZ800);

static boolean neoLedStateLocal = true;

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
	else					strip.fill(color_map[index]);

	strip.show();

	// Debug print
	if (IS_DEBUG_MODE || IS_SHOW_NEO_STATUS) {
		Serial.println("[NEO LED] " + String(string_color[index]));
	}
}

void neo_blinky(void *pvParameters) {
	setup_neo_blinky();

	while (1) {
		static float currentHumid = 0.0f;

		if (xSemaphoreTake(xSensorDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
			currentHumid = sensorData.humidity;
			xSemaphoreGive(xSensorDataMutex);
		}

		// Change NEO LED color based on humidity
		if 		(currentHumid <   30) 	update_NEO_LED(0);
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

		vTaskDelay(pdMS_TO_TICKS(NEO_BLINKY_DELAY_MS));
	}
}

void setup_neo_blinky() {
	// TODO
	Serial.println("[INIT] Neo Blinky task created successfully");

	strip.begin();
	strip.setBrightness(100);
	strip.show();
}
