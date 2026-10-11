/*
  TeleRC / ArduRover - RC PWM to 4x BTS7960 Converter
  Target: ESP32-S3 DevKitC-1

  PURPOSE
  -------
  Convert standard RC/servo PWM from a flight controller
  (1000-2000 us, 1500 us neutral) into RPWM/LPWM signals
  for four BTS7960 / IBT-2 brushed DC motor drivers.

  DEFAULT MODE
  ------------
  Two FC inputs for skid steering:
    LEFT input  -> Front Left + Rear Left BTS7960
    RIGHT input -> Front Right + Rear Right BTS7960

  SAFETY FEATURES
  ---------------
  - Input pulse validation
  - Loss-of-signal timeout
  - All-stop failsafe
  - Neutral deadband
  - Acceleration/deceleration slew limiting
  - Direction reversal always returns through zero
  - 20 kHz BTS7960 PWM
  - Serial diagnostics at 115200 baud

  IMPORTANT
  ---------
  - ALL GROUNDS MUST BE COMMON: FC GND, ESP32 GND, BTS7960 logic GND.
  - Do NOT feed 5 V into an ESP32-S3 GPIO.
  - BTS7960 R_EN and L_EN may be tied HIGH to its regulated 5 V logic supply.
  - Use a regulated supply for ESP32/BTS logic.
  - Never feed the rover motor-battery voltage directly into the ESP32.
  - Motor battery power goes directly to each BTS7960 power stage through
    appropriate fusing and wiring.
  - This is a STANDALONE companion sketch. Flashing it over TeleRCBridge.ino
    on the same ESP32 will replace the Wi-Fi/MAVLink bridge firmware.
*/

#include <Arduino.h>
#include <esp_arduino_version.h>

// -----------------------------------------------------------------------------
// USER CONFIGURATION
// -----------------------------------------------------------------------------

// true  = 2-input skid-steer mode: LEFT drives motors 0/1, RIGHT drives 2/3.
// false = 4 independent RC inputs, one per BTS7960.
#ifndef TELERC_PWM_PAIRED
#define TELERC_PWM_PAIRED 0
#endif
constexpr bool PAIRED_SKID_STEER = TELERC_PWM_PAIRED;

// In four-input mode, loss of any required RC signal stops all motors.
constexpr bool FAILSAFE_ALL_STOP = true;

// Standard RC PWM calibration.
constexpr uint16_t RC_MIN_US     = 1000;
constexpr uint16_t RC_CENTER_US  = 1500;
constexpr uint16_t RC_MAX_US     = 2000;

// Accept slightly wider pulses for validation.
constexpr uint16_t RC_VALID_MIN_US = 850;
constexpr uint16_t RC_VALID_MAX_US = 2150;

// Neutral deadband around 1500 us.
constexpr uint16_t RC_DEADBAND_US = 35;

// Signal-loss timeout.
constexpr uint32_t RC_TIMEOUT_US = 150000;
constexpr uint32_t SOURCE_NEUTRAL_DWELL_US = 300000;

// Output PWM.
constexpr uint32_t PWM_FREQ_HZ = 20000;
constexpr uint8_t  PWM_BITS    = 8;

// 255 = 100%.
// For first bench test use 140-180, then increase only after verifying
// motor direction, neutral, current draw and failsafe behavior.
constexpr int MAX_MOTOR_DUTY = 255;

// Control loop and slew rate.
// Smaller ACCEL_STEP = gentler launch.
// Larger DECEL_STEP = faster return toward neutral.
constexpr uint32_t CONTROL_PERIOD_US = 5000;
constexpr int ACCEL_STEP = 6;
constexpr int DECEL_STEP = 12;

// Serial diagnostics period.
constexpr uint32_t DIAG_PERIOD_MS = 250;

// -----------------------------------------------------------------------------
// PIN ASSIGNMENT - ESP32-S3 DevKitC-1
// -----------------------------------------------------------------------------

// RC PWM inputs from SpeedyBee F405 V4 / ArduRover.
// In paired mode only GPIO4 and GPIO5 are required.
constexpr uint8_t RC_IN_PIN[4] = {
  4,  // LEFT or Motor 0
  5,  // RIGHT or Motor 1
  6,  // Motor 2 - independent mode only
  7   // Motor 3 - independent mode only
};

// BTS7960 outputs.
// Motor order:
//   0 = Front Left
//   1 = Rear Left
//   2 = Front Right
//   3 = Rear Right
constexpr uint8_t RPWM_PIN[4] = {8, 10, 12, 14};
constexpr uint8_t LPWM_PIN[4] = {9, 11, 13, 15};

// Reverse a motor in software if mechanical mounting/wiring makes it run
// opposite to the intended rover direction.
constexpr bool INVERT_MOTOR[4] = {
  false,  // Front Left
  false,  // Rear Left
  false,  // Front Right
  false   // Rear Right
};

// -----------------------------------------------------------------------------
// RC INPUT CAPTURE
// -----------------------------------------------------------------------------

portMUX_TYPE captureMux = portMUX_INITIALIZER_UNLOCKED;
volatile bool riseSeen[4] = {}, pulseValid[4] = {};
bool snapshotValid[4] = {};
uint32_t snapshotLastUs[4] = {};
uint16_t snapshotPulseUs[4] = {};

volatile uint32_t riseUs[4] = {0, 0, 0, 0};
volatile uint32_t lastValidPulseUs[4] = {0, 0, 0, 0};
volatile uint16_t pulseWidthUs[4] = {
  RC_CENTER_US, RC_CENTER_US, RC_CENTER_US, RC_CENTER_US
};

static inline void IRAM_ATTR captureEdge(uint8_t ch) {
  const uint32_t now = micros();
  portENTER_CRITICAL_ISR(&captureMux);
  if (digitalRead(RC_IN_PIN[ch])) {
    riseUs[ch] = now; riseSeen[ch] = true;
  } else {
    const uint32_t width = now - riseUs[ch];
    pulseValid[ch] = riseSeen[ch] && width >= RC_VALID_MIN_US && width <= RC_VALID_MAX_US;
    if (pulseValid[ch]) {pulseWidthUs[ch] = uint16_t(width); lastValidPulseUs[ch] = now;}
    riseSeen[ch] = false;
  }
  portEXIT_CRITICAL_ISR(&captureMux);
}

void snapshotInputs() {
  portENTER_CRITICAL(&captureMux);
  for (uint8_t i = 0; i < 4; ++i) {
    snapshotPulseUs[i] = pulseWidthUs[i]; snapshotLastUs[i] = lastValidPulseUs[i]; snapshotValid[i] = pulseValid[i];
  }
  portEXIT_CRITICAL(&captureMux);
}

void IRAM_ATTR rc0ISR() { captureEdge(0); }
void IRAM_ATTR rc1ISR() { captureEdge(1); }
void IRAM_ATTR rc2ISR() { captureEdge(2); }
void IRAM_ATTR rc3ISR() { captureEdge(3); }

// -----------------------------------------------------------------------------
// MOTOR PWM OUTPUT
// -----------------------------------------------------------------------------

#if ESP_ARDUINO_VERSION_MAJOR < 3
constexpr uint8_t RPWM_CH[4] = {0, 2, 4, 6};
constexpr uint8_t LPWM_CH[4] = {1, 3, 5, 7};
#endif

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

static inline void pwmWritePin(uint8_t motor, bool rpwm, uint8_t duty) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(rpwm ? RPWM_PIN[motor] : LPWM_PIN[motor], duty);
#else
  ledcWrite(rpwm ? RPWM_CH[motor] : LPWM_CH[motor], duty);
#endif
}

// command range: -MAX_MOTOR_DUTY ... +MAX_MOTOR_DUTY
void setBtsMotor(uint8_t motor, int command) {
  command = constrain(command, -MAX_MOTOR_DUTY, MAX_MOTOR_DUTY);

  if (INVERT_MOTOR[motor]) {
    command = -command;
  }

  if (command > 0) {
    // Forward: RPWM active, LPWM off.
    pwmWritePin(motor, false, 0);
    pwmWritePin(motor, true, static_cast<uint8_t>(command));
  } else if (command < 0) {
    // Reverse: LPWM active, RPWM off.
    pwmWritePin(motor, true, 0);
    pwmWritePin(motor, false, static_cast<uint8_t>(-command));
  } else {
    // Neutral: both PWM inputs low. Actual braking depends on the driver.
    pwmWritePin(motor, true, 0);
    pwmWritePin(motor, false, 0);
  }
}

void stopAllMotors() {
  for (uint8_t i = 0; i < 4; ++i) {
    setBtsMotor(i, 0);
  }
}

// -----------------------------------------------------------------------------
// SIGNAL PROCESSING
// -----------------------------------------------------------------------------

bool channelFresh(uint8_t ch, uint32_t nowUs) {
  return snapshotValid[ch] && uint32_t(nowUs - snapshotLastUs[ch]) < RC_TIMEOUT_US;
}

int rcPulseToCommand(uint16_t us) {
  us = constrain(us, RC_MIN_US, RC_MAX_US);
  const int delta = static_cast<int>(us) - RC_CENTER_US;

  if (abs(delta) <= RC_DEADBAND_US) {
    return 0;
  }

  int command;

  if (delta > 0) {
    command = map(
      delta,
      RC_DEADBAND_US,
      RC_MAX_US - RC_CENTER_US,
      0,
      MAX_MOTOR_DUTY
    );
  } else {
    command = -map(
      -delta,
      RC_DEADBAND_US,
      RC_CENTER_US - RC_MIN_US,
      0,
      MAX_MOTOR_DUTY
    );
  }

  return constrain(command, -MAX_MOTOR_DUTY, MAX_MOTOR_DUTY);
}

// Slew toward target.
// A commanded direction reversal MUST reach zero before the opposite
// polarity is allowed.
int slewToward(int current, int target) {
  if (current == target) {
    return current;
  }

  // Explicit reversal handling: decelerate to zero first.
  if ((current > 0 && target < 0) || (current < 0 && target > 0)) {
    if (abs(current) <= DECEL_STEP) {
      return 0;
    }
    return (current > 0) ? (current - DECEL_STEP)
                         : (current + DECEL_STEP);
  }

  // Same direction or target is zero.
  const bool magnitudeIncreasing =
      (target != 0) && (abs(target) > abs(current));

  const int step = magnitudeIncreasing ? ACCEL_STEP : DECEL_STEP;

  if (target > current) {
    current += step;
    if (current > target) current = target;
  } else {
    current -= step;
    if (current < target) current = target;
  }

  return current;
}

// -----------------------------------------------------------------------------
// RUNTIME
// -----------------------------------------------------------------------------

int currentCmd[4] = {0, 0, 0, 0};
int targetCmd[4]  = {0, 0, 0, 0};

uint32_t lastControlUs = 0, lastDiagMs = 0;
bool motorPwmReady = false, sourceEnabled = false, neutralTracking = false;
uint32_t neutralSinceUs = 0, snapshotAtUs = 0;

void hardStop() {
  sourceEnabled = false; neutralTracking = false;
  for (uint8_t i = 0; i < 4; ++i) { currentCmd[i] = targetCmd[i] = 0; }
  stopAllMotors();
}

bool computeTargets(uint32_t nowUs) {
  if (PAIRED_SKID_STEER) {
    if (!channelFresh(0, nowUs) || !channelFresh(1, nowUs)) return false;
    targetCmd[0] = targetCmd[1] = rcPulseToCommand(snapshotPulseUs[0]);
    targetCmd[2] = targetCmd[3] = rcPulseToCommand(snapshotPulseUs[1]);
    return true;
  }
  bool anyLost = false, anyFresh = false;
  for (uint8_t i = 0; i < 4; ++i) {
    const bool fresh = channelFresh(i, nowUs);
    anyLost |= !fresh; anyFresh |= fresh;
    targetCmd[i] = fresh ? rcPulseToCommand(snapshotPulseUs[i]) : 0;
  }
  return anyFresh && (!FAILSAFE_ALL_STOP || !anyLost);
}

void updateMotors() {
  for (uint8_t i = 0; i < 4; ++i) {
    if (!PAIRED_SKID_STEER && !channelFresh(i, snapshotAtUs)) currentCmd[i] = 0;
    else currentCmd[i] = slewToward(currentCmd[i], targetCmd[i]);
    setBtsMotor(i, currentCmd[i]);
  }
}

void printDiagnostics(uint32_t nowUs) {
  const uint32_t nowMs = millis();
  if (uint32_t(nowMs - lastDiagMs) < DIAG_PERIOD_MS) return;
  lastDiagMs = nowMs;
  char diagnostic[192];
  const int n = snprintf(diagnostic, sizeof(diagnostic),
      "RC(us): %u%c %u%c %u%c %u%c | CMD: %d %d %d %d | source=%s PWM=%s\n",
      snapshotPulseUs[0], channelFresh(0, nowUs)?'*':'!', snapshotPulseUs[1], channelFresh(1, nowUs)?'*':'!',
      snapshotPulseUs[2], channelFresh(2, nowUs)?'*':'!', snapshotPulseUs[3], channelFresh(3, nowUs)?'*':'!',
      currentCmd[0], currentCmd[1], currentCmd[2], currentCmd[3],
      sourceEnabled?"enabled":"neutral-wait", motorPwmReady?"ready":"failed");
  if (n > 0 && n < int(sizeof(diagnostic)) && Serial.availableForWrite() >= n)
    Serial.write(reinterpret_cast<const uint8_t*>(diagnostic), size_t(n));
}

void setup() {
  // Establish the output-low state before startup delay, diagnostics or input capture.
  for (uint8_t i = 0; i < 4; ++i) {
    pinMode(RPWM_PIN[i], OUTPUT); pinMode(LPWM_PIN[i], OUTPUT);
    digitalWrite(RPWM_PIN[i], LOW); digitalWrite(LPWM_PIN[i], LOW);
  }
  hardStop();
  Serial.begin(115200);
  delay(250);

  Serial.println();
  Serial.println("TeleRC 4x BTS7960 PWM Converter");
  Serial.println(PAIRED_SKID_STEER
                 ? "Mode: paired skid-steer (2 RC inputs -> 4 BTS7960)"
                 : "Mode: 4 independent RC inputs");

  for (uint8_t i = 0; i < 4; ++i) {
    pinMode(RC_IN_PIN[i], INPUT_PULLDOWN);
  }

  attachInterrupt(digitalPinToInterrupt(RC_IN_PIN[0]), rc0ISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(RC_IN_PIN[1]), rc1ISR, CHANGE);

  if (!PAIRED_SKID_STEER) {
    attachInterrupt(digitalPinToInterrupt(RC_IN_PIN[2]), rc2ISR, CHANGE);
    attachInterrupt(digitalPinToInterrupt(RC_IN_PIN[3]), rc3ISR, CHANGE);
  }

  motorPwmReady = attachMotorPwm();
  hardStop();
  Serial.println(motorPwmReady ? "Outputs neutral; waiting for 300 ms of fresh neutral inputs."
                             : "FATAL: PWM attachment failed; outputs inhibited.");
}

void loop() {
  snapshotInputs();
  const uint32_t nowUs = micros();
  snapshotAtUs = nowUs;
  if (uint32_t(nowUs - lastControlUs) >= CONTROL_PERIOD_US) {
    lastControlUs = nowUs;
    if (!motorPwmReady || !computeTargets(nowUs)) hardStop();
    else {
      if (!sourceEnabled) {
        bool neutral = true;
        for (uint8_t i = 0; i < (PAIRED_SKID_STEER ? 2 : 4); ++i)
          if (channelFresh(i, nowUs)) neutral &= abs(int(snapshotPulseUs[i]) - int(RC_CENTER_US)) <= RC_DEADBAND_US;
        if (!neutral) neutralTracking = false;
        else if (!neutralTracking) {neutralTracking = true; neutralSinceUs = nowUs;}
        else if (uint32_t(nowUs - neutralSinceUs) >= SOURCE_NEUTRAL_DWELL_US) sourceEnabled = true;
      }
      if (sourceEnabled) updateMotors(); else stopAllMotors();
    }
  }
  printDiagnostics(nowUs);
}

