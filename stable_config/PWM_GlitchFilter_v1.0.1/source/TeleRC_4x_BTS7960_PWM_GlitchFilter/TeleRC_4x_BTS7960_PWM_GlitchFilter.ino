/*
  TeleRC / ArduRover - ESP32-S3 PWM converter
  Glitch-filter test candidate 1.0.1, 2026-10-11
  Derived from your uploaded Pasted markdown(3).md.
  Invalid samples are discarded; last valid sample expires after 150 ms.
  Four FC inputs -> four BTS7960 drivers.
  M5 -> GPIO4 -> Front Left
  M6 -> GPIO5 -> Rear Left
  M7 -> GPIO6 -> Front Right
  M8 -> GPIO7 -> Rear Right
  Front Left:  RPWM GPIO8,  LPWM GPIO9
  Rear Left:   RPWM GPIO10, LPWM GPIO11
  Front Right: RPWM GPIO12, LPWM GPIO13
  Rear Right:  RPWM GPIO14, LPWM GPIO15
  Native USB settings:
  USB Mode: Hardware CDC and JTAG
  USB CDC On Boot: Enabled
  Serial Monitor: 115200 baud
  Select the board preset matching your actual ESP32-S3 module.
  All grounds must be common.
  Never apply 5V to an ESP32 GPIO.
  Use external PWM pulldowns and a physical motor power cutoff.
  Confirm BTS7960 input logic compatibility.
  This sketch does not receive the FC armed state.
  FC arming and command-link failsafes remain required.
*/
#include <Arduino.h>
#include <esp_arduino_version.h>
#include <esp_system.h>
constexpr uint16_t RC_MIN_US = 1000;
constexpr uint16_t RC_CENTER_US = 1500;
constexpr uint16_t RC_MAX_US = 2000;
constexpr uint16_t RC_VALID_MIN_US = 850;
constexpr uint16_t RC_VALID_MAX_US = 2150;
constexpr uint16_t RC_DEADBAND_US = 35;
constexpr uint32_t RC_TIMEOUT_US = 150000;
constexpr uint32_t NEUTRAL_DWELL_US = 300000;
constexpr uint32_t CONTROL_PERIOD_US = 5000;
constexpr uint32_t DIAG_PERIOD_MS = 250;
constexpr uint32_t PWM_FREQ_HZ = 20000;
constexpr uint8_t PWM_BITS = 8;
// 255 = full PWM duty. Use 128 for initial raised-wheel tests.
constexpr int MAX_MOTOR_DUTY = 255;
constexpr int ACCEL_STEP = 12;
constexpr int DECEL_STEP = 12;
constexpr uint8_t RC_IN_PIN[4] = {4, 5, 6, 7};
constexpr uint8_t RPWM_PIN[4] = {8, 10, 12, 14};
constexpr uint8_t LPWM_PIN[4] = {9, 11, 13, 15};
// Motor order: Front Left, Rear Left, Front Right, Rear Right.
constexpr bool INVERT_MOTOR[4] = {false, false, false, false};
#if ESP_ARDUINO_VERSION_MAJOR < 3
constexpr uint8_t RPWM_CH[4] = {0, 2, 4, 6};
constexpr uint8_t LPWM_CH[4] = {1, 3, 5, 7};
#endif
portMUX_TYPE captureMux = portMUX_INITIALIZER_UNLOCKED;
volatile bool riseSeen[4] = {};
// Latched only after a valid pulse; rejected edges never refresh its age.
volatile bool pulseValid[4] = {};
volatile uint32_t rejectedPulseCount[4] = {};
volatile uint32_t riseUs[4] = {};
volatile uint32_t lastValidPulseUs[4] = {};
volatile uint16_t pulseWidthUs[4] = {
  RC_CENTER_US, RC_CENTER_US, RC_CENTER_US, RC_CENTER_US
};
bool snapshotValid[4] = {};
uint32_t snapshotRejected[4] = {};
uint32_t signalStops = 0;
int bootResetReason = 0;
uint32_t snapshotLastUs[4] = {};
uint16_t snapshotPulseUs[4] = {};
int currentCmd[4] = {};
int targetCmd[4] = {};
bool motorPwmReady = false;
bool sourceEnabled = false;
bool neutralTracking = false;
uint32_t neutralSinceUs = 0;
uint32_t lastControlUs = 0;
uint32_t lastDiagMs = 0;
// Diagnostics are transmitted in small chunks so a complete line
// does not have to fit in the USB transmit buffer at once.
char diagnostic[256];
size_t diagnosticLength = 0;
size_t diagnosticOffset = 0;
static inline void IRAM_ATTR captureEdge(uint8_t channel) {
  const uint32_t now = micros();
  portENTER_CRITICAL_ISR(&captureMux);
  if (digitalRead(RC_IN_PIN[channel])) {
    riseUs[channel] = now;
    riseSeen[channel] = true;
  } else {
    const uint32_t width = now - riseUs[channel];
    const bool valid = riseSeen[channel] &&
      width >= RC_VALID_MIN_US && width <= RC_VALID_MAX_US;
    if (valid) {
      pulseWidthUs[channel] = static_cast<uint16_t>(width);
      lastValidPulseUs[channel] = now;
      pulseValid[channel] = true;
    } else {
      // Reject this sample, retain the last VALID command for at most 150 ms.
      // Do not clear pulseValid or update lastValidPulseUs on noise.
      ++rejectedPulseCount[channel];
    }
    riseSeen[channel] = false;
  }
  portEXIT_CRITICAL_ISR(&captureMux);
}
void IRAM_ATTR rc0ISR() { captureEdge(0); }
void IRAM_ATTR rc1ISR() { captureEdge(1); }
void IRAM_ATTR rc2ISR() { captureEdge(2); }
void IRAM_ATTR rc3ISR() { captureEdge(3); }
void snapshotInputs() {
  portENTER_CRITICAL(&captureMux);
  for (uint8_t i = 0; i < 4; ++i) {
    snapshotPulseUs[i] = pulseWidthUs[i];
    snapshotLastUs[i] = lastValidPulseUs[i];
    snapshotValid[i] = pulseValid[i];
    snapshotRejected[i] = rejectedPulseCount[i];
  }
  portEXIT_CRITICAL(&captureMux);
}
bool attachMotorPwm() {
  bool ok = true;
  for (uint8_t i = 0; i < 4; ++i) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ok = ledcAttach(RPWM_PIN[i], PWM_FREQ_HZ, PWM_BITS) && ok;
    ok = ledcAttach(LPWM_PIN[i], PWM_FREQ_HZ, PWM_BITS) && ok;
#else
    ok = (ledcSetup(RPWM_CH[i], PWM_FREQ_HZ, PWM_BITS) > 0) && ok;
    ok = (ledcSetup(LPWM_CH[i], PWM_FREQ_HZ, PWM_BITS) > 0) && ok;
    ledcAttachPin(RPWM_PIN[i], RPWM_CH[i]);
    ledcAttachPin(LPWM_PIN[i], LPWM_CH[i]);
#endif
  }
  return ok;
}
void pwmWritePin(uint8_t motor, bool forward, uint8_t duty) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(forward ? RPWM_PIN[motor] : LPWM_PIN[motor], duty);
#else
  ledcWrite(forward ? RPWM_CH[motor] : LPWM_CH[motor], duty);
#endif
}
void setBtsMotor(uint8_t motor, int command) {
  command = constrain(command, -MAX_MOTOR_DUTY, MAX_MOTOR_DUTY);
  if (INVERT_MOTOR[motor]) {
    command = -command;
  }
  if (command > 0) {
    pwmWritePin(motor, false, 0);
    pwmWritePin(motor, true, static_cast<uint8_t>(command));
  } else if (command < 0) {
    pwmWritePin(motor, true, 0);
    pwmWritePin(motor, false, static_cast<uint8_t>(-command));
  } else {
    // Zero command. Actual braking depends on the driver.
    pwmWritePin(motor, true, 0);
    pwmWritePin(motor, false, 0);
  }
}
void stopAllMotors() {
  for (uint8_t i = 0; i < 4; ++i) {
    setBtsMotor(i, 0);
  }
}
void hardStop() {
  sourceEnabled = false;
  neutralTracking = false;
  for (uint8_t i = 0; i < 4; ++i) {
    currentCmd[i] = 0;
    targetCmd[i] = 0;
  }
  stopAllMotors();
}
bool channelFresh(uint8_t channel, uint32_t nowUs) {
  return snapshotValid[channel] &&
         uint32_t(nowUs - snapshotLastUs[channel]) < RC_TIMEOUT_US;
}
int rcPulseToCommand(uint16_t pulseUs) {
  pulseUs = constrain(pulseUs, RC_MIN_US, RC_MAX_US);
  const int delta = static_cast<int>(pulseUs) - RC_CENTER_US;
  if (abs(delta) <= RC_DEADBAND_US) {
    return 0;
  }
  const int magnitude = abs(delta);
  const int span = delta > 0
    ? RC_MAX_US - RC_CENTER_US
    : RC_CENTER_US - RC_MIN_US;
  const int command = static_cast<int>(
    map(magnitude, RC_DEADBAND_US, span, 0, MAX_MOTOR_DUTY)
  );
  return constrain(
    delta > 0 ? command : -command,
    -MAX_MOTOR_DUTY,
    MAX_MOTOR_DUTY
  );
}
int slewToward(int current, int target) {
  if (current == target) {
    return current;
  }
  if ((current > 0 && target < 0) ||
      (current < 0 && target > 0)) {
    if (abs(current) <= DECEL_STEP) {
      return 0;
    }
    return current > 0
      ? current - DECEL_STEP
      : current + DECEL_STEP;
  }
  const bool accelerating =
    target != 0 && abs(target) > abs(current);
  const int step = accelerating ? ACCEL_STEP : DECEL_STEP;
  if (target > current) {
    return current + min(step, target - current);
  }
  return current - min(step, current - target);
}
bool computeTargets(uint32_t nowUs) {
  for (uint8_t i = 0; i < 4; ++i) {
    if (!channelFresh(i, nowUs)) {
      return false;
    }
  }
  for (uint8_t i = 0; i < 4; ++i) {
    targetCmd[i] = rcPulseToCommand(snapshotPulseUs[i]);
  }
  return true;
}
bool inputsNeutral() {
  for (uint8_t i = 0; i < 4; ++i) {
    if (abs(static_cast<int>(snapshotPulseUs[i]) -
            static_cast<int>(RC_CENTER_US)) > RC_DEADBAND_US) {
      return false;
    }
  }
  return true;
}
void updateMotors() {
  for (uint8_t i = 0; i < 4; ++i) {
    currentCmd[i] = slewToward(currentCmd[i], targetCmd[i]);
    setBtsMotor(i, currentCmd[i]);
  }
}
void serviceDiagnostics(uint32_t nowUs) {
  const uint32_t nowMs = millis();
  if (diagnosticOffset >= diagnosticLength &&
      uint32_t(nowMs - lastDiagMs) >= DIAG_PERIOD_MS) {
    lastDiagMs = nowMs;
    const int count = snprintf(
      diagnostic,
      sizeof(diagnostic),
      "RC(us): %u%c %u%c %u%c %u%c | CMD: %d %d %d %d | source=%s PWM=%s | bad=%lu,%lu,%lu,%lu stops=%lu up=%lu reset=%d\n",
      static_cast<unsigned>(snapshotPulseUs[0]),
      channelFresh(0, nowUs) ? '*' : '!',
      static_cast<unsigned>(snapshotPulseUs[1]),
      channelFresh(1, nowUs) ? '*' : '!',
      static_cast<unsigned>(snapshotPulseUs[2]),
      channelFresh(2, nowUs) ? '*' : '!',
      static_cast<unsigned>(snapshotPulseUs[3]),
      channelFresh(3, nowUs) ? '*' : '!',
      currentCmd[0], currentCmd[1], currentCmd[2], currentCmd[3],
      sourceEnabled ? "enabled" : "neutral-wait",
      motorPwmReady ? "ready" : "failed",
      static_cast<unsigned long>(snapshotRejected[0]),
      static_cast<unsigned long>(snapshotRejected[1]),
      static_cast<unsigned long>(snapshotRejected[2]),
      static_cast<unsigned long>(snapshotRejected[3]),
      static_cast<unsigned long>(signalStops),
      static_cast<unsigned long>(nowMs), bootResetReason
    );
    diagnosticOffset = 0;
    diagnosticLength =
      count > 0 && count < static_cast<int>(sizeof(diagnostic))
      ? static_cast<size_t>(count)
      : 0;
  }
  if (diagnosticOffset >= diagnosticLength) {
    return;
  }
  const int available = Serial.availableForWrite();
  if (available <= 0) {
    return;
  }
  size_t chunk = diagnosticLength - diagnosticOffset;
  if (chunk > 32) {
    chunk = 32;
  }
  if (chunk > static_cast<size_t>(available)) {
    chunk = static_cast<size_t>(available);
  }
  diagnosticOffset += Serial.write(
    reinterpret_cast<const uint8_t*>(diagnostic + diagnosticOffset),
    chunk
  );
}
void setup() {
  for (uint8_t i = 0; i < 4; ++i) {
    pinMode(RPWM_PIN[i], OUTPUT);
    pinMode(LPWM_PIN[i], OUTPUT);
    digitalWrite(RPWM_PIN[i], LOW);
    digitalWrite(LPWM_PIN[i], LOW);
    pinMode(RC_IN_PIN[i], INPUT_PULLDOWN);
  }
  Serial.begin(115200);
  bootResetReason = static_cast<int>(esp_reset_reason());
  // No wait for Serial: motor safety must work without a computer.
  motorPwmReady = attachMotorPwm();
  hardStop();
  attachInterrupt(digitalPinToInterrupt(RC_IN_PIN[0]), rc0ISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(RC_IN_PIN[1]), rc1ISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(RC_IN_PIN[2]), rc2ISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(RC_IN_PIN[3]), rc3ISR, CHANGE);
}
void loop() {
  snapshotInputs();
  const uint32_t nowUs = micros();
  if (uint32_t(nowUs - lastControlUs) >= CONTROL_PERIOD_US) {
    lastControlUs = nowUs;
    if (!motorPwmReady || !computeTargets(nowUs)) {
      if (sourceEnabled && motorPwmReady) ++signalStops;
      hardStop();
    } else {
      if (!sourceEnabled) {
        if (!inputsNeutral()) {
          neutralTracking = false;
        } else if (!neutralTracking) {
          neutralTracking = true;
          neutralSinceUs = nowUs;
        } else if (uint32_t(nowUs - neutralSinceUs) >= NEUTRAL_DWELL_US) {
          sourceEnabled = true;
        }
      }
      if (sourceEnabled) {
        updateMotors();
      } else {
        stopAllMotors();
      }
    }
  }
  serviceDiagnostics(nowUs);
}
