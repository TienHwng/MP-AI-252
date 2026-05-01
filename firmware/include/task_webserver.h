#ifndef __TASK_WEBSERVER_H__
#define __TASK_WEBSERVER_H__

#include "LittleFS.h"
#include "global.h"
#include <ArduinoJson.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>

extern AsyncWebServer server;
extern AsyncWebSocket ws;
extern bool webserver_isrunning;

void connectWSV();
void connnectWSV();
void Webserver_stop();
void Webserver_reconnect();
void Webserver_senddata(String data);
void onEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len);

#endif
