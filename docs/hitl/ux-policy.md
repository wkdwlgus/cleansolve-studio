# HITL UX Policy

HITL is an exception path. `needs_review=true` means the system needs internal validation or automatic correction. It does not mean the user sees the item.

Only `requires_human_review=true` items are exposed in the editor review panel. The review panel budget is three items per job. Jobs that exceed three visible items should be treated as a quality warning in the harness.

Corrections should be visual first:

- approve or reject a candidate
- drag an endpoint
- drag a label
- drag a curve control point
- choose from candidates

The default UI must not ask users to type mathematical point names, segment names, or commands such as `OR` or `QR`.
