#include "buttons.h"

ButtonScanner::ButtonScanner(TinyScreen& display, const hw::ButtonConfig* buttons, int count,
                             unsigned long debounceMs, unsigned long holdMs)
    : display_(display), debounceMs_(debounceMs), holdMs_(holdMs) {
  for (int i = 0; i < count; i++) {
    State state;
    state.id = buttons[i].id;
    state.mask = buttons[i].mask;
    states_.push_back(state);
  }
}

bool ButtonScanner::rawDown(const State& state) const {
  return display_.getButtons(state.mask) != 0;
}

void ButtonScanner::resetUntilRelease() {
  for (State& state : states_) {
    if (rawDown(state)) state.suppressed = true;
    state.stableDown = false;
    state.candidateDown = rawDown(state);
    state.holdFired = false;
  }
}

std::vector<Gesture> ButtonScanner::poll(unsigned long nowMs, long controlEpoch) {
  std::vector<Gesture> gestures;
  for (State& state : states_) {
    Gesture gesture;
    if (pollOne(state, nowMs, controlEpoch, gesture)) gestures.push_back(gesture);
  }
  return gestures;
}

bool ButtonScanner::pollOne(State& state, unsigned long nowMs, long controlEpoch,
                            Gesture& outGesture) {
  bool rawDownNow = rawDown(state);

  if (state.suppressed) {
    if (!rawDownNow) state.suppressed = false;
    return false;
  }

  if (rawDownNow != state.candidateDown) {
    state.candidateDown = rawDownNow;
    state.candidateSince = nowMs;
    return false;
  }
  if ((unsigned long)(nowMs - state.candidateSince) < debounceMs_) return false;

  if (rawDownNow && !state.stableDown) {
    state.stableDown = true;
    state.downSince = nowMs;
    state.epoch = controlEpoch;
    state.holdFired = false;
    return false;
  }

  if (rawDownNow && state.stableDown && !state.holdFired) {
    if ((unsigned long)(nowMs - state.downSince) >= holdMs_) {
      state.holdFired = true;
      outGesture = {state.id, "hold", state.epoch};
      return true;
    }
    return false;
  }

  if (!rawDownNow && state.stableDown) {
    state.stableDown = false;
    if (state.holdFired) return false;
    outGesture = {state.id, "press", state.epoch};
    return true;
  }

  return false;
}
