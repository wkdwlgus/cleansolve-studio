import { useEffect, useMemo, useState } from 'react';
import { loadEditorJob, loadSampleEditorJob, type EditorJob } from '../api/client';
import { EditorCanvas } from '../editor/EditorCanvas';
import { ReviewPanel } from '../editor/ReviewPanel';
import { getStylePresetLabel } from '../editor/editorCopy';
import { filterHumanReviewItems } from '../editor/reviewHelpers';

const ACTIVE_STYLE_PRESET = 'default_pretty_handwriting';

const statusLabels: Record<string, string> = {
  CREATED: '작업 생성됨',
  APPROVED: '자동 검토 완료',
  NEEDS_REVIEW: '사람 검토 필요'
};

export function App() {
  const [job, setJob] = useState<EditorJob>({
    jobId: '',
    status: 'LOADING',
    revisionAttempts: 0,
    reviewItems: []
  });
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'fallback'>('loading');

  useEffect(() => {
    let active = true;

    loadEditorJob()
      .then((loadedJob) => {
        if (!active) {
          return;
        }

        setJob(loadedJob);
        setLoadState('ready');
      })
      .catch(() => {
        if (!active) {
          return;
        }

        setJob(loadSampleEditorJob());
        setLoadState('fallback');
      });

    return () => {
      active = false;
    };
  }, []);

  const visibleReviewItems = useMemo(() => filterHumanReviewItems(job.reviewItems), [job.reviewItems]);
  const markerReviewItem = visibleReviewItems.find((item) => item.type === 'freehand_dimension_marker');
  const statusLabel =
    loadState === 'loading'
      ? '작업 불러오는 중'
      : loadState === 'fallback'
        ? '샘플 작업 표시 중'
        : (statusLabels[job.status] ?? '작업 상태 확인 중');

  return (
    <main className="app-shell">
      <section className="workspace" aria-label="편집 작업 영역">
        <header className="topbar">
          <div>
            <h1>CleanSolve Studio</h1>
            <p>
              활성 스타일: <strong>{getStylePresetLabel(ACTIVE_STYLE_PRESET)}</strong>
            </p>
          </div>
          <div className="job-summary" aria-label="작업 상태">
            <span>검토 항목 {visibleReviewItems.length}</span>
            <span>{statusLabel}</span>
          </div>
        </header>
        <EditorCanvas markerReviewItem={markerReviewItem} />
      </section>
      <ReviewPanel items={job.reviewItems} />
    </main>
  );
}
