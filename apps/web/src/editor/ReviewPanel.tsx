import type { ReviewItem } from '../types/spec';
import { filterHumanReviewItems, getPrimitiveTypeLabel, getReviewReasonText } from './reviewHelpers';

interface ReviewPanelProps {
  items: ReviewItem[];
}

export function ReviewPanel({ items }: ReviewPanelProps) {
  const reviewItems = filterHumanReviewItems(items);

  return (
    <aside className="review-panel" aria-label="검토 패널">
      <div className="panel-header">
        <h2>사람 검토</h2>
        <span>{reviewItems.length}/3</span>
      </div>
      {reviewItems.length === 0 ? (
        <p className="empty-state">사용자 확인이 필요한 항목이 없습니다.</p>
      ) : (
        <ul className="review-list">
          {reviewItems.map((item) => (
            <li key={item.element_id}>
              <strong>{getPrimitiveTypeLabel(item.type)}</strong>
              <span>{getReviewReasonText(item)}</span>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
