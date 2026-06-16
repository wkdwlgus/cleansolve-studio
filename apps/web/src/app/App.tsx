import { FormEvent, useMemo, useState } from 'react';
import { runUploadToReviewWorkflow } from '../api/client';
import { EditorCanvas } from '../editor/EditorCanvas';
import { ReviewPanel } from '../editor/ReviewPanel';
import { getStylePresetLabel } from '../editor/editorCopy';
import { filterHumanReviewItems } from '../editor/reviewHelpers';
import { initialWorkflowState, nextWorkflowState, type WorkflowPhase } from './workflowState';

const ACTIVE_STYLE_PRESET = 'default_pretty_handwriting';

const statusLabels: Record<string, string> = {
  CREATED: '작업 생성됨',
  APPROVED: '자동 검토 완료',
  NEEDS_REVIEW: '사람 검토 필요',
  REVISION_REQUIRED: '추가 검토 필요',
  FAILED: '작업 실패'
};

const phaseLabels: Record<WorkflowPhase, string> = {
  idle: '이미지를 업로드해 작업을 시작하세요',
  creating: '작업을 생성하는 중',
  uploading: '이미지를 업로드하는 중',
  running: '분석 workflow를 실행하는 중',
  ready: '작업 상태 확인 중',
  error: '작업을 완료하지 못했습니다'
};

export function App() {
  const [workflow, setWorkflow] = useState(initialWorkflowState);
  const [problemFile, setProblemFile] = useState<File | null>(null);
  const [teacherSolutionFile, setTeacherSolutionFile] = useState<File | null>(null);
  const job = workflow.job;
  const reviewItems = job?.reviewItems ?? [];
  const visibleReviewItems = useMemo(() => filterHumanReviewItems(reviewItems), [reviewItems]);
  const markerReviewItem = visibleReviewItems.find((item) => item.type === 'freehand_dimension_marker');
  const statusLabel = workflow.phase === 'ready' && job ? (statusLabels[job.status] ?? '작업 상태 확인 중') : phaseLabels[workflow.phase];
  const isBusy = workflow.phase === 'creating' || workflow.phase === 'uploading' || workflow.phase === 'running';
  const canSubmit = Boolean(problemFile && teacherSolutionFile && !isBusy);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!problemFile || !teacherSolutionFile || isBusy) {
      return;
    }

    setWorkflow((current) => nextWorkflowState(current, { type: 'start' }));

    try {
      const result = await runUploadToReviewWorkflow(
        { problemFile, teacherSolutionFile },
        {
          onPhase: (phase) => setWorkflow((current) => nextWorkflowState(current, { type: phase }))
        }
      );
      setWorkflow((current) => nextWorkflowState(current, { type: 'ready', job: result }));
    } catch (error) {
      setWorkflow((current) =>
        nextWorkflowState(current, {
          type: 'error',
          message: error instanceof Error ? error.message : '작업을 완료하지 못했습니다.'
        })
      );
    }
  };

  const handleReset = () => {
    setProblemFile(null);
    setTeacherSolutionFile(null);
    setWorkflow((current) => nextWorkflowState(current, { type: 'reset' }));
  };

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
          <div className="job-summary" aria-label="작업 상태" role="status" aria-live="polite">
            <span>검토 항목 {visibleReviewItems.length}</span>
            <span>{statusLabel}</span>
          </div>
        </header>
        <form className="upload-panel" aria-label="이미지 업로드" onSubmit={handleSubmit}>
          <div className="upload-grid">
            <label className="file-field">
              <span>원본 문제 이미지</span>
              <input
                type="file"
                accept="image/png,image/jpeg"
                disabled={isBusy}
                onChange={(event) => setProblemFile(event.currentTarget.files?.[0] ?? null)}
              />
              <small className="file-name">{problemFile?.name ?? '선택된 파일 없음'}</small>
            </label>
            <label className="file-field">
              <span>선생님 손풀이 이미지</span>
              <input
                type="file"
                accept="image/png,image/jpeg"
                disabled={isBusy}
                onChange={(event) => setTeacherSolutionFile(event.currentTarget.files?.[0] ?? null)}
              />
              <small className="file-name">{teacherSolutionFile?.name ?? '선택된 파일 없음'}</small>
            </label>
          </div>
          <div className="workflow-actions">
            <button type="submit" disabled={!canSubmit}>
              업로드 후 분석 실행
            </button>
            <button type="button" disabled={isBusy} onClick={handleReset}>
              다시 선택
            </button>
          </div>
          {workflow.phase === 'error' ? (
            <p className="workflow-error" role="alert">
              {workflow.errorMessage}
            </p>
          ) : null}
        </form>
        <EditorCanvas candidateSpec={job?.candidateSpec ?? null} markerReviewItem={markerReviewItem} />
      </section>
      <ReviewPanel items={reviewItems} />
    </main>
  );
}
