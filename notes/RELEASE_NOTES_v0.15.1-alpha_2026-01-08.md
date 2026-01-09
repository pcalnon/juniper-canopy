# Release Notes: v0.15.1-alpha

**Release Date:** 2026-01-08  
**Release Type:** Security Patch  
**Priority:** High

---

## 🔒 Security Release

This is a security patch release addressing a critical vulnerability in the `urllib3` dependency.

---

## Security Advisory

### CVE: Decompression-bomb safeguards bypassed when following HTTP redirects (streaming API)

**Severity:** High  
**Dependabot Alert:** [#2](https://github.com/pcalnon/Juniper/security/dependabot/2)  
**CWE:** CWE-409 (Improper Handling of Highly Compressed Data)

#### Impact

urllib3's streaming API is designed for efficient handling of large HTTP responses by reading content in chunks. When using `preload_content=False`, the library decompresses only necessary bytes.

However, for HTTP redirect responses, urllib3 v2.6.2 and earlier would:

- Read the entire response body to drain the connection
- Decompress content unnecessarily before any read methods were called
- Ignore configured read limits for decompressed data

A malicious server could exploit this to trigger excessive resource consumption (high CPU usage and large memory allocations), constituting a decompression bomb attack.

#### Affected Versions

- urllib3 < 2.6.3

#### Resolution

Updated `urllib3` dependency to v2.6.3, which does not decode content of redirect responses when `preload_content=False`.

---

## Changes

### Dependencies

- **urllib3**: Updated from vulnerable version to ≥2.6.3

---

## Upgrade Instructions

```bash
# Update dependencies
pip install --upgrade urllib3~=2.6.3

# Or update via conda environment
conda activate JuniperPython
pip install --upgrade urllib3~=2.6.3

# Verify installation
python -c "import urllib3; print(urllib3.__version__)"
```

---

## Verification

After upgrading, verify the vulnerability is resolved:

```bash
# Check urllib3 version (should be 2.6.3 or higher)
pip show urllib3 | grep Version
```

---

## Related Links

- [Dependabot Alert #2](https://github.com/pcalnon/Juniper/security/dependabot/2)
- [urllib3 Security Advisory](https://github.com/urllib3/urllib3/security/advisories)
- [CWE-409: Improper Handling of Highly Compressed Data](https://cwe.mitre.org/data/definitions/409.html)
