# MVP Roadmap Design

Date: 2026-06-14
Status: Approved for documentation

## Context

The initial CleanSolve Studio scaffold has been merged into `main`. The project now has a working monorepo foundation, but the path from scaffold to MVP is not visible enough. The next required artifact is not feature code; it is a roadmap that maps `SoT.md` MVP scope and success criteria to concrete milestones.

All user-facing README-style documentation should be written in Korean. Superpowers planning artifacts may use English when they are internal process documents, but this design keeps the roadmap intent explicit for future agents.

## Problem

Without a milestone roadmap, each next task feels arbitrary. The project needs a durable source that answers:

- What is already done?
- What is partial?
- What remains before MVP?
- What order should implementation PRs follow?
- What files or sample inputs does the user need to provide?
- Which milestone should the next Superpowers spec/plan target?

## Decision

Create `docs/product/mvp-roadmap.md` as the product-facing roadmap, written in Korean.

The roadmap should:

- Map current scaffold status against the SoT MVP scope.
- Define milestones from scaffold completion through MVP E2E verification.
- Include acceptance criteria for each milestone.
- List optional user-provided files when a milestone benefits from real sample images.
- Track all 22 SoT MVP success criteria as Done, Partial, or Not Started.
- Recommend the next implementation milestone.

## Milestone Model

Use these milestones:

1. M0 Scaffold Foundation
2. M1 Image Ingestion & Artifact Storage
3. M2 Candidate Spec Pipeline
4. M3 Renderer Coverage Expansion
5. M4 Web Upload-to-Review Flow
6. M5 Spec Patch & Deterministic Re-render
7. M6 Export Foundation
8. M7 OpenAI Adapter Integration
9. M8 MVP E2E Harness & Release Checklist

## Status Definitions

- Done: The scaffold already satisfies the expected MVP behavior for this scope.
- Partial: A foundation exists, but MVP behavior or integration is incomplete.
- Not Started: No meaningful implementation exists yet.
- Blocked by input: Implementation can start with synthetic fixtures, but meaningful validation needs user-provided sample files.

## User Inputs

No user-provided file is required to write the roadmap.

For later implementation milestones, the most useful files are:

- One original math problem image.
- One teacher handwritten solution image for the same problem.
- Optional expected cleaned result image for visual QA.

If these are not available, implementation should start with synthetic fixtures.

## Recommended Next Step

After this roadmap lands, the next implementation work should be `M1. Image Ingestion & Artifact Storage`.

Reasoning:

- It is the first SoT MVP success criterion.
- It encodes the product rule that original images are the highest Source of Truth.
- Later pipeline, rendering, review, and export work all depend on stable job artifacts.

## Acceptance Criteria

- `docs/product/mvp-roadmap.md` exists.
- The roadmap is written in Korean.
- It includes current state, milestones, acceptance criteria, optional user inputs, SoT success criteria mapping, and recommended next PR order.
- The next implementation milestone is explicit.
- No implementation code is changed by this documentation task.

