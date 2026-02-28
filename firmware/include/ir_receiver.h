#ifndef __IR_RECEIVER_H__
#define __IR_RECEIVER_H__

#include "global.h"

void setup_ir_receiver();
void ir_receiver_task(void *pvParameters);

#endif // __IR_RECEIVER_H__
