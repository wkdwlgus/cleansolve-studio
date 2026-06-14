# 초기 Workflow

첫 runtime workflow는 LangGraph를 사용하며 아래 경로를 따른다.

```text
CREATED
STYLE_PRESET_LOADED
SPEC_EXTRACTED
SPEC_VALIDATING
RENDERED
INSPECTING
CORRECTION_PLANNING
AUTO_REVISING
APPROVED or NEEDS_REVIEW
```

workflow는 시스템 내장 스타일 프리셋을 로드하고, mock analysis client로 candidate spec을 만든다. 이후 spec 검증, SVG overlay preview 렌더링, deterministic mock issue 검사, correction plan 생성, 제한된 자동 revision 적용을 거친다. 마지막으로 `requires_human_review=true` 항목만 사용자 review 대상으로 노출한다.

`max_revision_attempts` 기본값은 `2`다. 현재 테스트는 mock workflow가 HITL 이전에 자동 revision을 수행하고, 보이는 review item 없이 승인 상태로 끝나는 흐름을 검증한다.
