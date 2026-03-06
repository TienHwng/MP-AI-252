#ifndef MQTT_HANDLER_H
#define MQTT_HANDLER_H

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "global.h"

// function for main.cpp
void setup_mqtt();
void publish_telemetry(float temp, float hum, float anomaly, bool led_state, bool neo_state);

// helper function
void reconnect();
void callback(char* topic, byte* payload, unsigned int length);
void mqtt_task(void *pvParameters);
#endif