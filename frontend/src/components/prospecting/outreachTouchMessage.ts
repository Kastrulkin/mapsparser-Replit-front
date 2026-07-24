export type OutreachTouchMessage = {
  sequence_index: number;
  channel: string;
  subject?: string | null;
  text?: string | null;
  generated_text?: string | null;
  approved_text?: string | null;
};

export type OutreachTouchMessageDraft = {
  subject: string;
  text: string;
  originalSubject: string;
  originalText: string;
  humanEdited: boolean;
};

export const outreachTouchMessageText = (touch: OutreachTouchMessage) => String(
  touch.text || touch.approved_text || touch.generated_text || '',
).trim();

export const outreachTouchMessageDraft = (touch: OutreachTouchMessage): OutreachTouchMessageDraft => {
  const subject = String(touch.subject || '').trim();
  const text = outreachTouchMessageText(touch);
  return {
    subject,
    text,
    originalSubject: subject,
    originalText: text,
    humanEdited: false,
  };
};
