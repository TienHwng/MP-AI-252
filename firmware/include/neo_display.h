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
void ws2812_set_color(int red, int green, int blue);
void ws2812_set_brightness(uint8_t brightness);
void ws2812_toggle();
String ws2812_get_color_hex();
String getNeoLedColorFromHumidity(float humidity);

void neoLED_set_brightness(uint8_t brightness);

#endif
