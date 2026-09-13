// TinyScreen+ hardware wiring: onboard buttons, timing and screen size.
//
// Confirmed hardware: TinyCircuits TinyScreen+ (Atmel SAMD21G18A), identified
// via its USB descriptor (VID 03EB) and Windows' BusReportedDeviceDesc
// "TinyScreen+". Unlike the RP2040 Pico this project originally assumed, the
// display and all four buttons are built onto the board itself -- no GPIO
// wiring or separate SPI display driver is needed. See
// ../../docs/design_decisions.md for the board-switch rationale.
#pragma once

#include <TinyScreen.h>
#include <stdint.h>

namespace hw {

constexpr unsigned long DEBOUNCE_MS = 20;
constexpr unsigned long HOLD_MS = 600;

struct ButtonConfig {
  int id;
  uint8_t mask;
};

// One entry per physical button, in wire-protocol advertisement order.
// TinyScreen+ has four built-in buttons; all four are exposed here (the
// original 2-button GPIO layout in pico/hardware_config.py does not apply
// to this board).
constexpr ButtonConfig BUTTONS[] = {
    {1, TSButtonUpperLeft},
    {2, TSButtonUpperRight},
    {3, TSButtonLowerLeft},
    {4, TSButtonLowerRight},
};
constexpr int BUTTON_COUNT = sizeof(BUTTONS) / sizeof(BUTTONS[0]);

constexpr int SCREEN_WIDTH = 96;
constexpr int SCREEN_HEIGHT = 64;

}  // namespace hw
