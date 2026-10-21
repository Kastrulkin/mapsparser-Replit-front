# Voice recording context reset

An isolated browser pass reproduced a recording surviving a business switch after Cancel had replaced its abort controller. An ordinary switch could also leave the recording indicator active. A delayed stop callback from the cancelled recorder could stop a newer microphone stream.

The shared voice input now aborts the current recording lifetime on context cleanup, resets recording duration/state and asset reference, and ignores callbacks from an aborted recording. Starting a new recording also clears the previous transcript shown beneath it. The per-business/context pending-job key remains unchanged, so an existing transcription can still be restored for its original business.

Validation: two scope regressions failed before the scope reset; the delayed-cancel regression then separately failed before its callback guard. Final focused voice/briefing checks passed on both production-based and common sources (22 cases each); production-based frontend build passed. Browser checks used explicitly synthetic microphone and job responses with no provider upload: cancel without upload, recover an upload error, edit transcript before apply, retry the same failed job, and clear recording on scope switch after Cancel. These do not certify physical microphone, acoustic recognition, Telegram voice-message upload, or a live MAX client.

Deployment uses the production-based frontend and exact source/index guards. No client content, account access, schedules or outbound deliveries are changed.
