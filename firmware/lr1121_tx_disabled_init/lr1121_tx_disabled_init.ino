/*
 * lr1121_tx_disabled_init
 * -----------------------
 * Safe read-only LR1121 bring-up + diagnostic firmware for LEO-DTF
 * H0 / H0.5 / H0.5B on a Nucleo-64 (NUCLEO_L476RG).
 *
 * SAFETY CONTRACT (do not weaken):
 *   - TX is DISABLED by default and at all times in this build.
 *   - No automatic transmission in setup() or loop().
 *   - Only READ-ONLY LR1121 SPI commands are issued (GetVersion-style probe).
 *   - No LR1121 radio TX/send API is invoked anywhere in this build.
 *   - The `tx` serial command is intentionally BLOCKED.
 *   - This firmware does NOT prove HIL/OTA/hardware validation.
 *
 * H0.5B adds a read-only SPI diagnostic sweep across candidate pin maps, SPI
 * settings, and command framing variants to find a plausible LR1121 response.
 */

#include <SPI.h>

// ---- Build identity ---------------------------------------------------------
static const char *FW_NAME    = "lr1121_tx_disabled_init";
static const char *FW_VERSION = "0.3.0";
static const char *BOARD_TGT  = "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_L476RG";
static const long  SERIAL_BAUD = 115200;

// ---- Safety flags (compile-time constants; not runtime-togglable) -----------
static const bool RF_TRANSMISSION_ENABLED      = false;
static const bool PACKET_TRANSMISSION_EXECUTED = false;
static const bool HIL_VALIDATION_COMPLETE      = false;
static const bool TX_DEFAULT_DISABLED          = true;

// SPI data pins are the Arduino default SPI1 (fixed): MOSI=D11, MISO=D12, SCK=D13.
static const int PIN_MOSI = D11;
static const int PIN_MISO = D12;
static const int PIN_SCK  = D13;

// ---- Candidate pin maps -----------------------------------------------------
struct LrPinMap {
  const char *name;
  int nss;
  int busy;
  int reset;
  int dio;
};

static const LrPinMap CANDIDATES[] = {
  {"map_current",                 D10, D8, D9, D3},
  {"map_alt_shield",              D7,  D3, A0, D5},
  {"map_alt_reset_d9",           D7,  D3, D9, D5},
  {"map_alt_busy_d8",            D7,  D8, A0, D5},
  {"map_cs_d10_busy_d3_reset_a0", D10, D3, A0, D5},
};
static const int N_CANDIDATES = sizeof(CANDIDATES) / sizeof(CANDIDATES[0]);

// ---- SPI settings to try ----------------------------------------------------
struct SpiCfg {
  uint8_t mode;
  uint32_t hz;
};
static const SpiCfg SPI_CFGS[] = {
  {0, 125000},
  {0, 500000},
  {0, 1000000},
  {0, 4000000},
  {3, 500000},   // diagnostic fallback only
};
static const int N_SPI_CFGS = sizeof(SPI_CFGS) / sizeof(SPI_CFGS[0]);

// ---- Command framing variants ----------------------------------------------
static const char *VARIANTS[] = {
  "variant_raw_0101",
  "variant_status_prefixed",
  "variant_dummy_before_read",
};
static const int N_VARIANTS = 3;

static const uint16_t LR_CMD_GET_VERSION = 0x0101;
static const int RESP_LEN = 10;

static bool g_spi_ready = false;
static bool g_probe_plausible = false;

static uint8_t spiMode(uint8_t m) {
  switch (m) {
    case 1: return SPI_MODE1;
    case 2: return SPI_MODE2;
    case 3: return SPI_MODE3;
    default: return SPI_MODE0;
  }
}

static bool waitBusyLow(int busyPin, uint32_t timeout_ms) {
  uint32_t t0 = millis();
  while (digitalRead(busyPin) == HIGH) {
    if (millis() - t0 > timeout_ms) return false;
  }
  return true;
}

static void configurePins(const LrPinMap &m) {
  pinMode(m.nss, OUTPUT);
  digitalWrite(m.nss, HIGH);     // deselect
  pinMode(m.reset, OUTPUT);
  digitalWrite(m.reset, HIGH);
  pinMode(m.busy, INPUT);
  pinMode(m.dio, INPUT);
}

static void pulseReset(const LrPinMap &m) {
  digitalWrite(m.reset, LOW);
  delay(2);
  digitalWrite(m.reset, HIGH);
  delay(5);
}

// READ-ONLY probe. Issues only the GetVersion opcode then clocks dummy bytes to
// read a response. No TX command is ever sent.
static void doProbe(const LrPinMap &m, const SpiCfg &cfg, int variant,
                    uint8_t *resp, int *busy_before, int *busy_after) {
  for (int i = 0; i < RESP_LEN; i++) resp[i] = 0;

  *busy_before = digitalRead(m.busy);
  pulseReset(m);
  waitBusyLow(m.busy, 50);
  *busy_after = digitalRead(m.busy);

  SPISettings settings(cfg.hz, MSBFIRST, spiMode(cfg.mode));

  // Send GetVersion opcode (read-only command).
  SPI.beginTransaction(settings);
  digitalWrite(m.nss, LOW);
  SPI.transfer((uint8_t)(LR_CMD_GET_VERSION >> 8));
  SPI.transfer((uint8_t)(LR_CMD_GET_VERSION & 0xFF));
  digitalWrite(m.nss, HIGH);
  SPI.endTransaction();

  waitBusyLow(m.busy, 50);

  // Read response with framing variant differences (dummy-byte offsets).
  int lead = 0;
  if (variant == 1) lead = 1;       // variant_status_prefixed
  else if (variant == 2) lead = 2;  // variant_dummy_before_read

  SPI.beginTransaction(settings);
  digitalWrite(m.nss, LOW);
  for (int i = 0; i < lead; i++) SPI.transfer(0x00);   // discard leading dummy bytes
  for (int i = 0; i < RESP_LEN; i++) resp[i] = SPI.transfer(0x00);
  digitalWrite(m.nss, HIGH);
  SPI.endTransaction();
}

static const char *scoreResponse(const uint8_t *resp) {
  bool all_zero = true, all_ff = true, changing = false;
  for (int i = 0; i < RESP_LEN; i++) {
    if (resp[i] != 0x00) all_zero = false;
    if (resp[i] != 0xFF) all_ff = false;
    if (i > 0 && resp[i] != resp[0]) changing = true;
  }
  if (all_zero) return "all_zero";
  if (all_ff) return "all_ff";
  if (changing) return "changing_nonzero";
  return "repeated_nonzero";
}

static const char *interpret(const char *score) {
  if (strcmp(score, "all_zero") == 0) return "bad_likely_power_wiring_miso";
  if (strcmp(score, "all_ff") == 0) return "bad_likely_floating_miso_or_cs";
  return "plausible";
}

static void printResponseHex(const uint8_t *resp) {
  for (int i = 0; i < RESP_LEN; i++) {
    if (resp[i] < 0x10) Serial.print('0');
    Serial.print(resp[i], HEX);
    if (i < RESP_LEN - 1) Serial.print('-');
  }
}

static void runSweep() {
  g_probe_plausible = false;
  Serial.println(F("SWEEP_BEGIN"));
  Serial.println(F("LR1121_SPI_PROBE_ATTEMPTED=true"));
  Serial.println(F("header,RESULT,map,spi_mode,spi_hz,busy_before,busy_after,variant,response_hex,score,interpretation"));
  for (int c = 0; c < N_CANDIDATES; c++) {
    const LrPinMap &m = CANDIDATES[c];
    configurePins(m);
    for (int s = 0; s < N_SPI_CFGS; s++) {
      for (int v = 0; v < N_VARIANTS; v++) {
        uint8_t resp[RESP_LEN];
        int bb = -1, ba = -1;
        doProbe(m, SPI_CFGS[s], v, resp, &bb, &ba);
        const char *score = scoreResponse(resp);
        const char *interp = interpret(score);
        if (strcmp(interp, "plausible") == 0) g_probe_plausible = true;
        Serial.print(F("RESULT,"));
        Serial.print(m.name); Serial.print(',');
        Serial.print(SPI_CFGS[s].mode); Serial.print(',');
        Serial.print(SPI_CFGS[s].hz); Serial.print(',');
        Serial.print(bb); Serial.print(',');
        Serial.print(ba); Serial.print(',');
        Serial.print(VARIANTS[v]); Serial.print(',');
        printResponseHex(resp); Serial.print(',');
        Serial.print(score); Serial.print(',');
        Serial.println(interp);
      }
    }
  }
  Serial.print(F("SPI_PROBE_PLAUSIBLE="));
  Serial.println(g_probe_plausible ? "true" : "false");
  Serial.println(F("SWEEP_END"));
}

static void spiInit() {
  SPI.begin();
  g_spi_ready = true;
  Serial.print(F("SPI_INIT_STATUS="));
  Serial.println(g_spi_ready ? "ok" : "fail");
}

static void printPins() {
  Serial.println(F("---- candidate pin maps ----"));
  for (int c = 0; c < N_CANDIDATES; c++) {
    const LrPinMap &m = CANDIDATES[c];
    Serial.print(m.name);
    Serial.print(F(": NSS=")); Serial.print(m.nss);
    Serial.print(F(" BUSY=")); Serial.print(m.busy);
    Serial.print(F(" RESET=")); Serial.print(m.reset);
    Serial.print(F(" DIO=")); Serial.println(m.dio);
  }
  Serial.print(F("SPI_MOSI=")); Serial.print(PIN_MOSI);
  Serial.print(F(" SPI_MISO=")); Serial.print(PIN_MISO);
  Serial.print(F(" SPI_SCK=")); Serial.println(PIN_SCK);
}

static void printBanner() {
  Serial.println();
  Serial.println(F("==== LEO-DTF H0.5B firmware ===="));
  Serial.print(F("firmware_name="));    Serial.println(FW_NAME);
  Serial.print(F("firmware_version=")); Serial.println(FW_VERSION);
  Serial.print(F("board_target="));     Serial.println(BOARD_TGT);
  Serial.print(F("serial_baud="));      Serial.println(SERIAL_BAUD);
  Serial.println(F("---- safety flags ----"));
  Serial.print(F("TX_DEFAULT_DISABLED="));          Serial.println(TX_DEFAULT_DISABLED ? "true" : "false");
  Serial.print(F("RF_TRANSMISSION_ENABLED="));      Serial.println(RF_TRANSMISSION_ENABLED ? "true" : "false");
  Serial.print(F("PACKET_TRANSMISSION_EXECUTED=")); Serial.println(PACKET_TRANSMISSION_EXECUTED ? "true" : "false");
  Serial.print(F("HIL_VALIDATION_COMPLETE="));      Serial.println(HIL_VALIDATION_COMPLETE ? "true" : "false");
}

static void printStatus() {
  Serial.println(F("---- status ----"));
  Serial.print(F("spi_ready="));               Serial.println(g_spi_ready ? "true" : "false");
  Serial.print(F("spi_probe_plausible="));     Serial.println(g_probe_plausible ? "true" : "false");
  Serial.print(F("RF_TRANSMISSION_ENABLED=")); Serial.println(RF_TRANSMISSION_ENABLED ? "true" : "false");
  Serial.println(F("READY"));
}

static void printHelp() {
  Serial.println(F("commands: help | status | pins | version | sweep | tx(blocked)"));
}

static void handleCommand(const String &cmd) {
  if (cmd == "status") {
    printStatus();
  } else if (cmd == "pins") {
    printPins();
  } else if (cmd == "version" || cmd == "sweep") {
    runSweep();
  } else if (cmd == "help") {
    printHelp();
  } else if (cmd == "tx") {
    Serial.println(F("TX command blocked in this firmware build"));
  } else if (cmd.length() > 0) {
    Serial.print(F("unknown command: "));
    Serial.println(cmd);
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0) < 3000) { /* wait up to 3s for USB serial */ }

  printBanner();
  spiInit();
  printPins();
  printStatus();
  printHelp();
  // NOTE: no transmission and no auto-sweep here. Send `sweep` to diagnose.
}

void loop() {
  // No automatic transmission. Only respond to safe serial commands.
  static String line;
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      line.trim();
      if (line.length() > 0) {
        handleCommand(line);
      }
      line = "";
    } else {
      line += c;
    }
  }
}
