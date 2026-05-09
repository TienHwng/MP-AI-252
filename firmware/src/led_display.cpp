#include "led_display.h"

static unsigned long previousMillis	 = 0;
static unsigned long currentMillis	 = 0;
static int			 currentBlinkInterval = BLINK_NORMAL;
static boolean		 ledStateLocal		 = true;
static uint16_t		 ledBrightnessLocal	 = 0;

static inline uint16_t clamp_pwm_10bit(uint16_t brightness) {
	return brightness > 1023 ? 1023 : brightness;
}

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
	1,				// TEMP_COLD
	1,				// TEMP_IDEAL
	1,				// TEMP_NORMAL
	2,				// TEMP_HOT
	3   			// TEMP_WARNING
};

TempState getTempState(float temp) {
	// The "low" temperature threshold should be lower.
	// But for testing purpose, it's set to < 25.0 C.
	if		(temp <= 20.0) 	return TEMP_COLD;
	else if (temp <= 25.0)	return TEMP_IDEAL;
	else if (temp <= 30.0)	return TEMP_NORMAL;
	else if (temp <= 35.0)	return TEMP_HOT;
	else					return TEMP_WARNING;
}
// clang-format on

void led_display(void *pvParameters) {
	setup_led_display();

	while (1) {
		currentMillis			 = millis();
		static float currentTemp = 0.0f;

		// Take temperature from sensorData
		if (xSemaphoreTake(xDHT20Semaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
			currentTemp = sensorData.temperature;
			xSemaphoreGive(xDHT20Semaphore);
		}

		TempState state = getTempState(currentTemp);

		// Debug print
		if ((IS_DEBUG_MODE || IS_SHOW_LED_STATUS) &&
			(currentMillis - previousMillis >= LED_BLINKY_DELAY_MS)) {
			previousMillis = currentMillis;

			Serial.println("[LED] Temperature is " + stringTempState[state] + " -> blinking " + stringBlinkState[state] + " style");
		}

		if (xSemaphoreTake(xLedStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
			// Update LED state from global variables
			ledStateLocal = is_LED_on;
			ledBrightnessLocal = clamp_pwm_10bit(led_brightness);
			xSemaphoreGive(xLedStateSemaphore);
		}

		if (!ledStateLocal || ledBrightnessLocal == 0) {
			// If LED is turned off, ensure it's LOW
			analogWrite(LED_PIN, 0);
			vTaskDelay(pdMS_TO_TICKS(LED_BLINKY_DELAY_MS));
		}
		else {
			// LED toggle behavior
			for (int i = 0; i < loopTimes[state]; i++) {
				analogWrite(LED_PIN, ledBrightnessLocal);
				vTaskDelay(pdMS_TO_TICKS(blinkInterval[state]));

				analogWrite(LED_PIN, 0);
				vTaskDelay(pdMS_TO_TICKS(blinkInterval[state]));
			}
		}
	}
}

void led_set_brightness(uint16_t brightness) {
	uint16_t pwm = clamp_pwm_10bit(brightness);

	if (xSemaphoreTake(xLedStateSemaphore, portMAX_DELAY) == pdTRUE) {
		led_brightness = pwm;
		is_LED_on	   = (pwm > 0);
		xSemaphoreGive(xLedStateSemaphore);
	}

	analogWrite(LED_PIN, pwm);

	if (IS_DEBUG_MODE || IS_SHOW_LED_STATUS) {
		Serial.printf("[LED] Brightness = %u / 1023\n", pwm);
	}
}

void setup_led_display() {
	Serial.println("[INIT] LED Display task created successfully");

	pinMode(LED_PIN, OUTPUT);
	analogWriteResolution(10);     // 0..1023
	analogWriteFrequency(20000);   // 20 kHz
	analogWrite(LED_PIN, 0);

	previousMillis = 0;
	currentMillis  = 0;
}
