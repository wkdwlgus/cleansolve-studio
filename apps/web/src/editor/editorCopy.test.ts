import { describe, expect, it } from 'vitest';
import { formatAnchorPatchSummary, getStylePresetLabel } from './editorCopy';

describe('editor user-facing copy', () => {
  it('maps style preset IDs to Korean labels without exposing raw IDs', () => {
    const label = getStylePresetLabel('default_pretty_handwriting');

    expect(label).toBe('기본 손글씨 스타일');
    expect(label).not.toContain('default_pretty_handwriting');
  });

  it('summarizes anchor patches in Korean without internal patch keys', () => {
    const summary = formatAnchorPatchSummary({
      start: { x: 178.4, y: 386.2 },
      end: { x: 542.1, y: 385.8 }
    });

    expect(summary).toBe('끝점 조정: 시작점 (178, 386), 끝점 (542, 386)');
    expect(summary).not.toContain('element_id');
    expect(summary).not.toContain('target_anchor_start');
    expect(summary).not.toContain('target_anchor_end');
  });
});
