#ifndef __TASK_WIFI_H__
#define __TASK_WIFI_H__

#include "global.h"
#include <WiFi.h>

bool wifiHasCredentials();
bool startAP();
bool stopAP();
bool startSTA(uint32_t timeoutMs = WIFI_CONNECT_TIMEOUT_MS);
bool Wifi_reconnect(uint32_t timeoutMs = WIFI_CONNECT_TIMEOUT_MS);

#endif
