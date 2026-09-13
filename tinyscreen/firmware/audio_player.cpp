#include "audio_player.h"

#include "audio_clip.h"

void AudioPlayer::begin() {
  periodMicros_ = 1000000UL / kAudioClipSampleRate;
}

void AudioPlayer::play() {
  index_ = 0;
  nextSampleMicros_ = micros();
  playing_ = true;
}

void AudioPlayer::stop() {
  playing_ = false;
}

void AudioPlayer::tick(unsigned long nowMicros) {
  if (!playing_) return;
  if ((long)(nowMicros - nextSampleMicros_) < 0) return;

  uint8_t sample = kAudioClip[index_];
  // Scale 8-bit (0-255) up to the 10-bit DAC resolution SoundPlayer configured.
  analogWrite(A0, (uint16_t)sample << 2);

  index_++;
  if (index_ >= kAudioClipLength) index_ = 0;

  unsigned long behind = nowMicros - nextSampleMicros_;
  if (behind > periodMicros_ * 4) {
    // Fell far behind (e.g. a cue or slow display write ran long) -- resync
    // to now instead of fast-forwarding through the backlog, which would
    // otherwise play back at an audibly sped-up rate.
    nextSampleMicros_ = nowMicros + periodMicros_;
  } else {
    nextSampleMicros_ += periodMicros_;
  }
}
