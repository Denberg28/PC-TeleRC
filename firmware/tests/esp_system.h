#pragma once
enum { ESP_RST_POWERON=1, ESP_RST_PANIC=4, ESP_RST_INT_WDT=5,
       ESP_RST_TASK_WDT=6, ESP_RST_WDT=7, ESP_RST_BROWNOUT=9 };
inline int esp_reset_reason() { return 1; }
