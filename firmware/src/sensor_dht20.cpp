#include "sensor_dht20.h"

void setup_sensor_dht20() {
	Serial.println("[INIT] DHT20 Reader task created successfully");

	if (xI2CMutex == NULL || xSensorDataMutex == NULL) {
		Serial.println("[ERROR] DHT20 Reader: mutexes are not initialized");
	}
}

void sensor_dht20(void *pvParameters) {
	setup_sensor_dht20();

	TickType_t		 lastWake = xTaskGetTickCount();
	const TickType_t period	  = pdMS_TO_TICKS(1000);

	while (1) {
		vTaskDelayUntil(&lastWake, period);

		float humid = NAN;
		float temp	= NAN;

		// I2C transaction: keep lock as short as possible
		if (xSemaphoreTake(xI2CMutex, pdMS_TO_TICKS(50)) == pdTRUE) {
			dht20.read();
			humid = dht20.getHumidity();
			temp  = dht20.getTemperature();
			xSemaphoreGive(xI2CMutex);
		}

		const bool ok = (!isnan(humid) && !isnan(temp));

		// Update shared latest data
		if (ok && xSemaphoreTake(xSensorDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
			sensorData.humidity	   = humid;
			sensorData.temperature = temp;
			xSemaphoreGive(xSensorDataMutex);
		}

		if (IS_DEBUG_MODE || IS_SHOW_DHT20_STATUS) {
			if (ok) {
				Serial.printf("[DHT20] Humidity: %.2f %%, Temperature: %.2f C\n", humid, temp);
			}
			else {
				Serial.println("[DHT20] Failed to read data from DHT20 sensor!");
			}
		}
	}
}