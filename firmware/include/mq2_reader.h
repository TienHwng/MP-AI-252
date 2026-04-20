#ifndef __MQ2_READER_H__
#define __MQ2_READER_H__

#include "global.h"
#include <Arduino.h>
#include <Preferences.h>

void setup_mq2_reader();
void mq2_reader(void *pvParameters);

#endif