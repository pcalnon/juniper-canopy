# Thread Handoff Procedure

**Purpose**: Preserve context fidelity during long-running Amp sessions by proactively handing off to a new thread before context compaction degrades output quality.

**Last Updated**: 2026-02-20

---

## Why Handoff Over Compaction

Thread compaction summarizes prior context to free token capacity. This introduces **information loss** — subtle details about decisions made, edge cases discovered, partial progress, and the reasoning behind specific implementation choices get compressed or dropped. For complex, multi-step work on JuniperCanopy (e.g., multi-component refactors, Dash callback rewiring, WebSocket protocol changes, cross-layer debugging), this degradation can cause:

- Repeated mistakes the thread already resolved
- Inconsistent code style mid-task
- Loss of discovered constraints or gotchas
- Re-reading files that were already understood

A **proactive handoff** transfers a curated, high-signal summary to a fresh thread with full context capacity, preserving the critical information while discarding the noise.

---

## When to Initiate a Handoff

Trigger a handoff when **any** of the following conditions are met:

| Condition                   | Indicator                                                                                                                   |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Context saturation**      | Thread has performed 15+ tool calls or edited 5+ files                                                                      |
| **Phase boundary**          | A logical phase of work is complete (e.g., planning done → implementation starting; implementation done → testing starting) |
| **Degraded recall**         | The agent re-reads a file it already read, or asks a question it already resolved                                           |
| **Multi-module transition** | Moving from one major component to another (e.g., `components/` → `communication/` → `tests/`)                              |
| **User request**            | User says "hand off", "new thread", "continue in a fresh thread", or similar                                                |

**Do NOT handoff** when:

- The task is nearly complete (< 2 remaining steps)
- The current thread is still sharp and producing correct output
- The work is tightly coupled and splitting would lose critical in-flight state

---

## Handoff Protocol

### Step 1: Checkpoint Current State

Before initiating the handoff, mentally inventory:

1. **What was the original task?** (user's request, verbatim or paraphrased)
2. **What has been completed?** (files created, files edited, tests passed/failed)
3. **What remains?** (specific next steps, not vague summaries)
4. **What was discovered?** (gotchas, constraints, decisions, rejected approaches)
5. **What files are in play?** (paths of files read, modified, or relevant)

### Step 2: Compose the Handoff Goal

Write a **concise, actionable** goal for the new thread. Structure it as:

```bash
Continue [TASK DESCRIPTION].

Completed so far:
- [Concrete item 1]
- [Concrete item 2]

Remaining work:
- [Specific next step 1]
- [Specific next step 2]

Key context:
- [Important discovery or constraint]
- [File X was modified to do Y]
- [Approach Z was rejected because...]
```

**Rules for the goal**:

- **Be specific**: "Add error handling to `CascorIntegration.connect()`" not "finish the error handling work"
- **Include file paths**: The new thread doesn't know what you've been looking at
- **State decisions made**: So the new thread doesn't re-litigate them
- **Mention test status**: If tests were run, state pass/fail counts
- **Keep it under ~500 words**: Dense signal, no filler

### Step 3: Execute the Handoff

Present the composed handoff goal to the user and recommend starting a new thread with it as the initial prompt. If the `handoff()` tool is available:

```bash
handoff(
    goal="<composed goal from Step 2>",
    follow=true
)
```

- Set `follow=true` when the current thread should stop and work continues in the new thread (the common case).
- Set `follow=false` only if the current thread has independent remaining work (rare).

---

## Handoff Goal Templates

### Template: Implementation In Progress

```bash
Continue implementing [FEATURE] in JuniperCanopy.

Completed:
- Created [file1] with [description]
- Modified [file2] to [change description]
- Tests in [test_file] pass (X/Y passing)

Remaining:
- Implement [specific component/callback]
- Add tests for [specific behavior]
- Update constants in src/constants.py if needed

Key context:
- Using [pattern/approach] because [reason]
- [File X] has a constraint: [detail]
- Run tests with: cd src && pytest tests/ -v
```

### Template: Debugging Session

```bash
Continue debugging [ISSUE DESCRIPTION] in JuniperCanopy.

Findings so far:
- Root cause is likely in [file:line] because [evidence]
- Ruled out: [rejected hypothesis 1], [rejected hypothesis 2]
- Reproduced with: [command or test]

Next steps:
- Verify hypothesis by [specific action]
- Apply fix in [file]
- Run [specific test] to confirm

Key context:
- The bug manifests as [symptom]
- Related code path: [file1] → [file2] → [file3]
```

### Template: Multi-Phase Task (Phase Transition)

```bash
Continue [OVERALL TASK] — starting Phase [N]: [PHASE NAME].

Phase [N-1] ([PREV PHASE NAME]) completed:
- [Deliverable 1]
- [Deliverable 2]
- All tests passing: cd src && pytest tests/ -v

Phase [N] scope:
- [Step 1]
- [Step 2]
- [Step 3]

Key context from prior phases:
- [Decision or discovery that affects this phase]
- [File modified in prior phase that this phase depends on]
```

### Template: Frontend Component Work

```bash
Continue [COMPONENT TASK] in JuniperCanopy.

Completed:
- Modified [component file] in src/components/
- Updated [callback] in [file]
- Dash layout changes in [file]

Remaining:
- Wire up [callback/store] for [behavior]
- Update WebSocket handler in src/communication/websocket_manager.py
- Add integration test in src/tests/integration/

Key context:
- Component uses [Dash pattern] (e.g., dcc.Store, clientside callback)
- WebSocket message type: [type] with schema [brief description]
- Demo mode behavior: [how demo mode handles this]
- Run app in demo mode: ./demo
- Run tests: cd src && pytest tests/ -v
```

---

## Best Practices

1. **Handoff early, not late** — A handoff at 70% context usage is better than compaction at 95%
2. **One handoff per phase boundary** — Don't chain 5 handoffs for one task; batch related work
3. **Include the verification command** — Always tell the new thread how to check its work (`cd src && pytest tests/ -v`, etc.)
4. **Reference CLAUDE.md** — The new thread will read it automatically, but call out any project-specific conventions relevant to the remaining work
5. **Don't duplicate CLAUDE.md content** — The new thread already has it; only include task-specific context
6. **State the git status** — If files are staged, modified, or if a branch is in use, mention it

---

## Integration with Project Workflow

This procedure complements the existing development workflow in CLAUDE.md. When a thread handoff occurs during feature development:

- The new thread should verify it can run tests before making changes
- The new thread should re-read any file it plans to edit (fresh context, no assumptions)
- If the handoff crosses a major boundary (e.g., code → documentation), the new thread should check the relevant `notes/` and `docs/` files for consistency

---

## Examples

### Example 1: Simple Handoff

> *Thread has added a new Dash component and its callback, but still needs to wire it to the WebSocket layer and add tests.*

```bash
Continue adding the network health indicator to JuniperCanopy.

Completed:
- Added NetworkHealthBadge component in src/components/network_health.py
- Added Dash callback in src/callbacks/network_health_callbacks.py
- Component renders correctly in demo mode (manual verification)

Remaining:
- Subscribe to WebSocket "metrics" messages in src/communication/websocket_manager.py
- Add dcc.Store for health state persistence across tab switches
- Add unit tests in src/tests/unit/test_network_health.py
- Add integration test verifying WebSocket → component data flow

Key context:
- Health thresholds defined in src/constants.py (HEALTH_WARNING_THRESHOLD, HEALTH_CRITICAL_THRESHOLD)
- Using the standardized message builder pattern (create_metrics_message)
- Verify with: cd src && pytest tests/ -v
- Demo mode: ./demo
```

### Example 2: Handoff After Discovery

> *Thread was asked to fix a layout bug but discovered a deeper state management issue.*

```bash
Continue fixing the metrics panel layout issue in JuniperCanopy. Investigation
revealed the root cause is not CSS but a stale dcc.Store value.

Findings:
- The metrics panel collapses because dcc.Store('training-state') retains
  stale data after a WebSocket reconnect
- src/communication/websocket_manager.py does not clear stores on reconnect
- The layout callback in src/callbacks/metrics_callbacks.py uses
  prevent_initial_call=True, which skips the reset

Remaining:
- Add store-clearing logic to websocket_manager.py on_connect handler
- Remove prevent_initial_call=True from the affected callback (or add
  an explicit initialization path)
- Add test for reconnect → store reset → layout re-render

Key context:
- Do NOT change the WebSocket message schema
- The fix must work in both demo mode and live backend mode
- Run tests: cd src && pytest tests/ -v
```
