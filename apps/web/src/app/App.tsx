import { EditorCanvas } from '../editor/EditorCanvas';
import { ReviewPanel } from '../editor/ReviewPanel';
import { getStylePresetLabel } from '../editor/editorCopy';

const ACTIVE_STYLE_PRESET = 'default_pretty_handwriting';

export function App() {
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
            <span>검토 항목 0</span>
            <span>자동 보정 대기</span>
          </div>
        </header>
        <EditorCanvas />
      </section>
      <ReviewPanel items={[]} />
    </main>
  );
}
