import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const source = readFileSync('src/pages/dashboard/ContentPage.tsx', 'utf8');

describe('content calendar truthful readiness', () => {
  it('uses the saved post selection for the card channel count', () => {
    expect(source).toContain('resolveItemSelectedChannels(item, posts, currentPlan).length');
    expect(source).not.toContain('posts.length || getSelectedCount(createDraft.channels)');
  });
  it('does not display an unanalyzed photo as zero quality', () => {
    expect(source).toContain("selectedPhoto.analysis_status !== 'analyzed' ? 'Качество ещё не оценено'");
  });
  it('shows a review state instead of ready when review is pending', () => {
    expect(source).toContain('needsReviewCount > 0 ? calendarCopy.needsReview : calendarCopy.contentReady');
  });
});
