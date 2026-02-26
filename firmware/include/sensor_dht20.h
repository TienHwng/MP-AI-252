#ifndef __SENSOR_DHT20_H__
#define __SENSOR_DHT20_H__

#include "DHT20.h"
#include "LiquidCrystal_I2C.h"
#include "global.h"
#include <Arduino.h>

void setup_sensor_dht20();
void sensor_dht20(void *pvParameters);

#endif // __SENSOR_DHT20_H__