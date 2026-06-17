import { FormEvent, useMemo, useState } from 'react';
import { patchCandidateSpec, renderJobPreview, runUploadToReviewWorkflow } from '../api/client';
import { EditorCanvas } from '../editor/EditorCanvas';
import { ReviewPanel } from '../editor/ReviewPanel';
import { createTargetAnchorDraft, draftToSpecPatchRequest, type TargetAnchorDraft } from '../editor/editDraft';
import { getStylePresetLabel } from '../editor/editorCopy';
import { filterHumanReviewItems } from '../editor/reviewHelpers';
import type { ReviewItem } from '../types/spec';
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

type EditPhase = 'idle' | 'saving' | 'rendering';

export function App() {
  const [workflow, setWorkflow] = useState(initialWorkflowState);
  const [problemFile, setProblemFile] = useState<File | null>(null);
  const [teacherSolutionFile, setTeacherSolutionFile] = useState<File | null>(null);
  const [selectedReviewItem, setSelectedReviewItem] = useState<ReviewItem | null>(null);
  const [editDraft, setEditDraft] = useState<TargetAnchorDraft | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [editPhase, setEditPhase] = useState<EditPhase>('idle');
  const [renderedPreviewSvg, setRenderedPreviewSvg] = useState<string | null>(null);
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
      setSelectedReviewItem(null);
      setEditDraft(null);
      setEditError(null);
      setRenderedPreviewSvg(null);
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
    setSelectedReviewItem(null);
    setEditDraft(null);
    setEditError(null);
    setEditPhase('idle');
    setRenderedPreviewSvg(null);
    setWorkflow((current) => nextWorkflowState(current, { type: 'reset' }));
  };

  const handleSelectReviewItem = (item: ReviewItem) => {
    if (editPhase !== 'idle') {
      return;
    }
    setSelectedReviewItem(item);
    const draft = createTargetAnchorDraft(job?.candidateSpec ?? null, item);
    setEditDraft(draft);
    setEditError(draft ? null : '이 검토 항목은 M5 편집 패널에서 수정할 수 없습니다.');
  };

  const updateDraftNumber = (key: keyof TargetAnchorDraft, value: string) => {
    if (!editDraft) {
      return;
    }
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return;
    }
    setEditDraft({ ...editDraft, [key]: parsed });
  };

  const handleSaveEdit = async () => {
    if (!job || !editDraft || editPhase !== 'idle') {
      return;
    }

    setEditPhase('saving');
    setEditError(null);
    try {
      const patchResponse = await patchCandidateSpec(job.jobId, draftToSpecPatchRequest(editDraft));
      setEditPhase('rendering');
      const renderResponse = await renderJobPreview(job.jobId);
      const updatedJob = {
        ...job,
        candidateSpec: patchResponse.candidate_spec
      };
      setWorkflow((current) => nextWorkflowState(current, { type: 'ready', job: updatedJob }));
      setEditDraft(createTargetAnchorDraft(patchResponse.candidate_spec, selectedReviewItem));
      setRenderedPreviewSvg(renderResponse.svg);
      setEditPhase('idle');
    } catch (error) {
      setEditPhase('idle');
      setEditError(error instanceof Error ? error.message : 'spec 수정사항을 저장하지 못했습니다.');
    }
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
        <section className="edit-panel" aria-label="선택 항목 수정">
          <div className="panel-header">
            <h2>선택 항목 수정</h2>
            <span>{editPhase === 'idle' ? '대기' : editPhase === 'saving' ? '저장 중' : '렌더링 중'}</span>
          </div>
          {selectedReviewItem ? (
            <p className="selected-review">
              {selectedReviewItem.element_id}
            </p>
          ) : (
            <p className="empty-state">검토 패널에서 수정할 항목을 선택하세요.</p>
          )}
          {editDraft ? (
            <>
              <div className="edit-grid">
                <label>
                  <span>시작점 x</span>
                  <input
                    type="number"
                    value={editDraft.startX}
                    disabled={editPhase !== 'idle'}
                    onChange={(event) => updateDraftNumber('startX', event.currentTarget.value)}
                  />
                </label>
                <label>
                  <span>시작점 y</span>
                  <input
                    type="number"
                    value={editDraft.startY}
                    disabled={editPhase !== 'idle'}
                    onChange={(event) => updateDraftNumber('startY', event.currentTarget.value)}
                  />
                </label>
                <label>
                  <span>끝점 x</span>
                  <input
                    type="number"
                    value={editDraft.endX}
                    disabled={editPhase !== 'idle'}
                    onChange={(event) => updateDraftNumber('endX', event.currentTarget.value)}
                  />
                </label>
                <label>
                  <span>끝점 y</span>
                  <input
                    type="number"
                    value={editDraft.endY}
                    disabled={editPhase !== 'idle'}
                    onChange={(event) => updateDraftNumber('endY', event.currentTarget.value)}
                  />
                </label>
              </div>
              <button type="button" className="save-edit-button" disabled={editPhase !== 'idle'} onClick={handleSaveEdit}>
                저장 후 미리보기 갱신
              </button>
            </>
          ) : null}
          {renderedPreviewSvg ? (
            <p className="render-summary">서버 SVG preview {renderedPreviewSvg.length}자 저장됨</p>
          ) : null}
          {editError ? (
            <p className="workflow-error" role="alert">
              {editError}
            </p>
          ) : null}
        </section>
      </section>
      <ReviewPanel items={reviewItems} onSelectItem={handleSelectReviewItem} selectionDisabled={editPhase !== 'idle'} />
    </main>
  );
}
