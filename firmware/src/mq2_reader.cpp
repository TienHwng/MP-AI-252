#include "mq2_reader.h"

#include <math.h>

static Preferences preferences;
static float gas_warn_ppm = MQ2_WARN_PPM_DEFAULT;
static float gas_crit_ppm = MQ2_CRIT_PPM_DEFAULT;
static float mq2_r0       = MQ2_DEFAULT_R0;

static float adcToVoltage(int raw) {
	return (constrain(raw, 0, (int)MQ2_ADC_MAX) * MQ2_VREF) / MQ2_ADC_MAX;
}

static float rsFromVoltage(float voltage) {
	if (voltage <= 0.0f)
		return -1.0f;
	return (5 * MQ2_RL_KOHM / voltage) - MQ2_RL_KOHM;
}

static float calibrate_mq2_r0() {
	float rs_sum = 0.0f;
	int	  valid	 = 0;

	for (int i = 0; i < MQ2_CALIBRATION_SAMPLES; i++) {
		int	  raw	 = analogRead(MQ2_ANALOG_PIN);
		float volts	 = adcToVoltage(raw);
		float rs_val = rsFromVoltage(volts);
		if (rs_val > 0.0f) {
			rs_sum += rs_val;
			valid++;
		}
		vTaskDelay(pdMS_TO_TICKS(MQ2_CALIBRATION_DELAY_MS));
	}

	if (valid == 0) {
		Serial.println("[MQ2] Calibration failed, using default R0");
		return MQ2_DEFAULT_R0;
	}

	float rs_avg = rs_sum / valid;
	float r0	 = rs_avg / MQ2_CLEAN_AIR_FACTOR;
	Serial.printf("[MQ2] Calibration done: R0=%.3f kOhm (samples=%d)\n", r0, valid);
	return r0;
}

static float ppmFromAdc(int raw) {
	float volts = adcToVoltage(raw);
	float rs	= rsFromVoltage(volts);
	if (rs <= 0.0f || mq2_r0 <= 0.0f)
		return 0.0f;

	float ratio = rs / mq2_r0;
	float ppm	= MQ2_CURVE_A * powf(ratio, MQ2_CURVE_B);
	if (ppm < 0.0f)
		ppm = 0.0f;
	return ppm;
}

void mq2_reader(void *pvParameters) {
	setup_mq2_reader();

	while (1) {
		if (xSemaphoreTake(xMQ2Semaphore, pdMS_TO_TICKS(20)) == pdTRUE) {
			int	  rawAdc	   = analogRead(MQ2_ANALOG_PIN);
			float gas_ppm	   = ppmFromAdc(rawAdc);
			sensorData.gas = gas_ppm;
			xSemaphoreGive(xMQ2Semaphore);

			if (IS_DEBUG_MODE || IS_SHOW_MQ2_STATUS) {
				Serial.printf("[MQ2] ADC=%d -> Gas=%.2f ppm (R0=%.3f kOhm)\n", rawAdc, gas_ppm,
							  mq2_r0);
			}
		}

		vTaskDelay(pdMS_TO_TICKS(GAS_MONITOR_DELAY_MS));
	}
}

void setup_mq2_reader() {
	pinMode(MQ2_ANALOG_PIN, INPUT);
	mq2_r0 = calibrate_mq2_r0();

	preferences.begin("gas_cfg", false);

	gas_warn_ppm = preferences.getFloat("warning", MQ2_WARN_PPM_DEFAULT);
	gas_crit_ppm = preferences.getFloat("critical", MQ2_CRIT_PPM_DEFAULT);
	mq2_r0		 = preferences.getFloat("mq2_r0", mq2_r0);

	float storedR0 = preferences.getFloat("mq2_r0", -1.0f);
	if (storedR0 > 0.0f) {
		mq2_r0 = storedR0;
		Serial.printf("[MQ2] Loaded R0 from NVS: %.3f kOhm\n", mq2_r0);
	}
	else {
		preferences.putFloat("mq2_r0", mq2_r0);
		Serial.printf("[MQ2] First run, saving R0 to NVS: %.3f kOhm\n", mq2_r0);
	}

	preferences.end();

	if (xMQ2Semaphore == NULL) {
		Serial.println("[ERROR] MQ2 Reader task has not been created");
	}
	else {
		Serial.println("[INIT] MQ2 Reader task created successfully");
	}
}