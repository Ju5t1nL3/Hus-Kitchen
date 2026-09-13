// Simple non-blocking tone player for the MicroSD/Audio TinyShield's onboard
// DAC (A0 -> its filter/amp/speaker).
//
// This plays short procedural beep sequences (not recorded WAV playback --
// there are no audio assets in this repo yet to play from the shield's SD
// card). It exists to give the desk pet audible feedback for connect/press/
// feed/celebrate events, wired the same way the render/animate cues are:
// firmware only plays what it's told, it doesn't decide when a "feed" cue
// means anything.
//
// There's only one DAC voice, so a looping "background" sequence (BGM) and a
// short one-shot "cue" (button press, feed, ready) can't truly play at once.
// A cue takes priority: it plays through, then playback falls back to the
// background sequence, resuming wherever its loop had gotten to.
#pragma once

#include <Arduino.h>

struct ToneStep {
  unsigned int freqHz;
  unsigned int durationMs;
};

class SoundPlayer {
 public:
  void begin();

  // Starts a looping sequence that plays continuously in between cues.
  // `steps` must outlive playback (pass a static/constexpr array).
  void playBackground(const ToneStep* steps, int count);

  // Starts a one-shot sequence that takes priority over the background
  // loop; the background loop resumes automatically once it finishes.
  void playCue(const ToneStep* steps, int count);

  // Call every loop() iteration; advances whichever sequence is currently
  // sounding and toggles the DAC output to approximate a square-wave tone
  // without blocking.
  void tick(unsigned long nowMicros);

  // True while a one-shot cue is playing (as opposed to the background
  // loop, or nothing). Lets other DAC users (AudioPlayer) yield the pin.
  bool isCuePlaying() const { return cueActive(); }

 private:
  const ToneStep* bgSteps_ = nullptr;
  int bgCount_ = 0;
  int bgIndex_ = 0;

  const ToneStep* cueSteps_ = nullptr;
  int cueCount_ = 0;
  int cueIndex_ = -1;  // -1 == no cue playing

  unsigned long stepEndMicros_ = 0;
  unsigned long toggleIntervalMicros_ = 0;
  unsigned long lastToggleMicros_ = 0;
  bool high_ = false;

  bool cueActive() const { return cueIndex_ >= 0; }
  void startStep(unsigned int freqHz, unsigned int durationMs, unsigned long nowMicros);
  void silence();
};
