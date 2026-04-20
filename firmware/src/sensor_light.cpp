#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include <Arduino.h>
#include <math.h>


// =========================
// CONFIG
// =========================
#define LIGHT_SENSOR_PIN     34
#define LIGHT_ADC_MAX		 4095
#define LIGHT_VCC			 3.3f
#define LIGHT_NUM_SAMPLES	 32
#define LIGHT_TASK_PERIOD_MS 500
#define LIGHT_EMA_ALPHA		 0.20f

// Gia dinh theo module cua ban
#define LIGHT_R_FIXED 10000.0f // 10k
#define LIGHT_R10	  15000.0f // 15k at 10 lux
#define LIGHT_GAMMA	  0.65f

// false = VCC - LDR - SIG - R_FIXED - GND
// true  = VCC - R_FIXED - SIG - LDR - GND
#define LIGHT_LDR_TO_GND false

// =========================
// DATA STRUCT
// =========================
typedef struct {
	int	  adcRaw;
	float adcFilt;
	float vout;
	float rldr;
	float luxRaw;
	float luxFilt;
	char  level[16];
} LightSensorData_t;

static LightSensorData_t g_lightData;
static SemaphoreHandle_t g_lightMutex = NULL;

// =========================
// INTERNAL FUNCTIONS
// =========================
static int light_readADC_Average() {
	long sum = 0;
	for (int i = 0; i < LIGHT_NUM_SAMPLES; i++) {
		sum += analogRead(LIGHT_SENSOR_PIN);
		vTaskDelay(pdMS_TO_TICKS(2));
	}
	return (int)(sum / LIGHT_NUM_SAMPLES);
}

static float light_adcToVoltage(int adc) { return ((float)adc * LIGHT_VCC) / (float)LIGHT_ADC_MAX; }

static float light_calcLdrResistance(float vout) {
	const float eps = 0.0001f;

	if (vout < eps)
		vout = eps;
	if (vout > LIGHT_VCC - eps)
		vout = LIGHT_VCC - eps;

	if (LIGHT_LDR_TO_GND) {
		// VCC - R_FIXED - SIG - LDR - GND
		return LIGHT_R_FIXED * vout / (LIGHT_VCC - vout);
	}
	else {
		// VCC - LDR - SIG - R_FIXED - GND
		return LIGHT_R_FIXED * (LIGHT_VCC / vout - 1.0f);
	}
}

static float light_resistanceToLux(float rldr) {
	if (rldr <= 0.0f)
		return 0.0f;

	float lux = 10.0f * powf(LIGHT_R10 / rldr, 1.0f / LIGHT_GAMMA);

	if (!isfinite(lux) || lux < 0.0f)
		lux = 0.0f;
	return lux;
}

static float light_ema(float input, float prev, float alpha) {
	return alpha * input + (1.0f - alpha) * prev;
}

static const char *light_getLevel(float lux) {
	if (lux < 1.0f)
		return "Rat toi";
	if (lux < 10.0f)
		return "Toi";
	if (lux < 50.0f)
		return "Mo";
	if (lux < 150.0f)
		return "Trong nha";
	if (lux < 400.0f)
		return "Sang";
	return "Rat sang";
}

// =========================
// PUBLIC API
// =========================
bool LightSensor_GetData(LightSensorData_t *outData) {
	if (outData == NULL || g_lightMutex == NULL)
		return false;

	if (xSemaphoreTake(g_lightMutex, pdMS_TO_TICKS(20)) == pdTRUE) {
		*outData = g_lightData;
		xSemaphoreGive(g_lightMutex);
		return true;
	}
	return false;
}

// =========================
// TASK
// =========================
void LightSensorTask(void *pvParameters) {
	analogReadResolution(12);

	if (g_lightMutex == NULL) {
		g_lightMutex = xSemaphoreCreateMutex();
	}

	float adcFilt  = 0.0f;
	float luxFilt  = 0.0f;
	bool  firstRun = true;

	TickType_t xLastWakeTime = xTaskGetTickCount();

	while (1) {
		int	  adcRaw = light_readADC_Average();
		float vout	 = light_adcToVoltage(adcRaw);
		float rldr	 = light_calcLdrResistance(vout);
		float luxRaw = light_resistanceToLux(rldr);

		if (firstRun) {
			adcFilt	 = (float)adcRaw;
			luxFilt	 = luxRaw;
			firstRun = false;
		}
		else {
			adcFilt = light_ema((float)adcRaw, adcFilt, LIGHT_EMA_ALPHA);
			luxFilt = light_ema(luxRaw, luxFilt, LIGHT_EMA_ALPHA);
		}

		if (g_lightMutex != NULL) {
			if (xSemaphoreTake(g_lightMutex, pdMS_TO_TICKS(20)) == pdTRUE) {
				g_lightData.adcRaw	= adcRaw;
				g_lightData.adcFilt = adcFilt;
				g_lightData.vout	= vout;
				g_lightData.rldr	= rldr;
				g_lightData.luxRaw	= luxRaw;
				g_lightData.luxFilt = luxFilt;

				snprintf(g_lightData.level, sizeof(g_lightData.level), "%s", light_getLevel(luxFilt));

				xSemaphoreGive(g_lightMutex);
			}
		}

		Serial.print("[LightTask] ADC=");
		Serial.print(adcRaw);
		Serial.print(" | ADC_f=");
		Serial.print((int)roundf(adcFilt));
		Serial.print(" | Vout=");
		Serial.print(vout, 3);
		Serial.print("V | RLDR=");
		Serial.print(rldr, 1);
		Serial.print(" ohm | Lux=");
		Serial.print(luxFilt, 1);
		Serial.print(" lx | ");
		Serial.println(light_getLevel(luxFilt));

		vTaskDelayUntil(&xLastWakeTime, pdMS_TO_TICKS(LIGHT_TASK_PERIOD_MS));
	}
}