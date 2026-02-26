#ifndef __LCD_DISPLAY__
#define __LCD_DISPLAY__

#include "DHT20.h"
#include "LiquidCrystal_I2C.h"
#include "global.h"
#include <Arduino.h>

void LCD_display(void *pvParameters);
void setup_LCD_display();

#endif