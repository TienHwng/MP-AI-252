#ifndef __ACTUATOR_MANAGER_H__
#define __ACTUATOR_MANAGER_H__

#include "global.h"

void actuator_init();
void set_device_state(DeviceID id, bool state);
void toggle_device_state(DeviceID id);
bool get_device_state(DeviceID id);

#endif