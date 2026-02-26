#ifndef __NEO_BLINKY__
#define __NEO_BLINKY__

#include <Adafruit_NeoPixel.h>
#include <Arduino.h>
#include <DHT20.h>
#include <Wire.h>
#include <global.h>

void setup_neo_blinky();
void update_NEO_LED(uint32_t index);
void neo_blinky(void *pvParameters);

#endif