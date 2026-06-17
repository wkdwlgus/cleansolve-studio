import type { ReviewItem } from '../types/spec';
import { REVIEW_ITEM_LIMIT, filterHumanReviewItems, getPrimitiveTypeLabel, getReviewReasonText } from './reviewHelpers';

interface ReviewPanelProps {
  items: ReviewItem[];
  onSelectItem?: (item: ReviewItem) => void;
  selectionDisabled?: boolean;
}

export function ReviewPanel({ items, onSelectItem, selectionDisabled = false }: ReviewPanelProps) {
  const reviewItems = filterHumanReviewItems(items);

  return (
    <aside className="review-panel" aria-label="검토 패널">
      <div className="panel-header">
        <h2>사람 검토</h2>
        <span>{reviewItems.length}/{REVIEW_ITEM_LIMIT}</span>
      </div>
      {reviewItems.length === 0 ? (
        <p className="empty-state">사용자 확인이 필요한 항목이 없습니다.</p>
      ) : (
        <ul className="review-list">
          {reviewItems.map((item) => (
            <li key={item.element_id}>
              <strong>{getPrimitiveTypeLabel(item.type)}</strong>
              <span>{getReviewReasonText(item)}</span>
              {onSelectItem ? (
                <button type="button" disabled={selectionDisabled} onClick={() => onSelectItem(item)}>
                  수정
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
