#include "LCD_display.h"

// OhStem LCD I2C address 0x21 == 33
static LiquidCrystal_I2C lcd(0x21, 16, 2);

// HShop LCD I2C address 0x27 == 39
// static LiquidCrystal_I2C lcd(0x27, 16, 2);

// clang-format off

// Timing constants for LCD update
static const TickType_t LCD_REFRESH_TICKS    = pdMS_TO_TICKS(200);  // Refresh parameters 0.2s/cycle
static const TickType_t AUTO_ROTATE_TICKS    = pdMS_TO_TICKS(3000); // Auto-rotate page every 3 seconds
static const TickType_t MANUAL_TIMEOUT_TICKS = pdMS_TO_TICKS(5000); // 5s after button press will auto-rotate page again

enum EnvStatus {
    ENV_COLD = 0,
    ENV_IDEAL,
    ENV_NORMAL,
    ENV_HOT,
    ENV_WARNING,
    ENV_STATUS_COUNT
};

static String status_LCD[ENV_STATUS_COUNT] = {
    "COLD",
    "IDEAL",
    "NORMAL",
    "HOT",
    "WARNING!"
};

static EnvStatus getEnvStatus(float temperature, float humidity) {
    if      ((                    temperature <= 20) && (60 < humidity && humidity <= 75))  return ENV_COLD;
    else if ((20 < temperature && temperature <= 25) && (60 < humidity && humidity <= 75))  return ENV_IDEAL;
    else if ((25 < temperature && temperature <= 30) && (60 < humidity && humidity <= 80))  return ENV_NORMAL;
    else if ((30 < temperature && temperature <= 35) && (60 < humidity && humidity <= 80))  return ENV_HOT;
    else                                                                                    return ENV_WARNING;
}

// clang-format on

static inline const char *onoff(bool x) { return x ? "ON" : "OFF"; }

static void lcd_print2(const char *l0, const char *l1) {
	char line0[17], line1[17];
	snprintf(line0, sizeof(line0), "%-16.16s", l0 ? l0 : "");
	snprintf(line1, sizeof(line1), "%-16.16s", l1 ? l1 : "");

	lcd.setCursor(0, 0);
	lcd.print(line0);
	lcd.setCursor(0, 1);
	lcd.print(line1);
}

// Graphics rendering function (Gather sensor data and output as string)
static void render_screen(LcdScreen screen, bool manualMode) {
	float t = NAN, h = NAN;
	if (xSemaphoreTake(xDHT20Semaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
		t = sensorData.temperature;
		h = sensorData.humidity;
		xSemaphoreGive(xDHT20Semaphore);
	}

	bool l1 = is_LED_on;
	bool l2 = is_NeoLED_on;

	if (xLedStateSemaphore && xSemaphoreTake(xLedStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
		l1 = is_LED_on;
		xSemaphoreGive(xLedStateSemaphore);
	}

	if (xNeoLedStateSemaphore && xSemaphoreTake(xNeoLedStateSemaphore, pdMS_TO_TICKS(10)) == pdTRUE) {
		l2 = is_NeoLED_on;
		xSemaphoreGive(xNeoLedStateSemaphore);
	}

	const char modeChar = manualMode ? 'M' : 'A';
	char	   l0[32], l1buf[32];

	if (screen == SCREEN_ENV) {
		if (isnan(t) || isnan(h)) {
			snprintf(l0, sizeof(l0), "%c Sensor waiting", modeChar);
			snprintf(l1buf, sizeof(l1buf), "No data yet");
		}
		else {
			EnvStatus st = getEnvStatus(t, h);
			snprintf(l0, sizeof(l0), "%c T:%4.1f H:%2.0f%%", modeChar, t, h);
			snprintf(l1buf, sizeof(l1buf), "St:%-12.12s", status_LCD[st].c_str());
		}
	}
	else if (screen == SCREEN_ACTUATORS) {
		snprintf(l0, sizeof(l0), "%c L1:%s L2:%s", modeChar, onoff(l1), onoff(l2));
		snprintf(l1buf, sizeof(l1buf), "FAN:%s", onoff(false));
	}
	else {
		snprintf(l0, sizeof(l0), "%c Unknown screen", modeChar);
		snprintf(l1buf, sizeof(l1buf), " ");
	}

	if (xSemaphoreTake(xLCDSemaphore, pdMS_TO_TICKS(50)) == pdTRUE) {
		lcd_print2(l0, l1buf);
		xSemaphoreGive(xLCDSemaphore);
	}
}

void setup_LCD_display() {
	Serial.println("[INIT] LCD Display task created successfully");

	if (xSemaphoreTake(xLCDSemaphore, pdMS_TO_TICKS(200)) == pdTRUE) {
		lcd.begin();
		lcd.backlight();
		lcd_print2("LCD ready", "Auto rotate...");
		xSemaphoreGive(xLCDSemaphore);
	}
	else {
		Serial.println("[WARN] LCD init skipped (I2C mutex timeout)");
	}
}

// LCD MAIN THREAD - COMPLETELY CLEANED UP
void LCD_display(void *pvParameters) {
	(void)pvParameters;
	setup_LCD_display();

	LcdScreen rendered_screen = SCREEN_ENV; // Variable storing the "currently being rendered" page
	bool	  manualMode	  = false;

	TickType_t lastRotate		= xTaskGetTickCount();
	TickType_t lastRefresh		= xTaskGetTickCount();
	TickType_t lastUserInteract = 0;

	while (1) {
		TickType_t now = xTaskGetTickCount();

		// 1. If digital_manager changes page (button press), LCD detects difference and re-renders immediately
		if (current_lcd_screen != rendered_screen) {
			rendered_screen	 = current_lcd_screen;
			manualMode		 = true; // Enable manual mode (M)
			lastUserInteract = now;	 // Mark the timestamp of last user interaction
			lastRotate		 = now;	 // Reset auto-rotate counter
			render_screen(rendered_screen, manualMode);
		}

		// 2. Timeout: After manual interaction, if no touch for 5s (MANUAL_TIMEOUT_TICKS) -> Switch to auto
		// rotate (A)
		if (manualMode && (now - lastUserInteract) > MANUAL_TIMEOUT_TICKS) {
			manualMode = false;
			lastRotate = now;
			render_screen(rendered_screen, manualMode);
		}

		// 3. Auto-rotate page (only runs in Auto mode)
		if (!manualMode && (now - lastRotate) > AUTO_ROTATE_TICKS) {
			lastRotate = now;
			// Change global variable, next loop iteration (item 1) will detect and update
			current_lcd_screen = (LcdScreen)((current_lcd_screen + 1) % SCREEN_COUNT);
		}

		// 4. Update parameters (Temperature/Humidity) every 200ms without rotating page
		if ((now - lastRefresh) > LCD_REFRESH_TICKS) {
			lastRefresh = now;
			render_screen(rendered_screen, manualMode);
		}

		// LCD no longer needs to check button, can sleep peacefully 50ms (save CPU)
		vTaskDelay(pdMS_TO_TICKS(50));
	}
}