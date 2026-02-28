#include "digital_manager.h"
#include "neo_display.h"

static bool output1State = false;
static bool output2State = false;
static bool output3State = false;

static bool lastStableRead   = HIGH;
static bool lastInstantRead  = HIGH;
static TickType_t lastChange = 0;

void setup_digital_manager() {
	Serial.println("[INIT] Digital manager task created successfully");

	pinMode(BUTTON_PIN, INPUT_PULLUP);
	pinMode(OUTPUT_GPIO_1, OUTPUT);
	pinMode(OUTPUT_GPIO_2, OUTPUT);
	pinMode(OUTPUT_GPIO_3, OUTPUT);

	digitalWrite(OUTPUT_GPIO_1, LOW);
	digitalWrite(OUTPUT_GPIO_2, LOW);
	digitalWrite(OUTPUT_GPIO_3, LOW);

	lastStableRead  = digitalRead(BUTTON_PIN);
	lastInstantRead = lastStableRead;
	lastChange      = xTaskGetTickCount();
}

void digital_manager(void *pvParameters) {
	setup_digital_manager();

	while (1) {
		const bool reading = digitalRead(BUTTON_PIN);

		if (reading != lastInstantRead) {
			lastInstantRead = reading;
			lastChange      = xTaskGetTickCount();
		}

		if ((xTaskGetTickCount() - lastChange) >= pdMS_TO_TICKS(DEBOUNCE_MS)) {
			if (reading != lastStableRead) {
				lastStableRead = reading;

				if (reading == LOW) {
					output1State = !output1State;
					output2State = !output2State;
					output3State = !output3State;

					digitalWrite(OUTPUT_GPIO_1, output1State ? HIGH : LOW);
					// digitalWrite(OUTPUT_GPIO_2, output2State ? HIGH : LOW);

                    ws2812_toggle();

					digitalWrite(OUTPUT_GPIO_3, output3State ? HIGH : LOW);


					if (IS_DEBUG_MODE) {
						Serial.printf("[BUTTON] GPIO %d -> %s, GPIO %d -> %s, GPIO %d -> %s\n",
									 OUTPUT_GPIO_1, output1State ? "ON" : "OFF",
									 OUTPUT_GPIO_2, output2State ? "ON" : "OFF",
									 OUTPUT_GPIO_3, output3State ? "ON" : "OFF");
					}
				}
			}
		}

		vTaskDelay(pdMS_TO_TICKS(10));
	}
}
