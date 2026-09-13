// Desk-pet view state, connection overlay and bounded animation playback.
//
// Ported from ../../pico/display.py. `Renderer` owns exactly what the spec
// allows firmware to know: the last validated view, connection status and a
// bounded, best-effort animation queue. It never infers mood or decides what
// to draw beyond the laptop-selected screen/mood -- see
// ../../docs/serial_protocol.md and ../../docs/class_design.md.
//
// Unlike the original (a placeholder `NullDisplayDriver` awaiting an
// ST7735S driver), this draws directly onto the TinyScreen+'s built-in
// 96x64 OLED via the TinyScreen library.
#pragma once

#include <Arduino.h>
#include <TinyScreen.h>
#undef min
#undef max
#include <vector>

#include "protocol.h"

class Renderer {
 public:
  explicit Renderer(TinyScreen& display);

  // Valid complete view -> atomic desired-view swap and dirty marking.
  void setView(const View& view);

  // Valid cue -> bounded, compatible visual playback only. `foodSprite` is
  // the fed item's configured sprite_id (e.g. "jollof_rice", "espresso"),
  // empty for cues other than "feed".
  void enqueueAnimation(const String& animationId, const String& name,
                        const String& foodSprite = String());

  // Boolean -> connection overlay and stale-animation clearing.
  void setConnected(bool value);

  // Firmware ticks -> bounded drawing/animation work; no game countdown.
  void tick(unsigned long nowMs);

  // The laptop's sound preference, remembered from the last settings-screen
  // view since it applies everywhere, not only while Settings is shown.
  bool soundEnabled() const { return soundEnabled_; }

  bool connected = false;

 private:
  static constexpr size_t kAnimationQueueLimit = 32;

  struct QueuedAnimation {
    String animationId;
    String name;
  };

  TinyScreen& display_;
  bool hasView_ = false;
  View view_;
  std::vector<QueuedAnimation> animationQueue_;
  std::vector<String> recentAnimationIds_;
  bool dirty_ = false;
  int idleFrame_ = 0;
  unsigned long lastIdleSwitchMs_ = 0;
  bool soundEnabled_ = true;

  // Feed animation: frame 0 for kEatFrame0DurationMs, then alternating
  // frames 1/2 for kEatLoopDurationMs, then back to normal mood/screen art.
  // Takes over drawing entirely while active, regardless of screen.
  bool eatAnimationActive_ = false;
  bool eatAnimationStarted_ = false;
  unsigned long eatAnimationStartMs_ = 0;
  int eatAnimationFrame_ = -2;
  String eatAnimationFoodSprite_;

  // Petting animation: alternates its two frames for a fixed duration, then
  // falls back to normal mood/screen art, played once when PetComforted
  // commits (see the laptop's presenter.py).
  bool petAnimationActive_ = false;
  bool petAnimationStarted_ = false;
  unsigned long petAnimationStartMs_ = 0;
  int petAnimationFrame_ = -1;

  // Focus-complete (break_offer) screen: XP/yarn show immediately, but
  // button labels are held back for kFocusCompleteButtonRevealMs so the
  // reward is the only thing drawn at first. The buttons still work when
  // pressed during that window -- only their drawn labels are suppressed.
  bool focusCompleteButtonsRevealed_ = false;
  bool focusCompleteTimerStarted_ = false;
  unsigned long focusCompleteEnteredMs_ = 0;

  bool showingMoodSprite() const;
  void drawText();
  void drawMoodSprite();
  void drawFocusSprite();
  void drawFocusCompleteScreen();
  void drawBreakScreen();
  void drawEatAnimation();
  void drawPetAnimation();
  void drawProgressionHud();
};
