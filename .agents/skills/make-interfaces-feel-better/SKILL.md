---
name: make-interfaces-feel-better
description: Refine an existing interface's visual polish, alignment, typography, surfaces and interaction feedback when the user asks for polish or identifies a concrete visual defect. Not a blanket trigger for every frontend task; preserve the task flow and established design system.
---

# Focused interface polish

Start with the target user, their immediate task and the visible defect. Fix task-completion or state-integrity problems before cosmetics. A polish request is not permission for an unrelated redesign.

## Work within the project

1. Inspect the affected route/component, state and data boundaries, reusable components and design tokens.
2. Pick the smallest change that resolves the observable problem. Preserve existing navigation and interaction conventions unless redesign is requested.
3. Prefer project tokens for spacing, typography, colors, radii, shadows and motion. Do not add a new icon/motion package for polish.
4. Check loading, empty, error and disabled states, keyboard/focus behavior, mobile layout, clipped text and layout shift.
5. Test the exact flow plus one risky adjacent transition and run the relevant build/check. Report what was actually verified and remaining risks.

## Use reference techniques selectively

Read only the reference needed for the identified defect:

- [Typography](typography.md): wrapping, legibility and stable dynamic numbers.
- [Surfaces](surfaces.md): nesting, alignment, shadows, outlines and hit areas.
- [Animations](animations.md): interruptible feedback and state transitions.
- [Performance](performance.md): explicit transition properties and measured compositing hints.

References contain illustrative defaults, not requirements to apply every effect. This rule overrides their absolute aesthetic prescriptions: project tokens and accessibility win over numeric examples, pure-black/white outlines, shadow-over-border preferences, a fixed press scale, spring values or stagger timing. Do not animate merely because a technique exists. Honor reduced motion and keep feedback usable with animation disabled. Retain visible focus and contrast, avoid overlapping touch targets, and use the project's accessible target-size rules.

For meaningful motion, prefer existing interruptible primitives, explicit animated properties and no unnecessary initial-load animation. Add `will-change` only when justified by observed performance, not universally.

## Handoff

Lead with the user-visible outcome, checks and residual risks. Use a compact before/after table only when it clarifies several changes; do not require a table for every CSS edit. Do not claim visual verification from a successful build alone. Deployment still follows the user's current authorization.
