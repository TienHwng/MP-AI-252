#ifndef __LED_DISPLAY__
#define __LED_DISPLAY__

#include "global.h"

// Local defines
// clang-format off
#define BLINK_COLD      2000
#define BLINK_IDEAL     1700
#define BLINK_NORMAL    1300
#define BLINK_HOT       900
#define BLINK_WARNING   500
// clang-format on

void setup_led_display(void);
void led_display(void *pvParameters);

#endif