# Voice input: recovery and review — 2026-10-21

Status: available in the shared Telegram/MAX/web voice component. Live MAX acceptance still requires platform access.

The recording input now explains denied, missing and occupied microphones in Russian and offers an audio file or text. A failed/pending transcription retains its existing job; checking it again uses the existing authenticated retry endpoint instead of uploading the audio again. An upload whose response is lost retains the request identity. Cancellation clears the local pending state. Scope changes clear private recording state.

Preserved deployed behavior: daily-brief transcriptions use their own recovery context and require explicit review even when the recognizer classifies the text as finance or a journal observation. General chat retains its existing direct preparation flow; this never authorizes external delivery.

Validation: the two denial cases and transcription-retry case failed before their fixes. The deployed frontend baseline passes 49 adjacent tests and builds successfully; the common-branch baseline passes 50 adjacent tests. These are overlapping component suites, not counts of independent user acceptance cases. The denied-microphone recovery was repeated in the live Telegram miniapp after deployment.

Limits: browser file-picker automation did not provide a chooser in the embedded client. A live synthetic-audio test reached SpeechKit, but its asynchronous operation remained pending past the worker's three-minute wait. This patch does not claim to resolve provider latency, accept physical-device recording, or complete the wider client acceptance matrix. No external business messages were sent.
