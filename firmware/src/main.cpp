#include "main.h"

// Setups for peripherals
// Adafruit_NeoPixel strip(NEO_LED_NUMBER, NEO_LED_PIN, NEO_GRB + NEO_KHZ800);

void setup() {
	// put your setup code here, to run once:
	system_init();

	Serial.println("\n======= System initializing... =======\n");

	xTaskCreate(sensor_dht20,      	"DHT20",   4096, NULL, PRIO_SENSOR, NULL);
	xTaskCreate(LCD_display, 	 	"LCD",     4096, NULL, PRIO_UI,     NULL);
	xTaskCreate(led_display, 		"LED Display",     4096, NULL, PRIO_UI,     NULL);
	xTaskCreate(neo_blinky, 		"Neo Display",  4096, NULL, PRIO_UI,     NULL);

	// --- Core 1: sensor + input + ML + UI ---
	// xTaskCreatePinnedToCore(sensor_dht20,        "DHT20",   4096, NULL, PRIO_SENSOR, NULL, 1);
	// xTaskCreatePinnedToCore(Task_Toogle_BOOT,    "BOOT",    4096, NULL, PRIO_INPUT,  NULL, 1);
	// xTaskCreatePinnedToCore(tiny_ml_task,        "TinyML",  8192, NULL, PRIO_ML,     NULL, 1);

	// // LCD_display: chỉ nên làm "consumer" (đọc snapshot + lcd + ws push)
	// xTaskCreatePinnedToCore(LCD_display,   "Monitor", 4096, NULL, PRIO_APP,    NULL, 1);

	// // UI nên gộp lại nếu được
	// xTaskCreatePinnedToCore(ui_task,             "UI",      4096, NULL, PRIO_UI,     NULL, 1);

	// // --- Core 0: network tasks ---
	// xTaskCreatePinnedToCore(coreiot_task,        "CoreIOT",  6144, NULL, PRIO_NET,    NULL, 0);
	// xTaskCreatePinnedToCore(telegram_alert_task, "Telegram", 8192, NULL, 1,           NULL, 0);
	// xTaskCreatePinnedToCore(main_server_task, "Server",   10240,NULL, 1,           NULL, 0);

	Serial.println("\n===== System initialization completed. =====\n");
}

void loop() {
	// put your main code here, to run repeatedly:
}

void semaphore_init() {
	// Mutex cho I2C & data
	xI2CMutex		 = xSemaphoreCreateMutex();
	xSensorDataMutex = xSemaphoreCreateMutex();

	// Mutex cho state variables (đang dùng như lock)
	xLedStateSemaphore		  = xSemaphoreCreateMutex();
	xNeoLedStateSemaphore	  = xSemaphoreCreateMutex();
	xInferenceResultSemaphore = xSemaphoreCreateMutex();

	// Internet “ready signal”: giữ binary cũng OK
	xBinarySemaphoreInternet = xSemaphoreCreateBinary();
}

void system_init() {
	semaphore_init();

	Serial.begin(115200);

	// check_info_File(0);

	Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
	// dht20.begin();

	// lcd.begin();
	// lcd.backlight();
}

