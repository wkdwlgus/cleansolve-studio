# Assumptions

- The initial scaffold uses local filesystem storage under `var/jobs`.
- The built-in handwriting style preset is represented by metadata first; generated style assets can be added later.
- Mock AI output is acceptable for initial workflow and harness tests.
- Server-side deterministic rendering starts with SVG output before PNG/PDF export is completed.
- The web editor shell can render sample spec data before upload and export are feature-complete.
