#ifndef __MAIN_H__
#define __MAIN_H__

// ===== RTOS task priorities (higher number = higher priority) =====
#ifndef PRIO_SENSOR
#define PRIO_SENSOR 4
#endif
#ifndef PRIO_INPUT
#define PRIO_INPUT 3
#endif
#ifndef PRIO_ML
#define PRIO_ML 3
#endif
#ifndef PRIO_APP
#define PRIO_APP 2
#endif
#ifndef PRIO_NET
#define PRIO_NET 2
#endif
#ifndef PRIO_UI
#define PRIO_UI 1
#endif

// ===== ESP32 core pinning =====
#ifndef CORE_APP
#define CORE_APP 1
#endif
#ifndef CORE_NET
#define CORE_NET 0
#endif

// ===== Include section =====
#include "global.h"


#include <Arduino.h>
// #include <WiFi.h>
// #include <WiFiClientSecure.h>
#include <ESPAsyncWebServer.h>

#include "sensor_dht20.h"
#include "led_display.h"
#include "neo_blinky.h"
#include "LCD_display.h"

void system_init();
void semaphore_init();

#endif // __MAIN_H__