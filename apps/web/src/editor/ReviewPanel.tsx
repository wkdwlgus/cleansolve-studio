import type { ReviewItem } from '../types/spec';

interface ReviewPanelProps {
  items: ReviewItem[];
}

export function ReviewPanel({ items }: ReviewPanelProps) {
  return (
    <aside className="review-panel" aria-label="검토 패널">
      <div className="panel-header">
        <h2>검토</h2>
        <span>{items.length}/3</span>
      </div>
      {items.length === 0 ? (
        <p className="empty-state">사용자 확인이 필요한 항목이 없습니다.</p>
      ) : (
        <ul className="review-list">
          {items.map((item) => (
            <li key={item.element_id}>
              <strong>{item.type}</strong>
              <span>{item.review_reason}</span>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
