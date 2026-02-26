#include "led_display.h"

static unsigned long previousMillis	 = 0;
static unsigned long currentMillis	 = 0;
static int			 currentBlinkInterval = BLINK_NORMAL;
static boolean		 ledStateLocal		 = true;

// clang-format off
enum TempState {
	TEMP_COLD = 0,
	TEMP_IDEAL,
	TEMP_NORMAL,
	TEMP_HOT,
	TEMP_WARNING,
	TEMP_STATE_COUNT
};

int blinkInterval[TEMP_STATE_COUNT] = {
	BLINK_COLD,
	BLINK_IDEAL,
	BLINK_NORMAL,
	BLINK_HOT,
	BLINK_WARNING
};

String stringTempState[TEMP_STATE_COUNT] = {
	"COLD",      	// TEMP_COLD
	"IDEAL",     	// TEMP_IDEAL
	"NORMAL",    	// TEMP_NORMAL
	"HOT",			// TEMP_HOT
	"WARNING!"		// TEMP_WARNING
};

String stringBlinkState[TEMP_STATE_COUNT] = {
	"SLOW",			// TEMP_COLD
	"BREATH",		// TEMP_IDEAL
	"NORMAL",		// TEMP_NORMAL
	"FAST",			// TEMP_HOT
	"ALERT"			// TEMP_WARNING
};

int loopTimes[TEMP_STATE_COUNT] = {
	1,			// TEMP_COLD
	1,			// TEMP_IDEAL
	1,			// TEMP_NORMAL
	2,			// TEMP_HOT
	3   		// TEMP_WARNING
};
// clang-format on

TempState getTempState(float temp) {
	// The "low" temperature threshold should be lower.
	// But for testing purpose, it's set to < 25.0 C.
	if		(temp <= 20.0) 	return TEMP_COLD;
	else if (temp <= 25.0)	return TEMP_IDEAL;
	else if (temp <= 30.0)	return TEMP_NORMAL;
	else if (temp <= 35.0)	return TEMP_HOT;
	else					return TEMP_WARNING;
}

void led_display(void *pvParameters) {
	setup_led_display();

	while (1) {
		currentMillis			 = millis();
		static float currentTemp = 0.0f;

		// Take temperature from sensorData
		if (xSemaphoreTake(xSensorDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
			currentTemp = sensorData.temperature;
			xSemaphoreGive(xSensorDataMutex);
		}

		TempState state = getTempState(currentTemp);

		// Debug print
		if ((IS_DEBUG_MODE || IS_SHOW_LED_STATUS) &&
			(currentMillis - previousMillis >= LED_BLINKY_DELAY_MS)) {
			previousMillis = currentMillis;

			Serial.println("[LED] Temperature is " + stringTempState[state] + " -> blinking " + stringBlinkState[state] + " style");
		}

		if (xSemaphoreTake(xLedStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
			// Update is_LED_on from global variable
			ledStateLocal = is_LED_on;
			xSemaphoreGive(xLedStateSemaphore);
		}

		if (!ledStateLocal) {
			// If LED is turned off, ensure it's LOW
			digitalWrite(LED_PIN, LOW);
			vTaskDelay(pdMS_TO_TICKS(LED_BLINKY_DELAY_MS));
		}
		else {
			// LED toggle behavior
			for (int i = 0; i < loopTimes[state]; i++) {
				digitalWrite(LED_PIN, HIGH);
				vTaskDelay(pdMS_TO_TICKS(blinkInterval[state]));

				digitalWrite(LED_PIN, LOW);
				vTaskDelay(pdMS_TO_TICKS(blinkInterval[state]));
			}
		}
	}
}

void setup_led_display() {
	Serial.println("[INIT] LED Display task created successfully");

	pinMode(LED_PIN, OUTPUT);

	previousMillis = 0;
	currentMillis  = 0;
}