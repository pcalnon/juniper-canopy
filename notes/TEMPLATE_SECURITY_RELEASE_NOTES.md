# Security Release Notes Template

**Purpose:** This template defines the required structure, formatting, and organization for all JuniperCanopy security patch release notes.

**Usage:** Copy this template and replace placeholder text (indicated by `[PLACEHOLDER]`) with actual release information.

---

# JuniperCanopy v[VERSION] – 🔒 SECURITY PATCH RELEASE

**Release Date:** [RELEASE_DATE]
**Release Type:** Security Patch  
**Priority:** [PRIORITY_LEVEL]
**Package Affected:** [PACKAGE_NAME]

---

**This is a security-focused point release addressing a critical vulnerability in a transitive dependency (`[PACKAGE_NAME]`). All users whose environments resolve `[PACKAGE_NAME]` to version [VULNERABLE_VERSION] are strongly advised to upgrade.**

JuniperCanopy is a real-time monitoring and diagnostic frontend for Cascade Correlation Neural Networks (CasCor). This release does not introduce new features; it focuses on security hardening.

---

## Security Impact ([SEVERITY])

| Attribute | Value |
| ----------- | ------- |
| **Vulnerable package** | `[PACKAGE_NAME]` [VULNERABLE_VERSION] |
| **Vulnerability class** | [VULNERABILITY_CLASS] ([CWE_ID]) |
| **Attack vector** | [ATTACK_VECTOR_DESCRIPTION] |
| **Upstream fix** | `[PACKAGE_NAME]` [FIXED_VERSION] |

[DETAILED_VULNERABILITY_DESCRIPTION]

[EXPLANATION_OF_HOW_JUNIPERCANOPY_IS_AFFECTED]

**Reference:** [Dependabot security advisory](<DEPENDABOT_ALERT_URL>)

---

## Affected Versions

JuniperCanopy deployments are affected if **both** of the following are true:

1. They are based on **v[PREVIOUS_VERSION]** (or earlier versions/alpha snapshots that allow `[PACKAGE_NAME]` [VULNERABLE_VERSION]) **and**
2. Their environment resolves `[PACKAGE_NAME]` to **[VULNERABLE_VERSION]** (for example, via `pip`, a requirements file, or a lockfile that includes this version).

Any JuniperCanopy environment that installs `[PACKAGE_NAME]==[VULNERABLE_VERSION]` is potentially vulnerable.

---

## Remediation / Upgrade Instructions

**Recommended action:** Upgrade to **JuniperCanopy v[VERSION]** and ensure `[PACKAGE_NAME]` is at least **[FIXED_VERSION]**.

### 1. Upgrade JuniperCanopy

If using Git directly:

```bash
git fetch origin
git checkout v[VERSION]
# Rebuild / reinstall your environment as usual
```

If using a dependency manager (e.g., `requirements.txt`, `pyproject.toml`, or a lockfile):

1. Update the JuniperCanopy version to **v[VERSION]**.
2. Regenerate and reinstall dependencies.

### 2. Ensure a Safe `[PACKAGE_NAME]` Version

In your dependency definitions, explicitly require:

```text
[PACKAGE_NAME]>=[FIXED_VERSION]
```

Then reinstall dependencies, for example:

```bash
pip install --upgrade -r requirements.txt
# or your project's equivalent install command
```

### Temporary Mitigation (Not a Substitute for Upgrading)

If you cannot immediately update JuniperCanopy, you should at minimum:

- Explicitly pin `[PACKAGE_NAME]` to **[FIXED_VERSION]** (or later) in your environment
- Reinstall dependencies to ensure the vulnerable version is no longer present
- [ADDITIONAL_TEMPORARY_MITIGATIONS_IF_ANY]

However, the **recommended** and supported remediation is to upgrade to **v[VERSION]**.

---

## Changes in v[VERSION]

### Security

- **Updated dependency:** `[PACKAGE_NAME]` **[VULNERABLE_VERSION] → [FIXED_VERSION]**
  - [DESCRIPTION_OF_WHAT_THE_FIX_ADDRESSES]
  - Aligns JuniperCanopy with the upstream security fix described in the Dependabot advisory

### Documentation

- [ANY_DOCUMENTATION_CHANGES_OR_REMOVE_SECTION_IF_NONE]

---

## Testing & Quality

| Metric            | Result                      |
| ----------------- | --------------------------- |
| **Tests passed**  | [NUM_PASSED]                |
| **Tests skipped** | [NUM_SKIPPED]               |
| **Runtime**       | [RUNTIME_SECONDS] seconds   |
| **Coverage**      | [COVERAGE_PERCENT]% overall |

These results cover the updated dependency set and related code paths.

---

## Upgrade Recommendation

We recommend that all users, especially those running JuniperCanopy in [RELEVANT_RISK_ENVIRONMENTS], upgrade to **v[VERSION]** as soon as practicable.

If you encounter issues during upgrade or have questions about this advisory, please open an issue in this repository (avoiding sensitive environment details in public tickets). We will coordinate on secure channels as needed.

---

## References

- [Dependabot Security Advisory](DEPENDABOT_ALERT_URL)
- [<CWE_ID>: <CWE_TITLE>](CWE_URL)
- [JuniperCanopy v[PREVIOUS_VERSION] Release Notes](RELEASE_NOTES_v[PREVIOUS_VERSION].md)
- [CHANGELOG.md](../CHANGELOG.md)
