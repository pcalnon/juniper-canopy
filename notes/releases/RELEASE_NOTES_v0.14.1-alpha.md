# JuniperCanopy v0.14.1-alpha – SECURITY PATCH RELEASE

**This is a security-focused point release addressing a critical vulnerability in a transitive dependency (`filelock`). All users whose environments resolve `filelock` to version 3.20.0 are strongly advised to upgrade.**

JuniperCanopy is a real-time monitoring and diagnostic frontend for Cascade Correlation Neural Networks (CasCor). This release does not introduce new features; it focuses on security hardening and minor documentation improvements.

---

## Security Impact (Critical)

| Attribute | Value |
| ----------- | ------- |
| **Vulnerable package** | `filelock` 3.20.0 |
| **Vulnerability class** | TOCTOU (Time-of-Check to Time-of-Use) race condition |
| **Attack vector** | Symlink-based attacks during lock file creation |
| **Upstream fix** | `filelock` 3.20.2 |

In environments where JuniperCanopy runs on a filesystem shared with untrusted users, an attacker could exploit a race condition during lock file creation. By manipulating symbolic links at the time locks are created, an attacker may be able to:

- Redirect lock files to unintended locations
- Overwrite or create files in paths they should not control
- Potentially cause denial-of-service or contribute to broader exploitation depending on local configuration

JuniperCanopy relies on `filelock` for runtime locking behavior, so installations using the vulnerable `filelock` version inherit this risk.

**Reference:** [Dependabot security advisory](https://github.com/pcalnon/Juniper/security/dependabot/1) *(pre-polyrepo URL; Dependabot alerts now reside in individual repo security tabs)*

---

## Affected Versions

JuniperCanopy deployments are affected if **both** of the following are true:

1. They are based on **v0.14.0-alpha** (or earlier versions/alpha snapshots that allow `filelock` 3.20.0), **and**
2. Their environment resolves `filelock` to **3.20.0** (for example, via `pip`, a requirements file, or a lockfile that includes this version).

Any JuniperCanopy environment that installs `filelock==3.20.0` is potentially vulnerable.

---

## Remediation / Upgrade Instructions

**Recommended action:** Upgrade to **JuniperCanopy v0.14.1-alpha** and ensure `filelock` is at least **3.20.2**.

### 1. Upgrade JuniperCanopy

If using Git directly:

```bash
git fetch origin
git checkout v0.14.1-alpha
# Rebuild / reinstall your environment as usual
```

If using a dependency manager (e.g., `requirements.txt`, `pyproject.toml`, or a lockfile):

1. Update the JuniperCanopy version to **v0.14.1-alpha**.
2. Regenerate and reinstall dependencies.

### 2. Ensure a Safe `filelock` Version

In your dependency definitions, explicitly require:

```text
filelock>=3.20.2,<3.21
```

Then reinstall dependencies, for example:

```bash
pip install --upgrade -r requirements.txt
# or your project's equivalent install command
```

### Temporary Mitigation (Not a Substitute for Upgrading)

If you cannot immediately update JuniperCanopy, you should at minimum:

- Explicitly pin `filelock` to **3.20.2** (or later patched 3.20.x) in your environment
- Reinstall dependencies to ensure the vulnerable 3.20.0 version is no longer present

However, the **recommended** and supported remediation is to upgrade to **v0.14.1-alpha**.

---

## Changes in v0.14.1-alpha

### Security

- **Updated dependency:** `filelock` **3.20.0 → 3.20.2**
  - Addresses a TOCTOU race condition that could be exploited via symlink attacks during lock file creation
  - Aligns JuniperCanopy with the upstream security fix described in the Dependabot advisory

### Documentation

- **Improved documentation clarity:**
  - Corrected table formatting in `DOCUMENTATION_OVERVIEW.md` to improve readability and clarity for CasCor monitoring and diagnostic workflows

---

## Testing & Quality

| Metric | Result |
| -------- | -------- |
| **Tests passed** | 1665 |
| **Tests skipped** | 37 |
| **Runtime** | 92.23 seconds |
| **Coverage** | 90% overall |

These results cover the updated dependency set and related code paths.

---

## Upgrade Recommendation

We recommend that all users, especially those running JuniperCanopy in **multi-user**, **shared**, or **untrusted local user** environments, upgrade to **v0.14.1-alpha** as soon as practicable.

If you encounter issues during upgrade or have questions about this advisory, please open an issue in this repository (avoiding sensitive environment details in public tickets). We will coordinate on secure channels as needed.

---

## References

- [Dependabot Security Advisory](https://github.com/pcalnon/Juniper/security/dependabot/1) *(pre-polyrepo URL)*
- [JuniperCanopy v0.14.0-alpha Release Notes](RELEASE_v0.14.0-alpha.md)
- [CHANGELOG.md](../CHANGELOG.md)
