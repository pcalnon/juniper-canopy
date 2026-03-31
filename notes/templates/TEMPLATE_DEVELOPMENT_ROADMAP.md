# Development Roadmap Template

**Purpose:** This template defines the required structure and formatting for JuniperCanopy development roadmaps and implementation plans.

**Usage:** Copy this template and replace placeholder text (indicated by `[PLACEHOLDER]`) with actual roadmap information. Update status fields as work progresses.

**Naming Convention:** `DEVELOPMENT_ROADMAP.md` (main roadmap) or `[AREA]_ROADMAP_[TIMEFRAME].md` for area-specific roadmaps.

---

# Juniper Canopy [AREA] Roadmap

**Last Updated:** [YYYY-MM-DD]  
**Version:** [X.Y.Z]  
**Status:** [DRAFT|IN_REVIEW|APPROVED|ACTIVE|ARCHIVED]  
**Owner:** [OWNER_NAME]

---

## Overview

[ONE_TO_THREE_SENTENCES_DESCRIBING_THE_SCOPE_AND_GOALS_OF_THIS_ROADMAP]

### Scope & Timeframe

- **Timeframe:** [E.G._Q3_2026_OR_2026-07_TO_2026-09]
- **Product area(s):** [AREAS_THIS_ROADMAP_COVERS]
- **Target version(s):** [X.Y.Z_RANGE]

### Out of Scope

<!-- Optional: Explicitly state what this roadmap does NOT cover -->

- [OUT_OF_SCOPE_ITEM_1]
- [OUT_OF_SCOPE_ITEM_2]

---

## Goals

- **[GOAL_1]:** [SHORT_DESCRIPTION]
- **[GOAL_2]:** [SHORT_DESCRIPTION]
- **[GOAL_3]:** [SHORT_DESCRIPTION]

### Success Metrics

<!-- Optional: Define measurable success criteria -->

| Metric                    | Current | Target | Notes                  |
| ------------------------- | ------- | ------ | ---------------------- |
| [METRIC_NAME]             | [VALUE] | [VALUE]| [NOTES]                |
| Test Coverage             | [N]%    | 95%+   | [NOTES]                |

---

## Implementation Plan

For detailed implementation plans, see:

- **[Phase 0: Title](LINK_TO_PHASE0_README)** – [BRIEF_DESCRIPTION]
- **[Phase 1: Title](LINK_TO_PHASE1_README)** – [BRIEF_DESCRIPTION]
- **[Phase 2: Title](LINK_TO_PHASE2_README)** – [BRIEF_DESCRIPTION]
- **[Phase 3: Title](LINK_TO_PHASE3_README)** – [BRIEF_DESCRIPTION]

---

## Milestones

| Milestone            | Target Date  | Version(s)   | Description                | Status        |
| -------------------- | ------------ | ------------ | -------------------------- | ------------- |
| [MILESTONE_NAME]     | [YYYY-MM-DD] | [X.Y.Z]      | [WHAT_IT_DELIVERS]         | ✅ Complete   |
| [MILESTONE_NAME]     | [YYYY-MM-DD] | [X.Y.Z]      | [WHAT_IT_DELIVERS]         | 🔄 In Progress|
| [MILESTONE_NAME]     | [YYYY-MM-DD] | [X.Y.Z]      | [WHAT_IT_DELIVERS]         | 📋 Planned    |

---

## Feature & Fix Roadmap

### Fixes and Enhancements by Area

<!-- Organize features/fixes by the area of the application they affect -->

#### [AREA_1] (e.g., Top Status Bar)

- **Fix:** [DESCRIPTION_OF_FIX]
  - [DETAILED_REQUIREMENT_1]
  - [DETAILED_REQUIREMENT_2]

- **Feat:** [DESCRIPTION_OF_FEATURE]
  - [DETAILED_REQUIREMENT_1]
  - [DETAILED_REQUIREMENT_2]

#### [AREA_2] (e.g., Training Controls)

1. **Fix:** [DESCRIPTION_OF_FIX]
   - [DETAILED_REQUIREMENT_1]
   - [DETAILED_REQUIREMENT_2]

2. **Feat:** [DESCRIPTION_OF_FEATURE]
   - [DETAILED_REQUIREMENT_1]
   - [DETAILED_REQUIREMENT_2]

<!-- Repeat for additional areas -->

---

## Current Status of Features and Fixes

### Status per Feature

| Priority | Feature / Fix                          | Status      | Phase | Target Version |
| -------- | -------------------------------------- | ----------- | ----- | -------------- |
| **P0**   | [FEATURE_OR_FIX_DESCRIPTION]           | ✅ Done     | 0     | [X.Y.Z]        |
| **P0**   | [FEATURE_OR_FIX_DESCRIPTION]           | 🔄 Progress | 0     | [X.Y.Z]        |
| **P1**   | [FEATURE_OR_FIX_DESCRIPTION]           | 📋 Planned  | 1     | [X.Y.Z]        |
| **P2**   | [FEATURE_OR_FIX_DESCRIPTION]           | ⏸️ Deferred | 2     | TBD            |
| **P3**   | [FEATURE_OR_FIX_DESCRIPTION]           | 📋 Planned  | 3     | [X.Y.Z]        |

### Status Legend

| Icon | Status      | Description                                |
| ---- | ----------- | ------------------------------------------ |
| ✅   | Done        | Implemented, tested, and released          |
| 🔄   | In Progress | Currently being worked on                  |
| 📋   | Planned     | Scheduled for future implementation        |
| ⏸️   | Deferred    | Postponed to a later phase or version      |
| ❌   | Cancelled   | No longer planned                          |

### Priority Legend

- **P0 (Phase 0):** Critical – Core UX bugs, must fix first
- **P1 (Phase 1):** High – High-impact features
- **P2 (Phase 2):** Medium – Polish and medium-priority
- **P3 (Phase 3):** Low – Advanced/infrastructure features

---

## What's Next

### Near-Term (Next 2-4 Weeks)

- [ITEM_1] – [EXPECTED_OUTCOME]
- [ITEM_2] – [EXPECTED_OUTCOME]

### Next Release (v[UPCOMING_VERSION])

- [ITEM_3] – [EXPECTED_OUTCOME]
- [ITEM_4] – [EXPECTED_OUTCOME]

### Coverage Goals

- [FILE] currently at [N]%, target 95%

---

## Dependencies

<!-- Optional: Document external and internal dependencies -->

| Dependent Item           | Depends On                      | Type       | Risk Level | Notes              |
| ------------------------ | ------------------------------- | ---------- | ---------- | ------------------ |
| [FEATURE_OR_MILESTONE]   | [OTHER_COMPONENT_OR_TEAM]       | [TECH\|ORG] | [L/M/H]    | [DETAILS]          |

### Critical Dependencies

```mermaid
graph TD
    [ITEM_A] --> [ITEM_B]
    [ITEM_B] --> [ITEM_C]
    [ITEM_A] --> [ITEM_D]
```

### Shared Dependencies

All items share dependencies on:

- [SHARED_DEPENDENCY_1]
- [SHARED_DEPENDENCY_2]

---

## Risks & Assumptions

### Risks

| Risk                     | Impact    | Likelihood | Mitigation                          |
| ------------------------ | --------- | ---------- | ----------------------------------- |
| [RISK_DESCRIPTION]       | [H/M/L]   | [H/M/L]    | [MITIGATION_STRATEGY]               |

### High-Risk Areas

1. **[RISK_AREA_1]**
   - Risk: [DESCRIPTION]
   - Mitigation: [STRATEGY]

### Medium-Risk Areas

1. **[RISK_AREA_2]**
   - Risk: [DESCRIPTION]
   - Mitigation: [STRATEGY]

### Low-Risk Areas

- [LOW_RISK_ITEM_1]
- [LOW_RISK_ITEM_2]

### Assumptions

- [ASSUMPTION_1]
- [ASSUMPTION_2]

---

## Test Coverage Requirements

| Phase   | Unit Tests | Integration Tests | Target Coverage |
| ------- | ---------- | ----------------- | --------------- |
| Phase 0 | [N]        | [N]               | [N]%            |
| Phase 1 | [N]        | [N]               | [N]%            |
| Phase 2 | [N]        | [N]               | [N]%            |
| Phase 3 | [N]        | [N]               | [N]%            |

---

## Out-of-Scope / Future Ideas

<!-- Optional: Track ideas that are explicitly not in current scope -->

- [IDEA_OR_FEATURE] – [WHY_NOT_NOW]
- [IDEA_OR_FEATURE] – [POTENTIAL_TIMELINE_OR_N/A]

---

## References

- [Implementation Plan](IMPLEMENTATION_PLAN.md)
- [Phase 0 Documentation](phase0/README.md)
- [Phase 1 Documentation](phase1/README.md)
- [Phase 2 Documentation](phase2/README.md)
- [Phase 3 Documentation](phase3/README.md)
- [CHANGELOG](../../CHANGELOG.md)
- [AGENTS.md](../../AGENTS.md)

---

## Change Log

| Date       | Version | Changes                              | Author       |
| ---------- | ------- | ------------------------------------ | ------------ |
| [DATE]     | [X.Y.Z] | [DESCRIPTION_OF_CHANGES]             | [AUTHOR]     |
| [DATE]     | [X.Y.Z] | Initial roadmap creation             | [AUTHOR]     |
