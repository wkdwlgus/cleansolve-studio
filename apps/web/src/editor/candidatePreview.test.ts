import { describe, expect, it } from 'vitest';
import type { CandidateSpecPreview } from '../api/client';
import { buildPreviewModel, getElementText } from './candidatePreview';

const baseSpec: CandidateSpecPreview = {
  job_id: 'job_preview',
  version: 1,
  page: { width: 1080, height: 1920 },
  elements: []
};

describe('candidate preview helpers', () => {
  it('computes a stable scale and coordinate transform', () => {
    const preview = buildPreviewModel({
      ...baseSpec,
      elements: [
        {
          id: 'el_line',
          type: 'highlight_line',
          geometry: { start: [0, 0], end: [1080, 1920] }
        }
      ]
    });

    expect(preview.stage.width).toBe(760);
    expect(preview.stage.height).toBe(540);
    expect(preview.scale).toBeCloseTo(0.239583, 5);
    expect(preview.primitives[0]).toMatchObject({
      kind: 'line',
      points: [20, 40, 278.75, 500]
    });
  });

  it('uses text priority and skips empty high priority text', () => {
    expect(
      getElementText({
        id: 'el_text',
        type: 'formula_line',
        display_text: 'display',
        text: 'text',
        geometry: { text: 'geometry' },
        label: 'label'
      })
    ).toBe('display');
    expect(
      getElementText({
        id: 'el_empty',
        type: 'formula_line',
        display_text: '',
        text: 'fallback'
      })
    ).toBeNull();
  });

  it('skips malformed primitives without throwing', () => {
    const preview = buildPreviewModel({
      ...baseSpec,
      elements: [
        { id: 'bad_line', type: 'highlight_line', geometry: { start: [true, 0], end: [10, 10] } },
        { id: 'bad_text', type: 'formula_line', geometry: { anchor: ['x', 0] }, text: 'bad' }
      ]
    });

    expect(preview.primitives).toEqual([]);
  });

  it('returns an empty preview for malformed top-level candidate specs', () => {
    expect(
      buildPreviewModel({
        job_id: 'job_bad',
        version: 1,
        page: { width: 0, height: 0 },
        elements: [
          {
            id: 'should_not_render',
            type: 'highlight_line',
            geometry: { start: [0, 0], end: [10, 10] }
          }
        ]
      }).primitives
    ).toEqual([]);

    expect(
      buildPreviewModel({
        job_id: 'job_bad',
        version: 1,
        page: { width: 1080, height: 1920 },
        elements: null
      } as unknown as CandidateSpecPreview).primitives
    ).toEqual([]);
  });

  it('renders freehand visible strokes and label primitives', () => {
    const preview = buildPreviewModel({
      ...baseSpec,
      elements: [
        {
          id: 'el_marker',
          type: 'freehand_dimension_marker',
          color: 'red',
          geometry: {
            visible_strokes: [{ stroke_id: 's1', points: [[100, 200], [200, 300]] }],
            label: '1',
            label_anchor: [150, 250]
          }
        }
      ]
    });

    expect(preview.primitives).toHaveLength(2);
    expect(preview.primitives[0]).toMatchObject({ kind: 'line', id: 'el_marker:s1', color: 'red' });
    expect(preview.primitives[1]).toMatchObject({ kind: 'text', id: 'el_marker:label', text: '1', color: 'red' });
  });
});
