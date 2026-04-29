#include "task_toogle_boot.h"

static bool s_isInAPMode = false;

static bool wifiModeHasApEnabled() {
	const wifi_mode_t mode = WiFi.getMode();
	return mode == WIFI_AP || mode == WIFI_AP_STA;
}

static void switchToApMode() {
	Webserver_stop();

	if (startAP()) {
		s_isInAPMode = true;
		Webserver_reconnect();
		Serial.println("[BOOT] Switched to AP mode.");
		return;
	}

	s_isInAPMode = false;
	Serial.println("[BOOT] Failed to switch to AP mode.");
}

static void switchToStaMode() {
	if (!wifiHasCredentials()) {
		Serial.println("[BOOT] Cannot switch to STA mode: missing WiFi credentials.");
		return;
	}

	Webserver_stop();
	stopAP();
	s_isInAPMode = false;

	if (startSTA(WIFI_CONNECT_TIMEOUT_MS)) {
		Serial.println("[BOOT] Switched to STA mode.");
	}
	else {
		Serial.println("[BOOT] STA mode requested, but WiFi connection failed.");
	}
}

void setup_toogle_boot() {
	pinMode(BOOT_PIN, INPUT_PULLUP);
	s_isInAPMode = wifiModeHasApEnabled();
	Serial.println("[INIT] Boot Button Monitor:");
	Serial.println("       Short press = AP mode");
	Serial.println("       Hold " + String(int(LONG_PRESS_MS / 1000)) + "s = STA mode");
}

void Task_Toogle_BOOT(void *pvParameters) {
	(void)pvParameters;
	setup_toogle_boot();

	bool		  buttonWasDown	   = false;
	bool		  longPressHandled = false;
	unsigned long pressStartTime   = 0;

	while (true) {
		bool		  buttonDown = (digitalRead(BOOT_PIN) == LOW);
		unsigned long now		 = millis();

		if (buttonDown && !buttonWasDown) {
			pressStartTime	 = now;
			longPressHandled = false;
		}

		if (buttonDown && buttonWasDown && !longPressHandled) {
			if (now - pressStartTime >= LONG_PRESS_MS) {
				longPressHandled = true;
				Serial.println("[BOOT] Long press detected.");
				switchToStaMode();
			}
		}

		if (!buttonDown && buttonWasDown) {
			unsigned long pressDuration = now - pressStartTime;

			if (!longPressHandled && pressDuration >= DEBOUNCE_MS &&
				pressDuration < LONG_PRESS_MS) {
				Serial.println("[BOOT] Short press detected.");
				switchToApMode();
			}
		}

		if (s_isInAPMode || webserver_isrunning) {
			Webserver_reconnect();
		}

		buttonWasDown = buttonDown;
		vTaskDelay(pdMS_TO_TICKS(50));
	}
}
