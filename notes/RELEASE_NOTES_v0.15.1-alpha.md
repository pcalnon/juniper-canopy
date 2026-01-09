# JuniperCanopy v0.15.1-alpha – 🔒 SECURITY PATCH RELEASE

**Release Date:** 2026-01-07
**Release Type:** Security Patch  
**Priority:** High
**Package Affected:** JuniperCanopy

**This is a security-focused point release addressing a critical vulnerability in a transitive dependency (`urllib3`). All users whose environments resolve `urllib3` to version 2.6.2 or earlier are strongly advised to upgrade.**

JuniperCanopy is a real-time monitoring and diagnostic frontend for Cascade Correlation Neural Networks (CasCor). This release does not introduce new features; it focuses on security hardening.

---

## Security Impact (Critical)

| Attribute               | Value                                                     |
| ----------------------- | --------------------------------------------------------- |
| **Vulnerable package**  | `urllib3` ≤2.6.2                                          |
| **Vulnerability class** | Decompression bomb (CWE-409)                              |
| **Attack vector**       | Malicious HTTP redirect responses with compressed content |
| **Upstream fix**        | `urllib3` 2.6.3                                           |

In environments where JuniperCanopy makes HTTP requests to untrusted sources using the streaming API (`preload_content=False`), an attacker could exploit a flaw in redirect handling. When following HTTP redirects, urllib3 would:

- Read the entire response body to drain the connection
- Decompress content unnecessarily before any read methods were called
- Ignore configured read limits for decompressed data

A malicious server could exploit this to trigger excessive resource consumption on the client (high CPU usage and large memory allocations for decompressed data), constituting a decompression bomb attack.

JuniperCanopy relies on `urllib3` for HTTP operations, so installations using the vulnerable `urllib3` version inherit this risk.

**Reference:** [Dependabot security advisory](https://github.com/pcalnon/Juniper/security/dependabot/2)

---

## Affected Versions

JuniperCanopy deployments are affected if **both** of the following are true:

1. They are based on **v0.15.0-alpha** (or earlier versions/alpha snapshots that allow `urllib3` ≤2.6.2), **and**
2. Their environment resolves `urllib3` to **2.6.2 or earlier** (for example, via `pip`, a requirements file, or a lockfile that includes this version).

Any JuniperCanopy environment that installs `urllib3<=2.6.2` is potentially vulnerable.

---

## Remediation / Upgrade Instructions

**Recommended action:** Upgrade to **JuniperCanopy v0.15.1-alpha** and ensure `urllib3` is at least **2.6.3**.

### 1. Upgrade JuniperCanopy

If using Git directly:

```bash
git fetch origin
git checkout v0.15.1-alpha
# Rebuild / reinstall your environment as usual
```

If using a dependency manager (e.g., `requirements.txt`, `pyproject.toml`, or a lockfile):

1. Update the JuniperCanopy version to **v0.15.1-alpha**.
2. Regenerate and reinstall dependencies.

### 2. Ensure a Safe `urllib3` Version

In your dependency definitions, explicitly require:

```text
urllib3>=2.6.3
```

Then reinstall dependencies, for example:

```bash
pip install --upgrade -r requirements.txt
# or your project's equivalent install command
```

### Temporary Mitigation (Not a Substitute for Upgrading)

If you cannot immediately update JuniperCanopy, you should at minimum:

- Explicitly pin `urllib3` to **2.6.3** (or later) in your environment
- Reinstall dependencies to ensure the vulnerable version is no longer present
- Alternatively, disable redirects by setting `redirect=False` for requests to untrusted sources

However, the **recommended** and supported remediation is to upgrade to **v0.15.1-alpha**.

---

## Changes in v0.15.1-alpha

### Security

- **Updated dependency:** `urllib3` **≤2.6.2 → 2.6.3**
  - Addresses a decompression bomb vulnerability that could be exploited via malicious HTTP redirect responses
  - Aligns JuniperCanopy with the upstream security fix described in the Dependabot advisory

---

## Testing & Quality

| Metric | Result |
| -------- | -------- |
| **Tests passed** | 2247 |
| **Tests skipped** | 34 |
| **Coverage** | 95% overall |

These results cover the updated dependency set and related code paths.

---

## Upgrade Recommendation

We recommend that all users, especially those running JuniperCanopy in environments that make HTTP requests to **untrusted sources**, upgrade to **v0.15.1-alpha** as soon as practicable.

If you encounter issues during upgrade or have questions about this advisory, please open an issue in this repository (avoiding sensitive environment details in public tickets). We will coordinate on secure channels as needed.

---

## References

- [Dependabot Security Advisory](https://github.com/pcalnon/Juniper/security/dependabot/2)
- [CWE-409: Improper Handling of Highly Compressed Data](https://cwe.mitre.org/data/definitions/409.html)
- [JuniperCanopy v0.15.0-alpha Release Notes](RELEASE_NOTES_v0.15.0-alpha.md)
- [CHANGELOG.md](../CHANGELOG.md)
