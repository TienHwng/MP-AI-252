#ifndef __DIGITAL_MANAGER_H__
#define __DIGITAL_MANAGER_H__

#include "global.h"

void setup_digital_manager();
void digital_manager(void *pvParameters);
void fan_set_speed(uint8_t speed);

#endif // __DIGITAL_MANAGER_H__
