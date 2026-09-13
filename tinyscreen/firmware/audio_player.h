// Loops the truncated/downsampled clip in audio_clip.h out the DAC (A0).
//
// This is polling-based (checked from loop(), not a hardware timer ISR), so
// its 8kHz sample clock is only as steady as loop() lets it be: a slow
// display SPI write can make it briefly late. Good enough for background
// ambience; not sample-accurate. firmware.ino only ticks this when
// SoundPlayer has no cue playing, since both ultimately drive the same
// single DAC pin.
#pragma once

#include <Arduino.h>

class AudioPlayer {
 public:
  void begin();

  // (Re)starts playback from the beginning.
  void play();

  // Stops playback; tick() becomes a no-op until play() is called again.
  void stop();

  // Call every loop() iteration; writes the next due sample and loops back
  // to the start when the clip ends. Does nothing until play() has been
  // called (so simply never calling play() fully disables this).
  void tick(unsigned long nowMicros);

 private:
  unsigned long periodMicros_ = 0;
  unsigned long nextSampleMicros_ = 0;
  unsigned long index_ = 0;
  bool playing_ = false;
};
