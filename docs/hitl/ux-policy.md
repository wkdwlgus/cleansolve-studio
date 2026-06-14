# HITL UX 정책

HITL은 예외 경로이다. `needs_review=true`는 시스템 내부 검증이나 자동 보정이 필요하다는 뜻이며, 곧바로 사용자에게 노출된다는 뜻이 아니다.

editor review panel에는 `requires_human_review=true`이고 아직 해결되지 않은 항목만 노출한다. 한 job에서 사용자에게 보이는 review item budget은 3개다. 3개를 초과하는 job은 harness에서 품질 경고로 다룬다.

수정 방식은 먼저 시각적이어야 한다.

- 후보 승인 또는 거절
- endpoint drag
- label drag
- curve control point drag
- 후보 중 선택

기본 UI는 사용자에게 수학적 점 이름, 선분 이름, `OR`, `QR` 같은 명령어 입력을 요구하지 않는다.
