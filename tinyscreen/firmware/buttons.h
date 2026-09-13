// Per-button debounce and press/hold gesture detection.
//
// Ported from ../../pico/buttons.py. Firmware only reports "button N was
// pressed/held"; it never decides what that means (see
// ../../docs/system_design.md). Reads TinyScreen+'s onboard button register
// via `TinyScreen::getButtons()` instead of raw GPIO, since all four buttons
// are built into this board.
#pragma once

#include <Arduino.h>
#include <TinyScreen.h>
#undef min
#undef max
#include <vector>

#include "hardware_config.h"

struct Gesture {
  int button;
  const char* action;  // "press" | "hold"
  long controlEpoch;
};

class ButtonScanner {
 public:
  ButtonScanner(TinyScreen& display, const hw::ButtonConfig* buttons, int count,
                unsigned long debounceMs, unsigned long holdMs);

  // Suppress already-held buttons across a boot/connection reset.
  void resetUntilRelease();

  // Read the button register; latch epoch at stable-down; emit each
  // gesture once.
  std::vector<Gesture> poll(unsigned long nowMs, long controlEpoch);

 private:
  struct State {
    int id;
    uint8_t mask;
    bool candidateDown = false;
    unsigned long candidateSince = 0;
    bool stableDown = false;
    unsigned long downSince = 0;
    long epoch = 0;
    bool holdFired = false;
    bool suppressed = false;
  };

  TinyScreen& display_;
  unsigned long debounceMs_;
  unsigned long holdMs_;
  std::vector<State> states_;

  bool rawDown(const State& state) const;
  bool pollOne(State& state, unsigned long nowMs, long controlEpoch, Gesture& outGesture);
};
