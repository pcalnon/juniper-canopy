# Pull Request Description Template

**Purpose:** This template defines the required structure and formatting for all JuniperCanopy pull request descriptions.

**Usage:** Copy this template and replace placeholder text (indicated by `[PLACEHOLDER]`) with actual pull request information.

---

# Pull Request: [SHORT_DESCRIPTIVE_TITLE]

**Date:** [YYYY-MM-DD]  
**Version(s):** [TARGET_VERSION_OR_RANGE]  
**Author:** [AUTHOR_NAME]  
**Status:** [DRAFT|IN_REVIEW|READY_FOR_MERGE]

---

## Summary

[ONE_OR_TWO_SENTENCES_SUMMARIZING_THE_PR]

---

## Context / Motivation

[EXPLAIN_THE_PROBLEM_OR_GOAL_THIS_PR_ADDRESSES]

- Why this change is needed now
- Links to related design documents, specs, or discussions

---

## Priority & Work Status

<!-- Optional: Use this table when the PR bundles multiple related changes -->

| Priority | Work Item              | The Overtoad    | Status      |
| -------- | ---------------------- | -------- | ----------- |
| P[0-3]   | [FEATURE_OR_TASK_NAME] | [OWNER]  | [STATUS]    |

### Priority Legend

- **P0:** Critical - Core bugs or blockers
- **P1:** High - High-impact features or fixes
- **P2:** Medium - Polish and medium-priority
- **P3:** Low - Advanced/infrastructure features

---

## Changes

<!-- Group by Keep a Changelog categories. Only include sections with content. -->

### Added

- [NEW_FEATURE_OR_ENDPOINT]
- [NEW_CONFIG_FLAG_OR_SETTING]

### Changed

- [BEHAVIOR_OR_API_THAT_CHANGED]
- [UI_OR_INTERNAL_LOGIC_CHANGE]

### Fixed

- [BUG_OR_ISSUE_FIXED] (see [ISSUE-XXX])

### Deprecated

<!-- Optional: Include if deprecating APIs or features -->

- [DEPRECATED_API_OR_FLAG] – Removal no earlier than v[X.Y.Z]

### Removed

<!-- Optional: Include if removing APIs or behavior -->

- [REMOVED_BEHAVIOR_OR_DEAD_CODE]

### Security

<!-- Optional: Include if security-related changes -->

- [SECURITY_RELATED_CHANGE]

---

## Impact & SemVer

- **SemVer impact:** [PATCH|MINOR|MAJOR]
- **User-visible behavior change:** [YES|NO]
- **Breaking changes:** [YES|NO]
  - If **YES**, describe:
    - **What breaks:** [BRIEF_DESCRIPTION]
    - **Migration steps:** [MIGRATION_INSTRUCTIONS_OR_LINK]
- **Performance impact:** [NONE|IMPROVED|REGRESSED] – [SHORT_EXPLANATION]
- **Security/privacy impact:** [NONE|LOW|MEDIUM|HIGH] – [SHORT_EXPLANATION]
- **Guarded by feature flag:** [YES|NO] – [FLAG_NAME_OR_N/A]

---

## Testing & Results

### Test Summary

| Test Type   | Passed | Failed | Skipped | Notes          |
| ----------- | ------ | ------ | ------- | -------------- |
| Unit        | [N]    | [N]    | [N]     | [NOTES_OR_N/A] |
| Integration | [N]    | [N]    | [N]     | [NOTES_OR_N/A] |
| E2E         | [N]    | [N]    | [N]     | [NOTES_OR_N/A] |
| Manual      | [N]    | [N]    | N/A     | [SCENARIOS]    |

### Coverage

| Component | Before | After | Target | Status |
| --------- | ------ | ----- | ------ | ------ |
| [FILE]    | [N]%   | [N]%  | 95%    | [MET]  |

### Environments Tested

- [ENVIRONMENT_1] (e.g., demo mode, local): [RESULT]

---

## Verification Checklist

- [ ] Main user flow(s) verified: [SHORT_DESCRIPTION]
- [ ] Edge cases checked: [LIST_KEY_EDGE_CASES]
- [ ] No regression in related areas: [RELATED_FEATURES]
- [ ] Demo mode works with all new features
- [ ] Feature defaults correct and documented
- [ ] Logging/metrics updated if needed
- [ ] Documentation updated: [LINK_OR_N/A]

---

## API Changes

<!-- Optional: Use if any externally observable API changed -->

| Method   | Endpoint              | Description        | Breaking? |
| -------- | --------------------- | ------------------ | --------- |
| [METHOD] | [/api/v1/endpoint]    | [SUMMARY_OF_CHANGE]| [YES/NO]  |

### Response Codes

**[METHOD] [ENDPOINT]:**

- `[CODE]` – [DESCRIPTION]
- `[CODE]` – [DESCRIPTION]

---

## Files Changed

<!-- Optional: Helpful on large PRs -->

### New Components

- [PATH/TO/NEW_FILE] – [BRIEF_DESCRIPTION]

### Modified Components

**Backend:**

- [PATH/TO/FILE] – [BRIEF_DESCRIPTION]

**Frontend:**

- [PATH/TO/FILE] – [BRIEF_DESCRIPTION]

**Tests:**

- [PATH/TO/TEST_FILE] – [BRIEF_DESCRIPTION]

**Documentation:**

- [PATH/TO/DOC_FILE] – [BRIEF_DESCRIPTION]

---

## Risks & Rollback Plan

<!-- Optional: Include for high-risk changes -->

- **Key risks:** [RISK_1], [RISK_2]
- **Monitoring / alerts to watch:** [METRICS_OR_DASHBOARDS]
- **Rollback plan:** [HOW_TO_DISABLE_FEATURE_OR_REVERT]

---

## Related Issues / Tickets

- Issues: [ISSUE-123], [ISSUE-456]
- Design / Spec: [LINK_TO_DOC]
- Related PRs: [PR-XXX], [PR-YYY]
- Phase Documentation: [LINK_TO_PHASE_README]

---

## What's Next

<!-- Optional: Include for PRs that are part of a larger effort -->

### Remaining Items

| Feature           | Status      | Priority |
| ----------------- | ----------- | -------- |
| [REMAINING_ITEM]  | Not Started | [P0-P3]  |

---

## Notes for Release

<!-- Optional: Pre-formatted snippet for release notes -->

[RELEASE_NOTES_READY_SNIPPET]

---

## Review Notes

<!-- Optional: Notes for reviewers -->

1. [KEY_POINT_FOR_REVIEWERS]
2. [AREAS_NEEDING_EXTRA_ATTENTION]
