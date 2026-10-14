/*
 * so101_force.ino  --  TAL221 mini load cell + HX711 + Arduino Nano
 * Force probe firmware for the SO-101 (LeRobot) thumbstick-pushing jig.
 *
 * Library : "HX711 Arduino Library" by Bogdan Necula (github.com/bogde/HX711),
 *           tested with release 0.7.5.  NOTE: in the Arduino Library Manager
 *           there is ALSO a library simply called "HX711" by Rob Tillaart -
 *           that is a DIFFERENT library and this sketch will not build with it.
 *           arduino-cli:  arduino-cli lib install "HX711 Arduino Library"
 * Board   : Arduino Nano (ATmega328P)  FQBN arduino:avr:nano
 *           (clones with the old bootloader: arduino:avr:nano:cpu=atmega328old)
 *
 * Wiring (HX711 board -> Nano):
 *   DAT / DT / DOUT -> D2      CLK / SCK / PD_SCK -> D3
 *   VCC (and VDD on SparkFun board) -> 5V        GND -> GND
 *
 * Serial: 115200 baud, lines end with "\r\n".
 *   Data line   : F,<millis>,<grams>        e.g.  F,123456,12.34
 *                 (grams = "nan" until a calibration is stored)
 *   Reply lines : OK,...  /  ERR,...  /  R,...
 *   Info lines  : start with '#'  (PC software should ignore them)
 *
 * Commands (type in Serial Monitor, newline at the end):
 *   t          tare: set zero (NOTHING may touch the probe tip)
 *   c<grams>   calibrate with a known weight resting on the tip, e.g. c100
 *              (do 't' first with no weight). Scale factor is saved to EEPROM.
 *   r          print one raw reading:  R,<millis>,<raw_avg>,<offset>,<counts_per_gram>
 *   a<n>       moving-average window, n = 1..16 (default 4, not saved)
 *   ?          help + current settings
 *
 * Sign convention: calibrate with the weight pressing the tip the SAME way the
 * thumbstick will press back on it. Then pushing = positive grams.
 */

#include <EEPROM.h>
#include <math.h>
#include <stdlib.h>
#include "HX711.h"

// ---------------- user settings ----------------
const uint8_t  PIN_DOUT        = 2;      // HX711 DAT/DT/DOUT
const uint8_t  PIN_SCK         = 3;      // HX711 CLK/SCK
const long     BAUD            = 115200;
const uint8_t  DEFAULT_WINDOW  = 4;      // samples in moving average
const uint8_t  MAX_WINDOW      = 16;
const uint8_t  TARE_SAMPLES    = 16;     // samples averaged for t and c
const uint16_t READY_TIMEOUT_MS = 600;   // 10 SPS -> 100 ms per sample
const float    MIN_COUNTS_PER_G = 50.0;  // below this, calibration is rejected

// ---------------- EEPROM layout ----------------
const int      EE_ADDR  = 0;
const uint32_t EE_MAGIC = 0x464F5231UL;  // "FOR1"
struct CalData {
  uint32_t magic;
  float    countsPerGram;
  uint32_t check;      // magic XOR raw bits of countsPerGram
};

HX711 scale;

float   countsPerGram = NAN;   // NAN = not calibrated
long    offsetRaw     = 0;
long    ring[MAX_WINDOW];
uint8_t window        = DEFAULT_WINDOW;
uint8_t ringCount     = 0;
uint8_t ringPos       = 0;
unsigned long lastSampleMs = 0;
unsigned long lastWarnMs   = 0;

char    cmdBuf[24];
uint8_t cmdLen = 0;

// ------------------------------------------------
static uint32_t floatBits(float f) {
  uint32_t u;
  memcpy(&u, &f, sizeof(u));
  return u;
}

static bool loadCalibration() {
  CalData d;
  EEPROM.get(EE_ADDR, d);
  if (d.magic != EE_MAGIC) return false;
  if (d.check != (d.magic ^ floatBits(d.countsPerGram))) return false;
  if (isnan(d.countsPerGram) || isinf(d.countsPerGram)) return false;
  if (fabs(d.countsPerGram) < MIN_COUNTS_PER_G) return false;
  countsPerGram = d.countsPerGram;
  return true;
}

static void saveCalibration(float cpg) {
  CalData d;
  d.magic = EE_MAGIC;
  d.countsPerGram = cpg;
  d.check = d.magic ^ floatBits(cpg);
  EEPROM.put(EE_ADDR, d);   // put() only rewrites bytes that changed
}

// Read one raw sample, waiting at most READY_TIMEOUT_MS. Returns false on timeout.
static bool readRaw(long &out) {
  if (!scale.wait_ready_timeout(READY_TIMEOUT_MS, 1)) return false;
  out = scale.read();
  return true;
}

// Average n raw samples (blocking, with timeout). Returns false on timeout.
static bool readRawAverage(uint8_t n, long &out) {
  long long sum = 0;
  for (uint8_t i = 0; i < n; i++) {
    long v;
    if (!readRaw(v)) return false;
    sum += v;
  }
  out = (long)(sum / n);
  return true;
}

static void resetRing() {
  ringCount = 0;
  ringPos = 0;
}

static void pushRing(long v) {
  ring[ringPos] = v;
  ringPos = (ringPos + 1) % window;
  if (ringCount < window) ringCount++;
}

static long ringAverage() {
  long long sum = 0;
  for (uint8_t i = 0; i < ringCount; i++) sum += ring[i];
  return ringCount ? (long)(sum / ringCount) : 0;
}

static void printHelp() {
  Serial.println(F("# so101_force  commands: t=tare  c<grams>=calibrate  r=raw  a<n>=avg window  ?=help"));
  Serial.print(F("# counts_per_gram="));
  if (isnan(countsPerGram)) Serial.println(F("NOT_CALIBRATED"));
  else Serial.println(countsPerGram, 3);
  Serial.print(F("# offset_raw="));
  Serial.print(offsetRaw);
  Serial.print(F(" window="));
  Serial.println(window);
}

static void doTare() {
  long avg;
  if (!readRawAverage(TARE_SAMPLES, avg)) {
    Serial.println(F("ERR,TARE,HX711_NOT_READY"));
    return;
  }
  offsetRaw = avg;
  resetRing();
  Serial.print(F("OK,TARE,"));
  Serial.println(offsetRaw);
}

static void doCalibrate(const char *arg) {
  float grams = atof(arg);
  if (!(grams > 0.0f)) {
    Serial.println(F("ERR,CAL,USAGE: c<grams>  e.g. c100"));
    return;
  }
  long avg;
  if (!readRawAverage(TARE_SAMPLES, avg)) {
    Serial.println(F("ERR,CAL,HX711_NOT_READY"));
    return;
  }
  float cpg = (float)(avg - offsetRaw) / grams;
  if (fabs(cpg) < MIN_COUNTS_PER_G) {
    Serial.print(F("ERR,CAL,SIGNAL_TOO_SMALL,"));
    Serial.println(cpg, 3);
    Serial.println(F("# Did you tare (t) with no weight first? Is the weight on the TIP? Check wiring."));
    return;
  }
  countsPerGram = cpg;
  saveCalibration(cpg);
  resetRing();
  Serial.print(F("OK,CAL,"));
  Serial.println(countsPerGram, 3);
}

static void doRaw() {
  long avg;
  if (!readRawAverage(window, avg)) {
    Serial.println(F("ERR,RAW,HX711_NOT_READY"));
    return;
  }
  Serial.print(F("R,"));
  Serial.print(millis());
  Serial.print(',');
  Serial.print(avg);
  Serial.print(',');
  Serial.print(offsetRaw);
  Serial.print(',');
  if (isnan(countsPerGram)) Serial.println(F("nan"));
  else Serial.println(countsPerGram, 3);
}

static void handleCommand(char *s) {
  while (*s == ' ') s++;
  if (*s == '\0') return;
  char c = *s;
  if (c >= 'A' && c <= 'Z') c = c - 'A' + 'a';
  char *arg = s + 1;
  while (*arg == ' ') arg++;
  switch (c) {
    case 't': doTare(); break;
    case 'c': doCalibrate(arg); break;
    case 'r': doRaw(); break;
    case 'a': {
      int n = atoi(arg);
      if (n < 1 || n > MAX_WINDOW) {
        Serial.println(F("ERR,AVG,RANGE_1_16"));
      } else {
        window = (uint8_t)n;
        resetRing();
        Serial.print(F("OK,AVG,"));
        Serial.println(window);
      }
      break;
    }
    case '?': case 'h': printHelp(); break;
    default:
      Serial.print(F("ERR,UNKNOWN,"));
      Serial.println(s);
  }
}

static void pollSerial() {
  while (Serial.available() > 0) {
    char ch = (char)Serial.read();
    if (ch == '\n' || ch == '\r') {
      cmdBuf[cmdLen] = '\0';
      handleCommand(cmdBuf);
      cmdLen = 0;
    } else if (cmdLen < sizeof(cmdBuf) - 1) {
      cmdBuf[cmdLen++] = ch;
    }
  }
}

void setup() {
  Serial.begin(BAUD);
  scale.begin(PIN_DOUT, PIN_SCK);      // channel A, gain 128
  // Library 0.7.5 leaves DOUT as plain INPUT on AVR; a pull-up makes a
  // disconnected HX711 read as "not ready" instead of random numbers.
  pinMode(PIN_DOUT, INPUT_PULLUP);

  Serial.println(F("# so101_force v1.0 (TAL221 + HX711, DOUT=D2 SCK=D3)"));
  if (loadCalibration()) {
    Serial.print(F("# calibration loaded from EEPROM, counts_per_gram="));
    Serial.println(countsPerGram, 3);
  } else {
    Serial.println(F("# NOT CALIBRATED: send t (no load), put a known weight on the tip, send c<grams>"));
  }
  delay(400);                          // let HX711 settle after power-up
  Serial.println(F("# auto-tare at boot: do not touch the probe"));
  doTare();
  lastSampleMs = millis();
}

void loop() {
  pollSerial();

  if (scale.is_ready()) {
    long v = scale.read();
    lastSampleMs = millis();
    if (v >= 8388607L || v <= -8388608L) {
      // ADC at full scale: open/broken wire or huge overload
      if (millis() - lastWarnMs > 1000) {
        Serial.println(F("# WARN,ADC_SATURATED (check load-cell wires)"));
        lastWarnMs = millis();
      }
    }
    pushRing(v);
    float grams = (float)(ringAverage() - offsetRaw) / countsPerGram;  // NAN if not calibrated
    Serial.print(F("F,"));
    Serial.print(lastSampleMs);
    Serial.print(',');
    if (isnan(grams)) Serial.println(F("nan"));
    else Serial.println(grams, 2);
  } else if (millis() - lastSampleMs > READY_TIMEOUT_MS && millis() - lastWarnMs > 1000) {
    Serial.println(F("# WARN,HX711_NOT_READY (check DAT->D2, CLK->D3, VCC, GND)"));
    lastWarnMs = millis();
  }
}
