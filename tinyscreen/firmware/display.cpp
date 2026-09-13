#include "display.h"

#include "colors.h"
#include "hardware_config.h"
#include "icons.h"
#include "sprites.h"

namespace {

constexpr int kMargin = 2;
const FONT_INFO& kSmallFont = thinPixel7_10ptFontInfo;
const FONT_INFO& kLargeFont = liberationSansNarrow_16ptFontInfo;

// PROTOTYPE: cream background instead of black. clearScreen() is a fixed
// hardware clear-to-black command with no color parameter, so the fill
// below is a plain filled rect instead. Only the idle sprite's transparency
// has been re-baked to match this color (see sprites.h) -- the party sprite
// and the three pixel-art icons still bake transparency as black, so
// they'll show a black box against this cream fill until/unless the look
// is adopted for real and every asset gets redone.
constexpr uint8_t kCreamBackground = 0xDF;  // ~RGB(255,255,218)

// TinyScreen's Print helpers take a mutable char*, not const char* / String.
void printAt(TinyScreen& display, int x, int y, const String& text, const FONT_INFO& font) {
  char buf[64];
  text.toCharArray(buf, sizeof(buf));
  display.setFont(font);
  display.fontColor(kInkColor, kCreamBackground);
  display.setCursor(x, y);
  display.print(buf);
}

int printWidth(TinyScreen& display, const String& text, const FONT_INFO& font) {
  char buf[64];
  text.toCharArray(buf, sizeof(buf));
  display.setFont(font);
  return display.getPrintWidth(buf);
}

void drawIcon(TinyScreen& display, int x, int y, const uint8_t* icon, int w, int h) {
  display.setX(x, x + w - 1);
  display.setY(y, y + h - 1);
  display.startData();
  display.writeBuffer(const_cast<uint8_t*>(icon), w * h);
  display.endTransfer();
}

// All mood sprites are 64x64, one shared size.
constexpr int kMoodSpriteSize = 64;

// Maps a laptop-sent mood to its frame set. Only the moods with drawn art so
// far are listed (idle, happy, sad, working_neutral, working_sad); every
// other documented mood (hungry, sleeping, party) falls back to idle rather
// than failing to draw -- the protocol requires accepting every documented
// mood value even where firmware has no dedicated art yet.
const uint8_t* const* moodFrames(const String& mood, int* frameCount) {
  if (mood == "happy") {
    *frameCount = kHappySpriteFrameCount;
    return kHappySpriteFrames;
  }
  if (mood == "sad") {
    *frameCount = kSadSpriteFrameCount;
    return kSadSpriteFrames;
  }
  if (mood == "working_neutral") {
    *frameCount = kWorkingNeutralSpriteFrameCount;
    return kWorkingNeutralSpriteFrames;
  }
  if (mood == "working_sad") {
    *frameCount = kWorkingSadSpriteFrameCount;
    return &kWorkingSadSprite;
  }
  *frameCount = kIdleSpriteFrameCount;
  return kIdleSpriteFrames;
}

}  // namespace

Renderer::Renderer(TinyScreen& display) : display_(display) {
  dirty_ = true;  // draw the idle sprite immediately, before any laptop connects
}

void Renderer::setView(const View& view) {
  bool enteringBreakOffer =
      view.screen == "break_offer" && (!hasView_ || view_.screen != "break_offer");
  if (enteringBreakOffer) {
    focusCompleteButtonsRevealed_ = false;
    focusCompleteTimerStarted_ = false;
  }
  view_ = view;
  hasView_ = true;
  dirty_ = true;
  // Sound is only ever attached to the settings-screen view, but the
  // preference applies everywhere, so remember the last value we were told.
  if (view.hasSettings) soundEnabled_ = view.settingsSoundEnabled;
}

void Renderer::enqueueAnimation(const String& animationId, const String& name,
                                 const String& foodSprite) {
  for (const String& id : recentAnimationIds_) {
    if (id == animationId) return;
  }
  recentAnimationIds_.push_back(animationId);
  if (recentAnimationIds_.size() > kAnimationQueueLimit) {
    recentAnimationIds_.erase(recentAnimationIds_.begin());
  }
  if (animationQueue_.size() >= kAnimationQueueLimit) {
    animationQueue_.erase(animationQueue_.begin());
  }
  animationQueue_.push_back({animationId, name});
  if (name == "feed") {
    eatAnimationActive_ = true;
    eatAnimationStarted_ = false;
    eatAnimationFrame_ = -2;
    eatAnimationFoodSprite_ = foodSprite;
  } else if (name == "pet") {
    petAnimationActive_ = true;
    petAnimationStarted_ = false;
    petAnimationFrame_ = -1;
  }
  dirty_ = true;
}

void Renderer::setConnected(bool value) {
  if (value == connected) return;
  connected = value;
  if (!value) {
    animationQueue_.clear();
    hasView_ = false;
    eatAnimationActive_ = false;
    eatAnimationStarted_ = false;
    petAnimationActive_ = false;
    petAnimationStarted_ = false;
  }
  dirty_ = true;
}

namespace {
constexpr unsigned long kIdleFrameIntervalMs = 800;

// Feed animation timing: frame 0 alone, then frames 1/2 alternating at the
// same cadence as idle animation, for a combined 4 seconds.
constexpr unsigned long kEatFrame0DurationMs = 1000;
constexpr unsigned long kEatLoopFrameDurationMs = 800;
constexpr unsigned long kEatLoopDurationMs = 3000;

// Which kEatSpriteFrames index to show `elapsedMs` into the animation, or -1
// once it has finished.
int eatFrameForElapsed(unsigned long elapsedMs) {
  if (elapsedMs < kEatFrame0DurationMs) return 0;
  unsigned long loopElapsed = elapsedMs - kEatFrame0DurationMs;
  if (loopElapsed >= kEatLoopDurationMs) return -1;
  return 1 + (loopElapsed / kEatLoopFrameDurationMs) % 2;
}

// Petting animation timing: alternate the two frames briskly for a total of
// 1.6s (four half-second-ish switches), then done.
constexpr unsigned long kPetFrameDurationMs = 400;
constexpr unsigned long kPetAnimationDurationMs = 1600;

// Which kPetSpriteFrames index to show `elapsedMs` into the animation, or -1
// once it has finished.
int petFrameForElapsed(unsigned long elapsedMs) {
  if (elapsedMs >= kPetAnimationDurationMs) return -1;
  return (elapsedMs / kPetFrameDurationMs) % 2;
}

// How long the focus-complete (break_offer) screen shows only the reward
// before its button labels are drawn.
constexpr unsigned long kFocusCompleteButtonRevealMs = 4000;
}  // namespace

bool Renderer::showingMoodSprite() const {
  // Mood art: shown whenever nothing more specific is on screen -- no laptop
  // connected yet (idle fallback), the laptop has us on the home screen, or
  // we're mid-focus (a smaller working-cat sprite alongside the countdown;
  // see drawFocusSprite()). break_offer and break have their own dedicated
  // poses, not a per-mood sprite set, so they're left off here.
  return !connected || (hasView_ && (view_.screen == "home" || view_.screen == "focus"));
}

void Renderer::tick(unsigned long nowMs) {
  if (showingMoodSprite() && (nowMs - lastIdleSwitchMs_) >= kIdleFrameIntervalMs) {
    lastIdleSwitchMs_ = nowMs;
    idleFrame_++;
    dirty_ = true;
  }

  if (eatAnimationActive_) {
    if (!eatAnimationStarted_) {
      eatAnimationStarted_ = true;
      eatAnimationStartMs_ = nowMs;
    }
    int frame = eatFrameForElapsed(nowMs - eatAnimationStartMs_);
    if (frame < 0) {
      eatAnimationActive_ = false;
      eatAnimationStarted_ = false;
      dirty_ = true;  // one more redraw to fall back to normal mood/screen art
    } else if (frame != eatAnimationFrame_) {
      eatAnimationFrame_ = frame;
      dirty_ = true;
    }
  }

  if (petAnimationActive_) {
    if (!petAnimationStarted_) {
      petAnimationStarted_ = true;
      petAnimationStartMs_ = nowMs;
    }
    int frame = petFrameForElapsed(nowMs - petAnimationStartMs_);
    if (frame < 0) {
      petAnimationActive_ = false;
      petAnimationStarted_ = false;
      dirty_ = true;  // one more redraw to fall back to normal mood/screen art
    } else if (frame != petAnimationFrame_) {
      petAnimationFrame_ = frame;
      dirty_ = true;
    }
  }

  if (hasView_ && view_.screen == "break_offer" && !focusCompleteButtonsRevealed_) {
    if (!focusCompleteTimerStarted_) {
      focusCompleteTimerStarted_ = true;
      focusCompleteEnteredMs_ = nowMs;
    }
    if (nowMs - focusCompleteEnteredMs_ >= kFocusCompleteButtonRevealMs) {
      focusCompleteButtonsRevealed_ = true;
      dirty_ = true;
    }
  }

  if (!dirty_) return;
  dirty_ = false;
  // Full-screen redraw; no partial dirty-region tracking, matching the
  // original firmware's approach until real sprite layouts are designed.
  display_.drawRect(0, 0, hw::SCREEN_WIDTH, hw::SCREEN_HEIGHT, TSRectangleFilled,
                     kCreamBackground);
  // Feed animation takes over the whole screen regardless of what's
  // otherwise showing, then falls through to normal drawing once done.
  // break_offer is the moment a focus session just completed -- show the
  // celebration pose; break gets its own small face; every other screen
  // keeps the usual mood-or-nothing background.
  if (eatAnimationActive_) {
    drawEatAnimation();
  } else if (petAnimationActive_) {
    drawPetAnimation();
  } else if (hasView_ && view_.screen == "break_offer") {
    drawFocusCompleteScreen();
  } else if (hasView_ && view_.screen == "break") {
    drawBreakScreen();
  } else if (hasView_ && view_.screen == "focus") {
    drawFocusSprite();
  } else if (showingMoodSprite()) {
    drawMoodSprite();
  }
  drawText();
  if (hasView_ && view_.hasProgression) drawProgressionHud();
}

void Renderer::drawMoodSprite() {
  int frameCount = 1;
  const uint8_t* const* frames;
  if (!connected) {
    // No laptop driving the screen yet (freshly booted or between
    // connections): show the pet asleep rather than the awake Idle pose,
    // which is reserved for an actual laptop-reported "idle" mood.
    frameCount = kSleepSpriteFrameCount;
    frames = kSleepSpriteFrames;
  } else {
    frames = moodFrames(view_.mood, &frameCount);
  }
  const uint8_t* frame = frames[idleFrame_ % frameCount];

  int x = (hw::SCREEN_WIDTH - kMoodSpriteSize) / 2;
  // Nudged down 3px from dead-center on Home to sit better under the clock.
  int y = (hw::SCREEN_HEIGHT - kMoodSpriteSize) / 2 + 3;
  drawIcon(display_, x, y, frame, kMoodSpriteSize, kMoodSpriteSize);
}

void Renderer::drawEatAnimation() {
  int frame = eatAnimationFrame_ < 0 ? 0 : eatAnimationFrame_;
  int x = (hw::SCREEN_WIDTH - kMoodSpriteSize) / 2;
  int y = (hw::SCREEN_HEIGHT - kMoodSpriteSize) / 2 + 3;
  drawIcon(display_, x, y, kEatSpriteFrames[frame], kMoodSpriteSize, kMoodSpriteSize);

  // The fed item appears next to the pet only on the first frame (about to
  // eat), then disappears once the eating motion (frames 1/2) starts.
  if (frame != 0) return;
  const uint8_t* foodIcon = nullptr;
  int foodWidth = 0;
  int foodHeight = 0;
  if (eatAnimationFoodSprite_ == "jollof_rice") {
    foodIcon = kIconJollof;
    foodWidth = kIconJollofWidth;
    foodHeight = kIconJollofHeight;
  } else if (eatAnimationFoodSprite_ == "espresso") {
    foodIcon = kIconEspresso;
    foodWidth = kIconEspressoWidth;
    foodHeight = kIconEspressoHeight;
  }
  if (foodIcon == nullptr) return;
  int foodX = hw::SCREEN_WIDTH - foodWidth - kMargin;
  int foodY = (hw::SCREEN_HEIGHT - foodHeight) / 2;
  drawIcon(display_, foodX, foodY, foodIcon, foodWidth, foodHeight);
}

void Renderer::drawPetAnimation() {
  int frame = petAnimationFrame_ < 0 ? 0 : petAnimationFrame_;
  int x = (hw::SCREEN_WIDTH - kMoodSpriteSize) / 2;
  int y = (hw::SCREEN_HEIGHT - kMoodSpriteSize) / 2 + 3;
  drawIcon(display_, x, y, kPetSpriteFrames[frame], kMoodSpriteSize, kMoodSpriteSize);
}

void Renderer::drawFocusSprite() {
  int frameCount = 1;
  const uint8_t* const* frames =
      moodFrames(hasView_ ? view_.mood : String("working_neutral"), &frameCount);
  const uint8_t* frame = frames[idleFrame_ % frameCount];

  // Full native resolution, flush against the left edge; the countdown
  // (drawText()) takes the remaining right-hand strip.
  int x = 0;
  int y = (hw::SCREEN_HEIGHT - kMoodSpriteSize) / 2;
  drawIcon(display_, x, y, frame, kMoodSpriteSize, kMoodSpriteSize);
}

void Renderer::drawFocusCompleteScreen() {
  // Party pose anchored to the right edge; "FOCUS COMPLETE!" on two lines to
  // its left, plus the XP/yarn just earned when the laptop supplies them.
  int spriteX = hw::SCREEN_WIDTH - kPartySpriteWidth;
  drawIcon(display_, spriteX, 0, kPartySprite, kPartySpriteWidth, kPartySpriteHeight);

  int fontHeight = display_.getFontHeight(kSmallFont);
  int lineGap = 2;
  int lineCount = view_.hasEarnedRewards ? 4 : 2;
  int y = (hw::SCREEN_HEIGHT - (fontHeight * lineCount + lineGap * (lineCount - 1))) / 2;

  printAt(display_, kMargin, y, String("FOCUS"), kSmallFont);
  y += fontHeight + lineGap;
  printAt(display_, kMargin, y, String("COMPLETE!"), kSmallFont);

  if (view_.hasEarnedRewards) {
    y += fontHeight + lineGap;
    printAt(display_, kMargin, y, "+" + String(view_.earnedXp) + " XP", kSmallFont);
    y += fontHeight + lineGap;
    String yarnText = "+" + String(view_.earnedYarn) + " ";
    printAt(display_, kMargin, y, yarnText, kSmallFont);
    int yarnTextWidth = printWidth(display_, yarnText, kSmallFont);
    int yarnIconY = y + (fontHeight - kIconYarnHeight) / 2;
    drawIcon(display_, kMargin + yarnTextWidth, yarnIconY, kIconYarn, kIconYarnWidth,
             kIconYarnHeight);
  }
}

void Renderer::drawBreakScreen() {
  // Full native resolution, flush against the left edge, matching Focus's
  // layout -- the countdown (drawText()) takes the right-hand strip. Stays
  // exactly like this even once the break's timer runs out on its own;
  // only the right-hand strip changes (see drawText()'s breakIsUp handling).
  int x = 0;
  int y = (hw::SCREEN_HEIGHT - kBreakSpriteHeight) / 2;
  drawIcon(display_, x, y, kBreakSprite, kBreakSpriteWidth, kBreakSpriteHeight);
}

// Button 4 always renders something in the bottom-right corner (an icon or
// a short label), so the progression HUD reserves this much room above it
// rather than risking an overlap -- see the button-drawing loop below.
constexpr int kProgressionBottomClearance = 14;

void Renderer::drawProgressionHud() {
  const View& view = view_;

  int yarnY = hw::SCREEN_HEIGHT - kIconYarnHeight - kMargin - kProgressionBottomClearance;
  int yarnIconX = hw::SCREEN_WIDTH - kIconYarnWidth - kMargin;
  drawIcon(display_, yarnIconX, yarnY, kIconYarn, kIconYarnWidth, kIconYarnHeight);

  String yarnText(view.yarnBalance);
  int yarnTextWidth = printWidth(display_, yarnText, kSmallFont);
  printAt(display_, yarnIconX - yarnTextWidth - 2, yarnY - 1, yarnText, kSmallFont);

  String levelText = "Lv" + String(view.level);
  int levelTextWidth = printWidth(display_, levelText, kSmallFont);
  int levelY = yarnY - display_.getFontHeight(kSmallFont) - 2;
  printAt(display_, hw::SCREEN_WIDTH - levelTextWidth - kMargin, levelY, levelText, kSmallFont);
}

void Renderer::drawText() {
  if (!connected || !hasView_) return;
  const View& view = view_;

  if (view.hasClockText) {
    // Top-center, not top-right: the top-right corner is button 2's label
    // (see the per-corner layout below -- TinyScreen+'s buttons are
    // physically at the screen's four corners, unlike the two-button
    // bottom-row layout this was originally written for).
    int width = printWidth(display_, view.clockText, kSmallFont);
    int x = (hw::SCREEN_WIDTH - width) / 2;
    printAt(display_, x, kMargin, view.clockText, kSmallFont);
  }

  // On break, timerSeconds == 0 means the break ran out on its own (see the
  // laptop's presenter._timer_seconds) rather than a live countdown reaching
  // zero mid-frame -- keep the resting pose on screen (drawBreakScreen()) and
  // just swap the countdown for "Break's"/"Up" on two lines, right-aligned in
  // the same slot.
  bool breakIsUp = view.screen == "break" && view.timerSeconds == 0;
  if (breakIsUp) {
    int fontHeight = display_.getFontHeight(kSmallFont);
    int lineGap = 2;
    int y = (hw::SCREEN_HEIGHT - (fontHeight * 2 + lineGap)) / 2;
    String line1("Break's");
    int width1 = printWidth(display_, line1, kSmallFont);
    printAt(display_, hw::SCREEN_WIDTH - width1 - kMargin, y, line1, kSmallFont);
    y += fontHeight + lineGap;
    String line2("Up");
    int width2 = printWidth(display_, line2, kSmallFont);
    printAt(display_, hw::SCREEN_WIDTH - width2 - kMargin, y, line2, kSmallFont);
  } else if (view.hasTimerSeconds) {
    char timerBuf[8];
    snprintf(timerBuf, sizeof(timerBuf), "%d:%02d", view.timerSeconds / 60,
             view.timerSeconds % 60);
    String timerText(timerBuf);
    int width = printWidth(display_, timerText, kLargeFont);
    int fontHeight = display_.getFontHeight(kLargeFont);
    // Right side of the screen -- the working-cat sprite (drawFocusSprite())
    // takes the left side while focus is running.
    int x = hw::SCREEN_WIDTH - width - kMargin;
    int y = (hw::SCREEN_HEIGHT - fontHeight) / 2;
    printAt(display_, x, y, timerText, kLargeFont);
  }

  // Setup screen: selected focus duration large and centered, calculated
  // break duration smaller underneath. 0 is the reserved debug duration --
  // a fixed 10-second session for quick local testing -- shown as "Debug
  // 10s" instead of the usual "Nm"/"Break Nm" pair.
  if (view.hasFocusMinutes) {
    bool isDebug = view.focusMinutes == 0;
    String focusText = isDebug ? String("Debug") : String(view.focusMinutes) + "m";
    int width = printWidth(display_, focusText, kLargeFont);
    int fontHeightLarge = display_.getFontHeight(kLargeFont);
    int x = (hw::SCREEN_WIDTH - width) / 2;
    int y = (hw::SCREEN_HEIGHT - fontHeightLarge) / 2 - 6;
    printAt(display_, x, y, focusText, kLargeFont);

    if (view.hasBreakMinutes) {
      String breakText = isDebug ? String("10s") : "Break " + String(view.breakMinutes) + "m";
      int breakWidth = printWidth(display_, breakText, kSmallFont);
      printAt(display_, (hw::SCREEN_WIDTH - breakWidth) / 2, y + fontHeightLarge + 2, breakText,
              kSmallFont);
    }
  }

  // Settings: three rows (Keyboard, Camera, Sound) with an on/off/unavailable
  // status and a ">" marker on the currently selected row. Sound has no
  // "unavailable" state.
  if (view.hasSettings) {
    int fontHeightSmall = display_.getFontHeight(kSmallFont);
    int rowGap = fontHeightSmall + 4;
    int rowY = (hw::SCREEN_HEIGHT - rowGap * 2 - fontHeightSmall) / 2;

    auto statusText = [](bool available, bool enabled) {
      if (!available) return String("Unavailable");
      return enabled ? String("On") : String("Off");
    };

    String keyboardLine =
        (view.settingsSelectedRow == 0 ? String("> Keyboard: ") : String("  Keyboard: ")) +
        statusText(view.settingsKeyboardAvailable, view.settingsKeyboardEnabled);
    String cameraLine =
        (view.settingsSelectedRow == 1 ? String("> Camera: ") : String("  Camera: ")) +
        statusText(view.settingsCameraAvailable, view.settingsCameraEnabled);
    String soundLine =
        (view.settingsSelectedRow == 2 ? String("> Sound: ") : String("  Sound: ")) +
        statusText(true, view.settingsSoundEnabled);

    printAt(display_, kMargin, rowY, keyboardLine, kSmallFont);
    printAt(display_, kMargin, rowY + rowGap, cameraLine, kSmallFont);
    printAt(display_, kMargin, rowY + rowGap * 2, soundLine, kSmallFont);
  }

  // One label per physical button, in its own corner -- TinyScreen+'s four
  // buttons sit at the screen's four corners (id 1=top-left, 2=top-right,
  // 3=bottom-left, 4=bottom-right; see hardware_config.h's BUTTONS table).
  // Several labels get small pixel-art icons instead of text; every other
  // label (Pause/Resume/End/Back/etc.) still draws as plain text. Button 4
  // always draws something here -- the progression HUD (drawn separately)
  // reserves clearance above this corner rather than the button skipping it.
  // On break_offer, labels are held back for the first few seconds (see
  // focusCompleteButtonsRevealed_) so only the reward is visible at first;
  // the buttons keep working even while their labels aren't drawn, since
  // button handling never depends on what's currently on screen.
  bool suppressButtonLabels =
      hasView_ && view.screen == "break_offer" && !focusCompleteButtonsRevealed_;
  int fontHeight = display_.getFontHeight(kSmallFont);
  if (suppressButtonLabels) return;
  for (const ButtonAdvert& entry : view.buttons) {
    bool isFocusIcon = entry.label == "Focus";
    bool isFeedIcon = entry.label == "Feed";
    bool isCaretUp = entry.label == "Up";
    bool isCaretDown = entry.label == "Down";
    bool isSettingsIcon = entry.label == "Settings";
    // Feed-menu labels carry the price ("Jollof 3Y", "Espresso 2Y"), so match
    // the item name as a prefix rather than the whole label.
    bool isJollofIcon = entry.label.startsWith("Jollof");
    bool isEspressoIcon = entry.label.startsWith("Espresso");

    int width, height;
    if (isFocusIcon) {
      width = kIconFocusWidth;
      height = kIconFocusHeight;
    } else if (isFeedIcon) {
      width = kIconFeedWidth;
      height = kIconFeedHeight;
    } else if (isCaretUp) {
      width = kIconCaretUpWidth;
      height = kIconCaretUpHeight;
    } else if (isCaretDown) {
      width = kIconCaretDownWidth;
      height = kIconCaretDownHeight;
    } else if (isSettingsIcon) {
      width = kIconSettingsWidth;
      height = kIconSettingsHeight;
    } else if (isJollofIcon) {
      width = kIconJollofWidth;
      height = kIconJollofHeight;
    } else if (isEspressoIcon) {
      width = kIconEspressoWidth;
      height = kIconEspressoHeight;
    } else {
      width = printWidth(display_, entry.label, kSmallFont);
      height = fontHeight;
    }

    int x = (entry.id == 1 || entry.id == 3) ? kMargin : hw::SCREEN_WIDTH - width - kMargin;
    int y = (entry.id == 1 || entry.id == 2) ? kMargin : hw::SCREEN_HEIGHT - height - kMargin;

    if (isFocusIcon) {
      drawIcon(display_, x, y, kIconFocus, kIconFocusWidth, kIconFocusHeight);
    } else if (isFeedIcon) {
      drawIcon(display_, x, y, kIconFeed, kIconFeedWidth, kIconFeedHeight);
    } else if (isCaretUp) {
      drawIcon(display_, x, y, kIconCaretUp, kIconCaretUpWidth, kIconCaretUpHeight);
    } else if (isCaretDown) {
      drawIcon(display_, x, y, kIconCaretDown, kIconCaretDownWidth, kIconCaretDownHeight);
    } else if (isSettingsIcon) {
      drawIcon(display_, x, y, kIconSettings, kIconSettingsWidth, kIconSettingsHeight);
    } else if (isJollofIcon) {
      drawIcon(display_, x, y, kIconJollof, kIconJollofWidth, kIconJollofHeight);
    } else if (isEspressoIcon) {
      drawIcon(display_, x, y, kIconEspresso, kIconEspressoWidth, kIconEspressoHeight);
    } else {
      printAt(display_, x, y, entry.label, kSmallFont);
    }
  }
}
