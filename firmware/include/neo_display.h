#ifndef __NEO_DISPLAY__
#define __NEO_DISPLAY__

#include <Adafruit_NeoPixel.h>
#include <Arduino.h>
#include <DHT20.h>
#include <Wire.h>
#include <global.h>

void setup_neo_display();
void update_NEO_LED(uint32_t index);
void neo_display(void *pvParameters);
void ws2812_set(bool on);
void ws2812_toggle();

#endif
