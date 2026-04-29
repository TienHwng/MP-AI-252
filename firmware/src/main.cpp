#include "main.h"

// Setups for peripherals
// Adafruit_NeoPixel strip(NEO_LED_NUMBER, NEO_LED_PIN, NEO_GRB + NEO_KHZ800);

void setup() {
	// put your setup code here, to run once:
	system_init();

	Serial.println("\n======= System initializing... =======\n");

	xTaskCreate(board_config_server_task, "Board Config", 8192, NULL, PRIO_NET, NULL);

	xTaskCreate(button_handler,    "Button",     2048, NULL, PRIO_INPUT, NULL);
	xTaskCreate(digital_manager,   "Digital IO", 4096, NULL, PRIO_INPUT, NULL);
	xTaskCreate(analog_manager,    "Analog IO",  4096, NULL, PRIO_INPUT, NULL);
	// xTaskCreate(ir_receiver_task,   "IR Receiver", 4096, NULL, PRIO_INPUT, NULL);
	xTaskCreate(mqtt_task,    "MQTT Handler",  4096, NULL, 2, NULL);

	xTaskCreate(sensor_dht20,      	"DHT20",   4096, NULL, PRIO_SENSOR, NULL);
	xTaskCreate(LCD_display, 	 	"LCD",     4096, NULL, PRIO_UI,     NULL);
	xTaskCreate(led_display, 		"LED Display",     4096, NULL, PRIO_UI,     NULL);
	xTaskCreate(neo_display, 		"Neo Display",  4096, NULL, PRIO_UI,     NULL);

	// --- Core 1: sensor + input + ML + UI ---
	// xTaskCreatePinnedToCore(sensor_dht20,        "DHT20",   4096, NULL, PRIO_SENSOR, NULL, 1);
	// xTaskCreatePinnedToCore(Task_Toogle_BOOT,    "BOOT",    4096, NULL, PRIO_INPUT,  NULL, 1);
	// xTaskCreatePinnedToCore(tiny_ml_task,        "TinyML",  8192, NULL, PRIO_ML,     NULL, 1);

	// // LCD_display: should only be a "consumer" (read snapshot + lcd + ws push)
	// xTaskCreatePinnedToCore(LCD_display,   "Monitor", 4096, NULL, PRIO_APP,    NULL, 1);

	// // UI should be merged if possible
	// xTaskCreatePinnedToCore(ui_task,             "UI",      4096, NULL, PRIO_UI,     NULL, 1);

	// // --- Core 0: network tasks ---
	// xTaskCreatePinnedToCore(coreiot_task,        "CoreIOT",  6144, NULL, PRIO_NET,    NULL, 0);
	// xTaskCreatePinnedToCore(telegram_alert_task, "Telegram", 8192, NULL, 1,           NULL, 0);
	// xTaskCreatePinnedToCore(main_server_task, "Server",   10240,NULL, 1,           NULL, 0);

	Serial.println("\n===== System initialization completed. =====\n");
}

void loop() {
	// put your main code here, to run repeatedly:
	// uint16_t raw = analogRead(ANALOG_GPIO_PIN);
    // float voltage = 3.3f * raw / 4095.0f;
    // Serial.printf("pin=%d raw=%u voltage=%.2fV\n", ANALOG_GPIO_PIN, raw, voltage);
    // delay(300);
}

void semaphore_init() {
	// Mutex for LCD I2C
	xLCDSemaphore		  = xSemaphoreCreateMutex();
	
	// Individual Mutex for each type of sensor data
	xDHT20Semaphore   = xSemaphoreCreateMutex();
	xLightSemaphore  = xSemaphoreCreateMutex();
	xMQ2Semaphore    = xSemaphoreCreateMutex();

	// Mutex for state variables (currently used as lock)
	xLedStateSemaphore		  = xSemaphoreCreateMutex();
	xNeoLedStateSemaphore	  = xSemaphoreCreateMutex();
	xWS2812StateSemaphore	  = xSemaphoreCreateMutex();
	xRelayStateSemaphore	  = xSemaphoreCreateMutex();
	xFanStateSemaphore		  = xSemaphoreCreateMutex();

	xInferenceResultSemaphore = xSemaphoreCreateMutex();

	// Internet "ready signal": keeping binary is also OK
	xBinarySemaphoreInternet = xSemaphoreCreateBinary();
}

void system_init() {
	semaphore_init();

	Serial.begin(115200);

	load_board_config_from_storage();

	// check_info_File(0);

	Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
	// dht20.begin();

	// lcd.begin();
	// lcd.backlight();

	// analogReadResolution(12);
    // analogSetPinAttenuation(ANALOG_GPIO_PIN, ADC_11db);
    // pinMode(ANALOG_GPIO_PIN, INPUT);

	
    delay(1000); // Wait for Serial to be ready
}
