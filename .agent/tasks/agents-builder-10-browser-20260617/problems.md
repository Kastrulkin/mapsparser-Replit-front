# Problems Found And Fixed

- Scheduled Telegram reminders were already mostly correct; kept them away from outreach/lead questions.
- Google Sheets to Finance asked generic extraction questions even when the prompt said new sales rows and Finance. Added extraction hints for sales/new rows.
- Negative review alerts asked for schedule despite `if a review appears`. Added event-trigger markers.
- Weekly owner report asked where a human should check before action despite `send to Telegram`. Treated Telegram send intent as enough control/delivery context.
- Telegram reactions/content-plan scenario was repeatedly misread by the AI compiler as post publishing or Telegram delivery. Added a dedicated Telegram content analytics path that creates a normal custom-agent draft instead of a forbidden provider workflow.
- First-screen wording leaked internal terms such as `draft`, `workflow`, `execution route`, and `provider path`. Replaced with user-facing Russian copy.
- Partnership data showed `лиды`; changed the user-facing source label to neutral `кандидаты`.
