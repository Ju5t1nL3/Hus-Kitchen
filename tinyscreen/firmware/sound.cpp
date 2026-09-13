#include "sound.h"

namespace {
constexpr int kDacCenter = 512;  // mid-rail of the 10-bit DAC
constexpr int kDacSwing = 150;
}  // namespace

void SoundPlayer::begin() {
  analogWriteResolution(10);
  analogWrite(A0, kDacCenter);
}

void SoundPlayer::playBackground(const ToneStep* steps, int count) {
  bgSteps_ = steps;
  bgCount_ = count;
  bgIndex_ = 0;
  if (!cueActive() && bgSteps_ != nullptr && bgCount_ > 0) {
    startStep(bgSteps_[0].freqHz, bgSteps_[0].durationMs, micros());
  }
}

void SoundPlayer::playCue(const ToneStep* steps, int count) {
  cueSteps_ = steps;
  cueCount_ = count;
  cueIndex_ = 0;
  if (cueCount_ > 0) {
    startStep(cueSteps_[0].freqHz, cueSteps_[0].durationMs, micros());
  }
}

void SoundPlayer::startStep(unsigned int freqHz, unsigned int durationMs, unsigned long nowMicros) {
  toggleIntervalMicros_ = freqHz > 0 ? (1000000UL / (2UL * freqHz)) : 0;
  stepEndMicros_ = nowMicros + (unsigned long)durationMs * 1000UL;
  lastToggleMicros_ = nowMicros;
  high_ = false;
}

void SoundPlayer::silence() {
  analogWrite(A0, kDacCenter);
}

void SoundPlayer::tick(unsigned long nowMicros) {
  if (!cueActive() && bgSteps_ == nullptr) return;

  if ((long)(nowMicros - stepEndMicros_) >= 0) {
    if (cueActive()) {
      cueIndex_++;
      if (cueIndex_ < cueCount_) {
        startStep(cueSteps_[cueIndex_].freqHz, cueSteps_[cueIndex_].durationMs, nowMicros);
      } else {
        // Cue finished -- fall back to the background loop, resuming at its
        // current position rather than restarting from the top.
        cueIndex_ = -1;
        if (bgSteps_ != nullptr && bgCount_ > 0) {
          startStep(bgSteps_[bgIndex_].freqHz, bgSteps_[bgIndex_].durationMs, nowMicros);
        } else {
          silence();
        }
      }
    } else {
      bgIndex_ = (bgIndex_ + 1) % bgCount_;
      startStep(bgSteps_[bgIndex_].freqHz, bgSteps_[bgIndex_].durationMs, nowMicros);
    }
    return;
  }

  if (toggleIntervalMicros_ == 0) return;
  if ((unsigned long)(nowMicros - lastToggleMicros_) >= toggleIntervalMicros_) {
    lastToggleMicros_ = nowMicros;
    high_ = !high_;
    analogWrite(A0, high_ ? kDacCenter + kDacSwing : kDacCenter - kDacSwing);
  }
}
