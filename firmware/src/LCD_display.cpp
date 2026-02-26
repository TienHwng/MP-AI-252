#include "LCD_display.h"

// OhStem LCD I2C address 0x21 == 33
static LiquidCrystal_I2C lcd(33, 16, 2);

// HShop LCD I2C address 0x27 == 39
// static LiquidCrystal_I2C lcd(0x27, 16, 2);

extern AsyncWebSocket ws;

// ====== Button config ======
#ifndef LCD_BTN_PIN
#define LCD_BTN_PIN 0
#endif
#ifndef LCD_BTN_ACTIVE_LOW
#define LCD_BTN_ACTIVE_LOW 1
#endif

// ====== Timing ======
static const TickType_t LCD_REFRESH_TICKS    = pdMS_TO_TICKS(200);
static const TickType_t AUTO_ROTATE_TICKS    = pdMS_TO_TICKS(2000);
static const TickType_t MANUAL_TIMEOUT_TICKS = pdMS_TO_TICKS(5000);
static const TickType_t BTN_DEBOUNCE_TICKS   = pdMS_TO_TICKS(50);

enum EnvStatus {
    ENV_COLD = 0,
    ENV_IDEAL,
    ENV_NORMAL,
    ENV_HOT,
    ENV_WARNING,
    ENV_STATUS_COUNT
};

static String status_LCD[ENV_STATUS_COUNT] = {
    "COLD",    // ENV_COLD
    "IDEAL",   // ENV_IDEAL
    "NORMAL",  // ENV_NORMAL
    "HOT",     // ENV_HOT
    "WARNING!" // ENV_WARNING
};

static EnvStatus getEnvStatus(float temperature, float humidity) {
    if      ((temperature <= 20) && (60 < humidity && humidity <= 75))                      return ENV_COLD;
    else if ((20 < temperature && temperature <= 25) && (60 < humidity && humidity <= 75))  return ENV_IDEAL;
    else if ((25 < temperature && temperature <= 30) && (60 < humidity && humidity <= 80))  return ENV_NORMAL;
    else if ((30 < temperature && temperature <= 35) && (60 < humidity && humidity <= 80))  return ENV_HOT;
    else                                                                                    return ENV_WARNING;
}

enum LcdScreen {
    SCREEN_ENV = 0,
    SCREEN_ACTUATORS,
    SCREEN_COUNT
};

static inline const char *onoff(bool x) { return x ? "ON" : "OFF"; }

// In 2 lines of 16 chars (no clear to reduce flicker)
static void lcd_print2(const char *l0, const char *l1) {
    char line0[17], line1[17];
    snprintf(line0, sizeof(line0), "%-16.16s", l0 ? l0 : "");
    snprintf(line1, sizeof(line1), "%-16.16s", l1 ? l1 : "");

    lcd.setCursor(0, 0);
    lcd.print(line0);
    lcd.setCursor(0, 1);
    lcd.print(line1);
}

static void render_screen(LcdScreen screen, bool manualMode) {
    float t = NAN, h = NAN;
    if (xSemaphoreTake(xSensorDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
        t = sensorData.temperature;
        h = sensorData.humidity;
        xSemaphoreGive(xSensorDataMutex);
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

    char l0[32], l1buf[32];

    if (screen == SCREEN_ENV) {
        if (isnan(t) || isnan(h)) {
            snprintf(l0, sizeof(l0), "%c Sensor waiting", modeChar);
            snprintf(l1buf, sizeof(l1buf), "No data yet");
        } else {
            EnvStatus st = getEnvStatus(t, h);
            snprintf(l0, sizeof(l0), "%c T:%4.1f H:%2.0f%%", modeChar, t, h);
            snprintf(l1buf, sizeof(l1buf), "St:%-12.12s", status_LCD[st].c_str());
        }
    } else if (screen == SCREEN_ACTUATORS) {
        snprintf(l0, sizeof(l0), "%c L1:%s L2:%s", modeChar, onoff(l1), onoff(l2));
        snprintf(l1buf, sizeof(l1buf), "FAN:%s", onoff(false));
    } else {
        snprintf(l0, sizeof(l0), "%c Unknown screen", modeChar);
        snprintf(l1buf, sizeof(l1buf), " ");
    }

    if (xSemaphoreTake(xI2CMutex, pdMS_TO_TICKS(50)) == pdTRUE) {
        lcd_print2(l0, l1buf);
        xSemaphoreGive(xI2CMutex);
    }

    if (IS_DEBUG_MODE || IS_SHOW_LCD_STATUS) {
        Serial.printf("[LCD] %s | T:%.1f H:%.1f | L1:%s L2:%s | mode:%c\n",
                      l0,
                      t,
                      h,
                      onoff(l1),
                      onoff(l2),
                      modeChar);
    }
}

void setup_LCD_display() {
    Serial.println("[INIT] LCD Display task created successfully");

    if (LCD_BTN_ACTIVE_LOW) {
        pinMode(LCD_BTN_PIN, INPUT_PULLUP);
    } else {
        pinMode(LCD_BTN_PIN, INPUT_PULLDOWN);
    }

    if (xSemaphoreTake(xI2CMutex, pdMS_TO_TICKS(200)) == pdTRUE) {
        lcd.begin();
        lcd.backlight();
        lcd_print2("LCD ready", "Auto rotate...");
        xSemaphoreGive(xI2CMutex);
    } else {
        Serial.println("[WARN] LCD init skipped (I2C mutex timeout)");
    }
}

void LCD_display(void *pvParameters) {
    (void)pvParameters;
    setup_LCD_display();

    LcdScreen cur = SCREEN_ENV;
    bool manualMode = false;

    TickType_t lastRotate = xTaskGetTickCount();
    TickType_t lastRefresh = xTaskGetTickCount();
    TickType_t lastUserInteract = 0;

#if LCD_BTN_ACTIVE_LOW
    bool stablePressed = (digitalRead(LCD_BTN_PIN) == LOW);
    bool lastRead = stablePressed;
#else
    bool stablePressed = (digitalRead(LCD_BTN_PIN) == HIGH);
    bool lastRead = stablePressed;
#endif
    TickType_t lastDebounce = xTaskGetTickCount();

    while (1) {
        TickType_t now = xTaskGetTickCount();

#if LCD_BTN_ACTIVE_LOW
        bool readingPressed = (digitalRead(LCD_BTN_PIN) == LOW);
#else
        bool readingPressed = (digitalRead(LCD_BTN_PIN) == HIGH);
#endif

        if (readingPressed != lastRead) {
            lastRead = readingPressed;
            lastDebounce = now;
        }

        bool pressedEvent = false;
        if ((now - lastDebounce) > BTN_DEBOUNCE_TICKS) {
            if (readingPressed != stablePressed) {
                stablePressed = readingPressed;
                if (stablePressed) {
                    pressedEvent = true;
                }
            }
        }

        if (pressedEvent) {
            manualMode = true;
            lastUserInteract = now;
            cur = (LcdScreen)((cur + 1) % SCREEN_COUNT);
            render_screen(cur, manualMode);
        }

        if (manualMode && (now - lastUserInteract) > MANUAL_TIMEOUT_TICKS) {
            manualMode = false;
            lastRotate = now;
            render_screen(cur, manualMode);
        }

        if (!manualMode && (now - lastRotate) > AUTO_ROTATE_TICKS) {
            lastRotate = now;
            cur = (LcdScreen)((cur + 1) % SCREEN_COUNT);
            render_screen(cur, manualMode);
        }

        if ((now - lastRefresh) > LCD_REFRESH_TICKS) {
            lastRefresh = now;
            render_screen(cur, manualMode);
        }

        vTaskDelay(pdMS_TO_TICKS(20));
    }
}