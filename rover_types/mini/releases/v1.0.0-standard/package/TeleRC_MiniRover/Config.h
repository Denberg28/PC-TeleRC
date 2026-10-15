#pragma once
#include <stdint.h>
#include "HardwareProfile.h"

namespace config {
constexpr char VERSION[] = "1.0.0-standard";
constexpr char WIFI_SSID[] = "TeleRC-MiniRover";
constexpr char WIFI_PASSWORD[] = "telerc123"; // Change here before upload; >=8 characters.
constexpr uint16_t UDP_PORT = 14550;
constexpr uint8_t SYSTEM_ID = 1;
constexpr uint8_t COMPONENT_ID = 1;
constexpr uint8_t GCS_SYSTEM_ID = 255;
constexpr uint8_t GCS_COMPONENT_ID = 190;
constexpr uint32_t CONTROL_TIMEOUT_MS = 500;
constexpr uint32_t PEER_TIMEOUT_MS = 3000;
constexpr uint32_t NEUTRAL_HOLD_MS = 250;
constexpr uint32_t MOTOR_TICK_MS = 5;
constexpr uint32_t REVERSAL_COAST_MS = 30;
constexpr uint32_t PWM_HZ = hardware::PWM_HZ;
constexpr uint8_t MAX_PWM = 180; // 180/255=71%; not a current limit.
constexpr int RC_DEADBAND_US = 25;
constexpr float STEER_GAIN = 0.50f; // Additional onboard skid-steer limit.
constexpr int BOOT_STOP_PIN = 0;
constexpr int STATUS_LED_PIN = 21; // External ordinary LED + 330 ohm; -1 disables.
// Motor order: left front, left rear, right front, right rear.
// Motor pins are defined once, in HardwareProfile.h.
constexpr bool MOTOR_INVERT[4] = {false,false,false,false};
// Reduce individual duty without boosting any motor; slots LF/LR/RF/RR.
constexpr uint8_t MOTOR_TRIM_PERCENT[4]={100,100,100,100};
constexpr uint8_t MOTOR_DUTY_CAP[4]={180,180,180,180};
// FS-iA6 individual PWM signal pins: CH1, CH2, CH5, CH6.
constexpr uint8_t RX_PINS[4] = {12,13,14,15};
constexpr bool RX_STEER_INVERT = false;
constexpr bool RX_DRIVE_INVERT = false;
constexpr uint32_t RX_TIMEOUT_US = 120000;
constexpr uint32_t SELECTOR_HOLD_MS = 80;
constexpr uint16_t PWM_VALID_MIN_US = 900;
constexpr uint16_t PWM_VALID_MAX_US = 2100;
constexpr uint16_t SWITCH_LOW_MAX = 1250;
constexpr uint16_t SWITCH_HIGH_MIN = 1750;
static_assert(sizeof(WIFI_PASSWORD) >= 9 && sizeof(WIFI_PASSWORD) <= 64,
              "Wi-Fi password must be 8..63 characters");
static_assert(SYSTEM_ID > 0 && SYSTEM_ID < 255, "Invalid vehicle system ID");
static_assert(STEER_GAIN > 0 && STEER_GAIN <= 1, "Invalid steering gain");
static_assert(RC_DEADBAND_US>=0 && RC_DEADBAND_US<500,"Invalid RC deadband");
static_assert(MOTOR_TRIM_PERCENT[0]<=100 && MOTOR_TRIM_PERCENT[1]<=100 && MOTOR_TRIM_PERCENT[2]<=100 && MOTOR_TRIM_PERCENT[3]<=100,"Motor trims may only reduce demand");
}
