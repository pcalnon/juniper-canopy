# Documentation Overview

## Complete Navigation Guide to Juniper Canopy Documentation

**Version:** 0.25.7  
**Last Updated:** September 5, 2026  
**Project:** Juniper Canopy - Real-Time CasCor Monitoring Frontend

---

## Table of Contents

- [Quick Navigation](#quick-navigation)
- [Getting Started](#getting-started)
- [Core Documentation](#core-documentation)
- [Technical Guides](#technical-guides)
- [Development Resources](#development-resources)
- [Historical Documentation](#historical-documentation)
- [Document Index](#document-index)
- [Documentation Standards](#documentation-standards)
- [Documentation Organization](#documentation-organization)
- [Documentation Authoring Standards](#documentation-authoring-standards)
- [Documentation Maintenance Workflow](#documentation-maintenance-workflow)
- [Documentation File Types](#documentation-file-types)
- [Documentation Update Triggers](#documentation-update-triggers)
- [Archive Procedures](#archive-procedures)
- [Documentation Update Workflow](#documentation-update-workflow)

---

## Quick Navigation

### I'm New Here - Where Do I Start?

```bash
1. README.md              → Project overview, what is this?
2. QUICK_START.md         → Get running in 5 minutes
3. ENVIRONMENT_SETUP.md   → Set up your environment
4. AGENTS.md              → Development conventions and guides
```

### I Want To

| Goal                         | Document                                                                  | Location       |
| ---------------------------- | ------------------------------------------------------------------------- | -------------- |
| **Get the app running**      | [QUICK_START.md](QUICK_START.md)                                          | docs/          |
| **Understand the project**   | [README.md](../README.md)                                                 | Root           |
| **Set up my environment**    | [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)                              | docs/          |
| **Run tests**                | [TESTING_QUICK_START.md](testing/TESTING_QUICK_START.md)                  | docs/testing/  |
| **Set up test environment**  | [TESTING_ENVIRONMENT_SETUP.md](testing/TESTING_ENVIRONMENT_SETUP.md)      | docs/testing/  |
| **Learn testing**            | [TESTING_MANUAL.md](testing/TESTING_MANUAL.md)                            | docs/testing/  |
| **View coverage reports**    | [TESTING_REPORTS_COVERAGE.md](testing/TESTING_REPORTS_COVERAGE.md)        | docs/testing/  |
| **Testing reference**        | [TESTING_REFERENCE.md](testing/TESTING_REFERENCE.md)                      | docs/testing/  |
| **Get CI/CD running**        | [CICD_QUICK_START.md](ci_cd/CICD_QUICK_START.md)                          | docs/ci_cd/    |
| **Set up CI/CD environment** | [CICD_ENVIRONMENT_SETUP.md](ci_cd/CICD_ENVIRONMENT_SETUP.md)              | docs/ci_cd/    |
| **Learn CI/CD workflow**     | [CICD_MANUAL.md](ci_cd/CICD_MANUAL.md)                                    | docs/ci_cd/    |
| **CI/CD reference**          | [CICD_REFERENCE.md](ci_cd/CICD_REFERENCE.md)                              | docs/ci_cd/    |
| **Review release-readiness findings** | [CODE_REVIEW_ANALYSIS_2026-04-04.md](../notes/history/CODE_REVIEW_ANALYSIS_2026-04-04.md) | notes/history/ |
| **Review remediation execution plan** | [CODE_REVIEW_PLAN_2026-04-04.md](../notes/history/CODE_REVIEW_PLAN_2026-04-04.md) | notes/history/ |
| **Find technical reference** | [REFERENCE.md](REFERENCE.md)                                              | docs/          |
| **See version history**      | [CHANGELOG.md](../CHANGELOG.md)                                           | Root           |
| **Quick-reference dev tasks** | [DEVELOPER_CHEATSHEET.md](DEVELOPER_CHEATSHEET.md)              | docs/         |
| **Read the cascor status cache (X7 1c)** | [AGENTS_REFERENCE.md — Cascor status cache](AGENTS_REFERENCE.md#cascor-status-cache-x7-slice-1c) | docs/ |
| **Contribute code**          | [AGENTS.md](../AGENTS.md)                                                 | Root           |

---

## Getting Started

### Essential Documents (Read First)

#### 1. [README.md](../README.md)

**Location:** Root directory  
**Purpose:** Project overview, features, quick start  
**Audience:** Everyone  
**Key Sections:**

- What is Juniper Canopy?
- Quick start (60 seconds)
- Key features
- Installation
- Usage
- Testing
- API reference

**When to Read:** First time visiting the project

---

#### 2. [QUICK_START.md](QUICK_START.md)

**Location:** docs/ directory  
**Purpose:** Get running in 5 minutes  
**Audience:** New users, developers  
**Key Sections:**

- Prerequisites checklist
- Step-by-step setup
- Demo mode launch
- Production mode setup
- First-time verification
- Common startup issues

**When to Read:** When you want to run the application immediately

---

#### 3. [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)

**Location:** docs/ directory  
**Purpose:** Complete environment configuration guide  
**Audience:** Developers setting up for the first time  
**Key Sections:**

- Conda environment setup
- Python dependencies
- Configuration files
- Environment variables
- Troubleshooting
- Verification steps

**When to Read:** Before starting development, when environment issues occur

---

#### 4. [AGENTS.md](../AGENTS.md)

**Location:** Root directory  
**Purpose:** AI agent development guide and conventions  
**Audience:** Developers, AI assistants  
**Key Sections:**

- Quick start commands
- Architecture overview
- Code style guidelines
- Thread safety patterns
- Testing requirements
- Common issues and solutions
- Definition of Done

**When to Read:** Before writing any code, when debugging issues

---

## Core Documentation

### Project Information

#### [CHANGELOG.md](../CHANGELOG.md)

**Location:** Root directory  
**Purpose:** Version history and release notes  
**Format:** Keep a Changelog standard  
**Audience:** All users  
**Key Sections:**

- Unreleased changes
- Version history (0.5.0, 0.4.0, 0.3.0, 0.2.1, 0.2.0, 0.1.4)
- Breaking changes
- Migration guides
- Testing procedures

**When to Read:**

- After updates/upgrades
- When investigating when a feature was added
- When troubleshooting regressions

**Update Frequency:** Every release, every significant change

---

### Architecture & Design

#### Project Structure

```bash
juniper_canopy/
├── README.md                      ← Start here
├── AGENTS.md                      ← Development guide
├── CHANGELOG.md                   ← Version history
├── conf/                          ← Configuration
│   ├── app_config.yaml
│   ├── requirements.txt
│   └── conda_environment.yaml
├── docs/                          ← Technical documentation
│   ├── DOCUMENTATION_OVERVIEW.md  ← You are here
│   ├── QUICK_START.md             ← Get running fast
│   ├── ENVIRONMENT_SETUP.md       ← Environment setup
│   ├── REFERENCE.md               ← Technical reference index
│   ├── ci_cd/                     ← CI/CD documentation (4 files)
│   │   ├── CICD_QUICK_START.md
│   │   ├── CICD_ENVIRONMENT_SETUP.md
│   │   ├── CICD_MANUAL.md
│   │   └── CICD_REFERENCE.md
│   ├── testing/                   ← Testing documentation
│   │   ├── TESTING_QUICK_START.md
│   │   ├── TESTING_ENVIRONMENT_SETUP.md
│   │   ├── TESTING_MANUAL.md
│   │   ├── TESTING_REFERENCE.md
│   │   └── TESTING_REPORTS_COVERAGE.md
│   ├── deployment/                ← Deployment guides
│   └── history/                   ← Historical docs
├── src/                           ← Source code
│   ├── main.py                    ← Entry point
│   ├── demo_mode.py
│   ├── config_manager.py
│   ├── backend/
│   ├── communication/
│   ├── frontend/
│   ├── logger/
│   └── tests/                     ← Test suite
├── util/                          ← Utility scripts
│   └── run_demo.bash
├── demo                           ← Demo mode launcher
└── try                            ← Production launcher
```

### Ecosystem Client Libraries

Juniper Canopy uses two client libraries to communicate with backend services:

| Library | PyPI | Purpose |
|---------|------|---------|
| [juniper-cascor-client](https://github.com/pcalnon/juniper-cascor-client) | `pip install juniper-cascor-client` | HTTP/WebSocket client for juniper-cascor (port 8200) |
| [juniper-data-client](https://github.com/pcalnon/juniper-data-client) | `pip install juniper-data-client` | HTTP client for juniper-data (port 8100) |

Both are available via the meta-package: `pip install juniper-ml[all]`

---

## Technical Guides

### CI/CD & Quality

> **Note:** CI/CD documentation consolidated on 2025-11-11. All CI/CD guides now in [docs/ci_cd/](ci_cd/).  
> Legacy files archived to [docs/history/](history/).

#### [docs/ci_cd/CICD_QUICK_START.md](ci_cd/CICD_QUICK_START.md)

**Lines:** ~400  
**Purpose:** Get CI/CD running in 5 minutes  
**Audience:** New developers  
**Key Sections:**

- Prerequisites
- Pre-commit installation
- Run tests locally
- GitHub secrets setup
- First commit
- View CI results

**When to Read:**

- First-time developer setup
- Need to get tests running quickly

---

#### [docs/ci_cd/CICD_ENVIRONMENT_SETUP.md](ci_cd/CICD_ENVIRONMENT_SETUP.md)

**Lines:** ~870  
**Purpose:** Complete CI/CD environment configuration  
**Audience:** DevOps, maintainers  
**Key Sections:**

- GitHub Actions configuration
- Environment variables and secrets
- Python matrix setup
- Dependencies and caching
- Workflow triggers
- Artifact management

**When to Read:**

- Setting up GitHub Actions for first time
- Modifying CI/CD environment
- Troubleshooting CI failures

---

#### [docs/ci_cd/CICD_MANUAL.md](ci_cd/CICD_MANUAL.md)

**Lines:** ~1,688  
**Purpose:** Comprehensive CI/CD usage guide  
**Audience:** All developers  
**Key Sections:**

- Complete pipeline overview
- Pre-commit hooks
- GitHub Actions workflow
- Testing stages
- Coverage reporting
- Troubleshooting

**When to Read:**

- Understanding full CI/CD pipeline
- Adding new workflow stages
- Debugging CI issues

---

#### [docs/ci_cd/CICD_REFERENCE.md](ci_cd/CICD_REFERENCE.md)

**Lines:** ~1,058  
**Purpose:** Technical CI/CD reference  
**Audience:** All developers  
**Key Sections:**

- Workflow file syntax
- Action configurations
- Environment variables
- Secret management
- Artifact handling
- Matrix testing

**When to Read:**

- Quick lookup of CI/CD configurations
- Modifying workflow files
- Adding new checks

---

### Testing Documentation

> **Note:** Testing documentation located in [docs/testing/](testing/).

#### [docs/testing/TESTING_QUICK_START.md](testing/TESTING_QUICK_START.md)

**Purpose:** Get testing in 5 minutes  
**Audience:** New developers  
**Key Sections:**

- Prerequisites
- Running tests
- Basic test commands
- Quick troubleshooting

---

#### [docs/testing/TESTING_ENVIRONMENT_SETUP.md](testing/TESTING_ENVIRONMENT_SETUP.md)

**Purpose:** Complete test environment configuration  
**Audience:** Developers  
**Key Sections:**

- Test environment setup
- Dependencies
- Configuration
- Environment variables

---

#### [docs/testing/TESTING_MANUAL.md](testing/TESTING_MANUAL.md)

**Purpose:** Comprehensive testing guide  
**Audience:** All developers  
**Key Sections:**

- Test organization
- Writing tests
- Running tests
- Coverage requirements
- Best practices

---

#### [docs/testing/TESTING_REFERENCE.md](testing/TESTING_REFERENCE.md)

**Purpose:** Technical testing reference  
**Audience:** Developers  
**Key Sections:**

- Pytest configuration
- Fixtures
- Markers
- Command reference

---

#### [docs/testing/TESTING_REPORTS_COVERAGE.md](testing/TESTING_REPORTS_COVERAGE.md)

**Purpose:** Coverage analysis and reports  
**Audience:** Developers  
**Key Sections:**

- Coverage metrics
- Report generation
- Coverage requirements
- Analysis

---

## Development Resources

### Configuration

| File                      | Purpose                       | Location |
| ------------------------- | ----------------------------- | -------- |
| `conf/app_config.yaml`    | Application configuration     | conf/    |
| `conf/requirements.txt`   | Python dependencies           | conf/    |
| `pyproject.toml`          | Python project configuration  | Root     |
| `.pre-commit-config.yaml` | Pre-commit hook configuration | Root     |

---

## Historical Documentation

### docs/history/ Directory

Contains archived documentation that has been superseded or consolidated.

**Location:** [docs/history/](history/)

**Purpose:** Historical reference for:

- Archived design documents
- Superseded guides
- Legacy implementation notes

---

## Document Index

### Root Directory

| File                       | Lines  | Type      | Audience       | Status        |
| -------------------------- | ------ | --------- | -------------- | ------------- |
| **README.md**              | ~200   | Overview  | All            | ✅ **Active** |
| **AGENTS.md**              | ~1,800 | Reference | Developers, AI | ✅ **Active** |
| **CHANGELOG.md**           | ~400   | History   | All            | ✅ **Active** |

### docs/ Directory

| File                                     | Lines  | Type      | Audience       | Status        |
| ---------------------------------------- | ------ | --------- | -------------- | ------------- |
| **DOCUMENTATION_OVERVIEW.md**            | ~800   | Overview  | All            | ✅ **Active** |
| **QUICK_START.md**                       | ~400   | Tutorial  | New users      | ✅ **Active** |
| **ENVIRONMENT_SETUP.md**                 | ~600   | Guide     | Developers     | ✅ **Active** |
| **REFERENCE.md**                         | ~190   | Reference | All            | ✅ **Active** |
| **ci_cd/CICD_QUICK_START.md**            | ~400   | Tutorial  | Developers     | ✅ **Active** |
| **ci_cd/CICD_ENVIRONMENT_SETUP.md**      | ~870   | Guide     | DevOps         | ✅ **Active** |
| **ci_cd/CICD_MANUAL.md**                 | ~1,688 | Guide     | Developers     | ✅ **Active** |
| **ci_cd/CICD_REFERENCE.md**              | ~1,058 | Reference | All            | ✅ **Active** |
| **testing/TESTING_QUICK_START.md**       | ~180   | Tutorial  | Developers     | ✅ **Active** |
| **testing/TESTING_ENVIRONMENT_SETUP.md** | ~550   | Guide     | Developers     | ✅ **Active** |
| **testing/TESTING_MANUAL.md**            | ~900   | Guide     | Developers     | ✅ **Active** |
| **testing/TESTING_REFERENCE.md**         | ~1,200 | Reference | Developers     | ✅ **Active** |
| **testing/TESTING_REPORTS_COVERAGE.md**  | ~900   | Guide     | Developers     | ✅ **Active** |

### notes/ Directory

| File                                     | Lines  | Type       | Audience       | Status        |
| ---------------------------------------- | ------ | ---------- | -------------- | ------------- |
| **DEVELOPER_CHEATSHEET.md**              | ~100   | Cheatsheet | Developers     | ✅ **Active** |
| **CODE_REVIEW_ANALYSIS_2026-04-04.md**   | ~1,400 | Analysis   | Maintainers    | ✅ **Active** |
| **CODE_REVIEW_PLAN_2026-04-04.md**       | ~320   | Plan       | Maintainers    | ✅ **Active** |

### docs/history/ Directory, Document Index

Contains archived documentation - see [Historical Documentation](#historical-documentation) section

---

## Documentation Standards

### File Naming Conventions

**Active Documentation:**

- Use clear, descriptive names: `QUICK_START.md`, `ENVIRONMENT_SETUP.md`
- All caps for major guides: `README.md`, `CHANGELOG.md`, `AGENTS.md`

**Historical Documentation:**

- Include dates for time-sensitive docs: `FINAL_STATUS_2025-11-03.md`
- Use descriptive names indicating purpose: `REGRESSION_FIX_REPORT.md`

---

### Markdown Formatting

**Required Elements:**

- Title (# heading)
- Table of contents (for docs >200 lines)
- Clear section headings (##, ###)
- Code blocks with language specification
- Links to related documents
- Last updated date
- Author/version information

**Example:**

```markdown
# Document Title

**Version:** 0.4.0  
**Last Updated:** November 7, 2025  
**Author:** Paul Calnon

## Table of Contents

- [Section 1](#section-1)
- [Section 2](#section-2)

## Section 1

Content...

## Section 2

Content...
```

---

### Cross-Referencing

**Internal Links:**

- Use relative paths: `[AGENTS.md](../AGENTS.md)`, `[CICD_MANUAL.md](ci_cd/CICD_MANUAL.md)`
- Include section anchors: `[Testing](#testing)`, `[Quick Start](../README.md#quick-start)`

**External Links:**

- Use descriptive text: `[FastAPI Documentation](https://fastapi.tiangolo.com/)`

---

### Update Requirements

**On Every Change:**

1. **CHANGELOG.md** - Summarize changes and impact
2. **README.md** - Update if run/test instructions change
3. **Relevant technical docs** - Update affected guides

**Version Bumps:**

- Update version numbers in README.md, CHANGELOG.md
- Add release notes to CHANGELOG.md
- Update "Last Updated" dates

---

## Documentation Gaps & Future Work

### Missing Documentation (To Be Created)

1. **ARCHITECTURE.md** - Complete system architecture with diagrams
2. **API_REFERENCE.md** - Complete API endpoint specifications
3. **TROUBLESHOOTING.md** - Common issues and solutions extracted from AGENTS.md
4. **CONTRIBUTING.md** - Contribution guidelines
5. **SECURITY.md** - Security policies and reporting

---

## Finding Information

### Search Strategies

**By Topic:**

1. Check this overview's "I Want To..." table
2. Search AGENTS.md for development topics
3. Search docs/ for technical guides
4. Search docs/history/ for historical context

**By Keyword:**

```bash
# Search all markdown files
grep -r "keyword" *.md docs/*.md

# Search with context
grep -r -C 3 "keyword" *.md docs/*.md

# Search specific directory
grep -r "keyword" docs/history/
```

**By Recent Changes:**

1. Check CHANGELOG.md for version history
2. Review git log for recent commits
3. Check "Recent Changes" section in AGENTS.md

---

## Quick Reference Card

### Essential Commands

```bash
# Get running
./demo

# Run tests
cd src && pytest tests/ -v

# Run with coverage
cd src && pytest tests/ --cov=. --cov-report=html

# Pre-commit checks
pre-commit run --all-files

# Format code
black src/ && isort src/

# Check syntax
python -m py_compile src/**/*.py
```

### Essential Files

```bash
# Start here
README.md              # What is this?
docs/QUICK_START.md    # Get running now
docs/ENVIRONMENT_SETUP.md  # Set up environment

# Development
AGENTS.md              # Development guide
docs/ci_cd/CICD_MANUAL.md  # Testing & CI/CD

# Reference
CHANGELOG.md           # Version history
```

---

## Documentation Organization

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

The project documentation follows a structured organization with clear separation between current and historical content:

### Root Directory Documentation

High-level documentation in the project root for quick access:

- **README.md** - Project overview, quick start, features
- **CHANGELOG.md** - Chronological change history with impact analysis
- **AGENTS.md** - This file - comprehensive developer guide
- **CLAUDE.md** - Symlink to AGENTS.md (Claude Code integration)
- **LICENSE** - MIT License

### docs/ Directory Documentation

Reference and subsystem documentation:

- **docs/QUICK_START.md** - 5-minute setup guide (get running ASAP)
- **docs/ENVIRONMENT_SETUP.md** - Complete environment configuration
- **docs/DOCUMENTATION_OVERVIEW.md** - Navigation guide to all documentation
- **docs/DEVELOPER_CHEATSHEET.md** - Quick reference for developers
- **docs/REFERENCE.md** - Technical reference
- **docs/USER_MANUAL.md** - End-user documentation

### Integration-Specific Documentation

Integration guides with consistent naming pattern:

- **[INTEGRATION]_QUICK_START.md** - 5-minute integration setup
- **[INTEGRATION]_MANUAL.md** - Comprehensive usage guide
- **[INTEGRATION]_REFERENCE.md** - Technical API/configuration reference

Current integrations:

- **REDIS_*** - Redis integration documentation
- **CASSANDRA_*** - Cassandra integration documentation
- **CASCOR_BACKEND_*** - CasCor backend integration documentation

### Testing Documentation

Comprehensive testing documentation suite:

- **TESTING_QUICK_START.md** - Get testing in 5 minutes
- **TESTING_MANUAL.md** - Complete testing guide
- **TESTING_REFERENCE.md** - Technical testing reference
- **TESTING_ENVIRONMENT_SETUP.md** - Test environment configuration
- **TESTING_REPORTS_COVERAGE.md** - Coverage analysis and reports

### docs/ Subdirectories

Technical deep-dive documentation organized by topic:

- **docs/api/** - API schema and reference documentation
- **docs/cascor/** - CasCor backend integration (manual, quick start, reference, constants guide)
- **docs/cassandra/** - Cassandra integration documentation
- **docs/ci_cd/** - CI/CD pipeline documentation (manual, quick start, reference, environment setup)
- **docs/demo/** - Demo mode documentation (manual, quick start, reference, environment setup)
- **docs/deployment/** - Kubernetes deployment plan
- **docs/history/** - Archived/superseded documentation
- **docs/redis/** - Redis integration documentation
- **docs/testing/** - Testing guides, analysis reports, selective test enablement

### docs/history/ Archive

Historical documentation with timestamp-based naming:

- **docs/history/FILENAME_YYYY-MM-DD.ext** - Archived versions
- **notes/history/INDEX.md** - Archive index with descriptions

Examples:

- `docs/history/TESTING_GUIDE_CONSOLIDATED_2025-11-04.md` - Superseded by split testing docs
- `docs/history/BACKEND_INTEGRATION_2025-11-04.md` - Obsolete integration docs

### notes/ Subdirectory

Development notes and technical details:

- **notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md** - Feature roadmap and status
- **notes/FINAL_STATUS_*.md** - Major milestone summaries
- **notes/IMPLEMENTATION_*.md** - Implementation details
- **notes/FIX_*.md** - Bug fix reports
- **notes/CI_CD_*.md** - CI/CD implementation notes

---

## Documentation Authoring Standards

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### Markdown Formatting Standards

#### Headers

- Use ATX-style headers (`#`, `##`, `###`)
- One H1 (`#`) per document (document title)
- Logical hierarchy without skipping levels
- Space after hash marks

✓ # Document Title
✓ ## Section
✓ ### Subsection

✗ #Document Title (no space)
✗ ## Section
    #### Subsection (skipped H3)

#### Code Blocks

- Use fenced code blocks with language specification
- Include comments for clarity
- Show both correct and incorrect examples where helpful

````bash
✓ ```python
  def example():
      """Proper code block."""
      pass
  ```

✓ ```bash
  # Show command with context
  pytest tests/ -v
  ```

✗ ```
  code without language
  ```
````

#### Lists

- Use `-` for unordered lists
- Use `1.` for ordered lists (auto-numbering)
- Indent nested lists with 3 spaces
- Blank line before/after lists

```bash
✓ - Item one
  - Nested item
  - Another nested
- Item two

✓ 1. First step
2. Second step
   - Sub-point
3. Third step

✗ * Mixed bullets
- Are confusing
```

#### Tables

- Use pipe tables with alignment
- Include header separator
- Align columns for readability

```bash
✓ | File Type     | Location                                    | Examples                            |
  | ------------- | ------------------------------------------- | ----------------------------------- |
  | Source    | `src/`   | `main.py` |

✗  |File|Loc|Ex|
|-|-|-|
|S-c|s-c|m-n|
||||
```

### Internal Linking Conventions

#### File Links

Use relative paths with descriptive link text:

✓ [Quick Start Guide](../docs/QUICK_START.md)
✓ [Testing Manual](../docs/testing/TESTING_MANUAL.md)
✓ [CI/CD Manual](../docs/ci_cd/CICD_MANUAL.md)
✓ [CI/CD Quick Start](../docs/ci_cd/CICD_QUICK_START.md)
✓ [Archive Index](../notes/history/INDEX.md)

✗ `[Example Link](.././docs/../TESTING_MANUAL.md)`
✗ See TESTING_MANUAL.md

#### Section Links

Link to specific sections with anchors:

```bash
✓ [Installation](../AGENTS.md#installation)
✓ [Testing Guidelines](../AGENTS.md#testing-guidelines)
✓ [API Endpoints](../AGENTS.md#rest-api-endpoints)
# Anchors are auto-generated from headers:
```

##### Section Links: Examples

```markdown
## Testing Guidelines → #testing-guidelines

## REST API Endpoints → #rest-api-endpoints
```

#### Code File Links

Link to source code with file references:

```bash
✓ [main.py](../src/main.py)
✓ [demo_mode.py](../src/demo_mode.py)
✓ [WebSocket Manager](../src/communication/websocket_manager.py)

# With line numbers (if viewer supports):
✓ [WebSocket broadcast](../src/communication/websocket_manager.py#L45-L67)
```

### Code Example Formatting

#### Command Examples

Show commands with context and expected output:

```bash
# Run all tests with coverage
cd src
pytest tests/ --cov=. --cov-report=html

# Expected output:
# ===== 170 passed in 12.34s =====
# Coverage HTML report: ../reports/coverage/index.html
```

#### Python Examples

Include docstrings and type hints:

```python
def thread_safe_update(self, value: Any) -> None:
    """Thread-safe state update.

    Args:
        value: New state value
    """
    with self._lock:
        self.state = value
```

#### Configuration Examples

Show complete, working configurations:

```yaml
# conf/app_config.yaml
server:
  host: "127.0.0.1"
  port: 8050
  debug: false
```

### Tables of Contents Requirements

All manuals and reference docs must include a table of contents:

#### Document Table of Contents

```markdown
- [Installation](../AGENTS.md#installation)
- [Configuration](../AGENTS.md#configuration)
- [Usage](../AGENTS.md#usage)
  - [Basic Usage](../AGENTS.md#basic-usage)
  - [Advanced Usage](../AGENTS.md#advanced-usage)
- [Troubleshooting](../AGENTS.md#troubleshooting)
- [Reference](../AGENTS.md#reference)
```

**TOC Requirements:**

- Place after document metadata (version, date)
- Include all H2 headers at minimum
- Include H3 headers for complex sections
- Use consistent anchor formatting
- Update when structure changes

##### [Feature] Installation Link

Include Link to Installation Section of the Document

##### [Feature] Configuration Link

Include Link to Configuration Section of the Document

##### [Feature] Usage Link

Include Link to Usage Section of the Document

###### [Feature] Basic Usage Link

Include Link to Basic Usage Section of the Document

###### [Feature] Advanced Usage Link

Include Link to Advanced Usage Section of the Document

##### [Feature] Troubleshooting Link

Include Link to Troubleshooting Section of the Document

##### [Feature] Reference Link

Include Link to Reference Section of the Document

### Document Metadata

All documentation should include metadata:

#### Document Title Status, Version, and Last-Updated Stamps

**Last Updated:** 2025-11-05  
**Version:** 1.0.0  
**Status:** Current | Archived | Draft

**Update rules:**

- `Last Updated`: Date of last significant change
- `Version`: Semantic versioning (major.minor.patch)
- `Status`: Current (active), Archived (historical), Draft (in progress)

**Version incrementing:**

- **Major** (1.0.0 → 2.0.0): Breaking changes, complete rewrites
- **Minor** (1.0.0 → 1.1.0): New sections, significant additions
- **Patch** (1.0.0 → 1.0.1): Corrections, clarifications, minor updates

---

## Documentation Maintenance Workflow

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### When to Update Documentation

Update documentation systematically based on the type of change:

#### On Feature Addition

1. **Update [INTEGRATION]_MANUAL.md** - Add feature usage instructions
2. **Update [INTEGRATION]_REFERENCE.md** - Add API/configuration details
3. **Update CHANGELOG.md** - Add entry under "Added" section
4. **Update README.md** - If feature changes core capabilities
5. **Update notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md** - Mark feature complete
6. **Add to Recent Changes** - Link implementation notes in AGENTS.md

#### On Bug Fix

1. **Update CHANGELOG.md** - Add entry under "Fixed" section
2. **Update troubleshooting sections** - In relevant manuals
3. **Update notes/** - Create fix report (e.g., `FIX_[ISSUE]_[DATE].md`)
4. **Update TESTING_*.md** - If test coverage added
5. **Add to Recent Changes** - Link fix details in AGENTS.md

#### On Breaking Change

1. **Update CHANGELOG.md** - Prominent entry under "Changed" with migration guide
2. **Update QUICK_START.md** - Reflect new setup/usage
3. **Update all affected manuals** - Update instructions
4. **Update all affected references** - Update API/config docs
5. **Update notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md** - Document migration path
6. **Create migration guide** - In docs/ if complex

#### On Test Addition

1. **Update TESTING_MANUAL.md** - Document new test types/approaches
2. **Update TESTING_REFERENCE.md** - Add test command variations
3. **Update TESTING_REPORTS_COVERAGE.md** - Update coverage metrics
4. **Update CHANGELOG.md** - If significant coverage improvement

#### On Deployment/Infrastructure Change

1. **Update docs/ci_cd/CICD_MANUAL.md** - Update pipeline documentation
2. **Update ENVIRONMENT_SETUP.md** - Update setup instructions
3. **Update DEPLOYMENT_GUIDE.md** - Update deployment steps (when created)
4. **Update CHANGELOG.md** - Document infrastructure changes

### Versioning and Archival Procedures

#### When to Archive Documentation

Archive documentation when:

1. **Major version changes** - Archive old version-specific docs
2. **Documentation consolidation** - Archive superseded individual files
3. **Documentation reorganization** - Archive old structure
4. **Documentation splits** - Archive consolidated docs when splitting

#### Archive Process

1. **Create timestamp-based filename:**

   ```bash
   FILENAME_YYYY-MM-DD.ext
   # Example: TESTING_GUIDE_CONSOLIDATED_2025-11-04.md
   ```

2. **Move to docs/history/:**

   ```bash
   mv FILENAME.md docs/history/FILENAME_YYYY-MM-DD.md
   ```

3. **Update notes/history/INDEX.md:**

   ```markdown
   ## YYYY-MM-DD: Archive Description

   - **[FILENAME](FILENAME_YYYY-MM-DD.md)** - Reason for archival, replacement docs
   ```

4. **Add redirect notice to new docs:**

   ```markdown
   > **Note:** This document replaces [Old Doc](../docs/history/OLD_DOC_2025-11-04.md) archived on 2025-11-04.
   ```

5. **Update navigation links** - Ensure all cross-references point to current docs

#### Archive Examples

```bash
# Consolidation → split
docs/history/TESTING_GUIDE_CONSOLIDATED_2025-11-04.md
# Replaced by: TESTING_QUICK_START.md, TESTING_MANUAL.md, TESTING_REFERENCE.md

# Superseded integration guide
docs/history/BACKEND_INTEGRATION_2025-11-04.md
# Replaced by: CASCOR_BACKEND_QUICK_START.md, CASCOR_BACKEND_MANUAL.md
```

### Cross-Referencing Requirements

Maintain consistent cross-references across documentation:

#### Internal Links

Use relative markdown links with descriptive text:

✓ See [Testing Quick Start](../docs/testing/TESTING_QUICK_START.md) for setup
✓ Refer to [API Reference](../docs/api/API_REFERENCE.md) for details
✓ Check [Archive Index](../notes/history/INDEX.md) for older versions

✗ See docs/API_REFERENCE.md
✗ Click here: docs/testing.md

#### Code References

Link to specific files and line numbers:

✓ Implementation in [src/demo_mode.py](../src/demo_mode.py)
✓ See [WebSocket Manager](../src/communication/websocket_manager.py#L45-L67)
✓ Configuration in [conf/app_config.yaml](../conf/app_config.yaml)

✗ See the demo mode file
✗ Check websocket manager

#### External Resources

Use descriptive link text with URLs:

✓ See [FastAPI Documentation](https://fastapi.tiangolo.com/)
✓ Refer to [WebSocket RFC 6455](https://tools.ietf.org/html/rfc6455)

✗ <https://fastapi.tiangolo.com/>
✗ See link: <https://example.com>

### Documentation Review Checklist

Before committing documentation changes:

- [ ] All internal links tested and working
- [ ] Code examples tested and accurate
- [ ] Version/last-updated stamps current
- [ ] Cross-references updated (if structure changed)
- [ ] Table of contents reflects all sections
- [ ] Markdown formatting validated
- [ ] No broken links to archived content
- [ ] CHANGELOG.md updated
- [ ] Archive INDEX.md updated (if archival)
- [ ] Navigation consistency maintained

---

## Documentation File Types

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### Quick Start Guides

**Purpose:** Get users running in 5 minutes or less

**Format:**

#### [Feature] Quick Start

**Last Updated:** YYYY-MM-DD
**Time to Complete:** ~5 minutes

##### Prerequisites

- Minimal requirements only

##### Installation

1. Step one
2. Step two
3. Step three

##### Verify Installation

```bash
# Quick verification command
```

##### Next Steps

```markdown
- [Full Manual](FEATURE_MANUAL.md)
- [Reference](FEATURE_REFERENCE.md)
```

**Characteristics:**

- Ultra-concise (< 200 lines)
- Numbered steps only
- No theory or background
- Single "happy path" workflow
- Links to comprehensive docs

**Examples:** QUICK_START.md, TESTING_QUICK_START.md, REDIS_QUICK_START.md

### Environment Setup Guides

**Purpose:** Complete environment configuration from scratch

**Format:**

#### [Feature] Environment Setup

**Last Updated:** YYYY-MM-DD

##### Table of Contents, Environment Setup

```markdown
- [System Requirements](../AGENTS.md#system-requirements)
- [Conda Environment](../AGENTS.md#conda-environment)
- [Dependencies](../AGENTS.md#dependencies)
- [Configuration](../AGENTS.md#configuration)
- [Verification](../AGENTS.md#verification)
- [Troubleshooting](../AGENTS.md#troubleshooting)
```

##### System Requirements, Environment Setup

- Operating system
- Python version
- System dependencies

##### Conda Environment, Environment Setup

Step-by-step environment setup...

##### Dependencies, Environment Setup

Dependencies required for feature...

##### Configuration, Environment Setup

Environment variables, config files...

##### Verification, Environment Setup

How to verify setup is correct...

##### Troubleshooting, Environment Setup

Common issues and solutions...

**Characteristics:**

- Comprehensive and detailed
- Platform-specific instructions
- Configuration examples
- Troubleshooting section
- Verification procedures

**Examples:** ENVIRONMENT_SETUP.md, TESTING_ENVIRONMENT_SETUP.md

### User Manuals

**Purpose:** Comprehensive feature usage guide

**Format:**

#### [Feature] User Manual

**Last Updated:** YYYY-MM-DD
**Version:** X.Y.Z

##### Table of Contents, User Manual

```markdown
- [Overview](../AGENTS.md#overview)
- [Getting Started](../AGENTS.md#getting-started)
- [Basic Usage](../AGENTS.md#basic-usage)
- [Advanced Usage](../AGENTS.md#advanced-usage)
- [Best Practices](../AGENTS.md#best-practices)
- [Troubleshooting](../AGENTS.md#troubleshooting)
- [Examples](../AGENTS.md#examples)
- [Reference](../AGENTS.md#reference)
```

##### Overview: User Manual

What the feature does, why use it...

##### Getting Started: User Manual

Prerequisites, quick setup...

##### Basic Usage: User Manual

Common workflows with examples...

##### Advanced Usage: User Manual

Complex scenarios, customization...

##### Best Practices: User Manual

Recommendations, patterns to follow...

##### Troubleshooting: User Manual

Common issues, solutions, debugging...

##### Examples: User Manual

Real-world usage examples...

##### Reference: User Manual

Links to technical reference...

**Characteristics:**

- Task-oriented organization
- Progressive complexity (basic → advanced)
- Extensive examples
- Best practices section
- Troubleshooting guide
- Reference links

**Examples:** TESTING_MANUAL.md, REDIS_MANUAL.md, CASSANDRA_MANUAL.md

### Reference Documentation

**Purpose:** Technical API, configuration, and command reference

**Format:**

#### [Feature] Reference

**Last Updated:** YYYY-MM-DD
**Version:** X.Y.Z

##### Table of Contents: Reference

```markdown
- [API Reference](../AGENTS.md#api-reference)
- [Configuration](../AGENTS.md#configuration)
- [Commands](../AGENTS.md#commands)
- [Error Codes](../AGENTS.md#error-codes)
```

##### API Reference: Reference

###### Function/Class Name

**Signature:**

```python
def function_name(param1: Type, param2: Type) -> ReturnType:
    """Brief description of function purpose."""
```

**Parameters:**

- `param1` (Type): Description
- `param2` (Type): Description

**Returns:**

- ReturnType: Description

**Raises:**

- Exception: When it occurs

**Example:**

```python
result = function_name(value1, value2)
```

##### Configuration: Reference

###### config_key

- **Type:** string | integer | boolean
- **Default:** `default_value`
- **Description:** What it configures
- **Example:** `config_key: value`

**Characteristics:**

- Alphabetical organization
- Complete parameter lists
- Type specifications
- Default values
- Example usage for each item
- Error code catalog

**Examples:** TESTING_REFERENCE.md, REDIS_REFERENCE.md, CASSANDRA_REFERENCE.md

### Integration Guides

**Purpose:** Third-party service integration documentation

**Naming Pattern:**

- `[SERVICE]_QUICK_START.md` - 5-minute setup
- `[SERVICE]_MANUAL.md` - Comprehensive guide
- `[SERVICE]_REFERENCE.md` - Technical reference

**Format:** Follows Quick Start, Manual, and Reference patterns above

**Additional Sections:**

- **Architecture**: How integration works
- **Configuration**: Service-specific settings
- **Authentication**: Credentials, security
- **Data Flow**: Request/response patterns
- **Monitoring**: Health checks, metrics
- **Troubleshooting**: Service-specific issues

**Examples:**

- Redis: REDIS_QUICK_START.md, REDIS_MANUAL.md, REDIS_REFERENCE.md
- Cassandra: CASSANDRA_QUICK_START.md, CASSANDRA_MANUAL.md, CASSANDRA_REFERENCE.md
- CasCor Backend: CASCOR_BACKEND_QUICK_START.md, CASCOR_BACKEND_MANUAL.md, CASCOR_BACKEND_REFERENCE.md

### Security Release Notes

**Purpose:** Document security patch releases addressing vulnerabilities in dependencies or application code.

**Template:** [notes/templates/TEMPLATE_SECURITY_RELEASE_NOTES.md](../notes/templates/TEMPLATE_SECURITY_RELEASE_NOTES.md)

**Required Structure:**

1. **Title**: `JuniperCanopy v<VERSION> – SECURITY PATCH RELEASE`
2. **Summary paragraph**: Brief description of vulnerability and upgrade recommendation
3. **Security Impact table**: Vulnerable package, vulnerability class, attack vector, upstream fix
4. **Detailed vulnerability description**: How the vulnerability works and affects JuniperCanopy
5. **Affected Versions section**: Which versions are vulnerable and under what conditions
6. **Remediation / Upgrade Instructions**: Step-by-step upgrade guide with Git and pip commands
7. **Temporary Mitigation**: Workarounds if immediate upgrade is not possible
8. **Changes section**: List of security and documentation changes
9. **Testing & Quality table**: Test pass/skip counts, runtime, coverage
10. **Upgrade Recommendation**: Risk-specific guidance
11. **References**: Links to Dependabot alert, CVE/CWE, previous release notes, CHANGELOG

**Naming Convention:** `RELEASE_NOTES_v<VERSION>.md`

**Examples:**

- [RELEASE_NOTES_v0.14.1-alpha.md](../notes/releases/RELEASE_NOTES_v0.14.1-alpha.md) - filelock TOCTOU vulnerability
- [RELEASE_NOTES_v0.15.1-alpha.md](../notes/releases/RELEASE_NOTES_v0.15.1-alpha.md) - urllib3 decompression bomb vulnerability

---

## Documentation Update Triggers

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

Clear rules for when to update each documentation type:

### On Feature Addition, Update Docs

**Must Update:**

- [ ] **[FEATURE]_MANUAL.md** - Add usage instructions in relevant section
- [ ] **[FEATURE]_REFERENCE.md** - Add API/configuration documentation
- [ ] **CHANGELOG.md** - Add entry under `## [Unreleased] ### Added`
- [ ] **notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md** - Mark feature complete, update status

**May Update:**

- [ ] **README.md** - If feature changes core project capabilities
- [ ] **QUICK_START.md** - If feature affects initial setup
- [ ] **AGENTS.md Recent Changes** - Link to implementation notes

**Create:**

- [ ] **notes/IMPLEMENTATION_[FEATURE]_[DATE].md** - Implementation details

### On Bug Fix, Update Docs

**Must Update:**

- [ ] **CHANGELOG.md** - Add entry under `## [Unreleased] ### Fixed`
- [ ] **Troubleshooting sections** - In affected manuals

**May Update:**

- [ ] **TESTING_MANUAL.md** - If regression tests added
- [ ] **TESTING_REPORTS_COVERAGE.md** - If coverage changed
- [ ] **AGENTS.md Recent Changes** - Link to fix report

**Create:**

- [ ] **notes/FIX_[ISSUE]_[DATE].md** - Bug fix details and analysis

### On Breaking Change, Update Docs

**Must Update:**

- [ ] **CHANGELOG.md** - Prominent entry under `## [Unreleased] ### Changed` with migration guide
- [ ] **All affected QUICK_START.md files** - Update setup instructions
- [ ] **All affected MANUAL.md files** - Update usage instructions
- [ ] **All affected REFERENCE.md files** - Update API/config documentation
- [ ] **notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md** - Document migration path

**Create:**

- [ ] **docs/MIGRATION_[VERSION].md** - Migration guide (if complex)
- [ ] **notes/BREAKING_CHANGE_[FEATURE]_[DATE].md** - Impact analysis

### On Test Addition, Update Docs

**Must Update:**

- [ ] **TESTING_MANUAL.md** - Document new test types/approaches
- [ ] **TESTING_REFERENCE.md** - Add test command variations
- [ ] **TESTING_REPORTS_COVERAGE.md** - Update coverage metrics

**May Update:**

- [ ] **CHANGELOG.md** - If significant coverage improvement
- [ ] **README.md** - If testing approach changed

### On Deployment/Infrastructure Change, Update Docs

**Must Update:**

- [ ] **docs/ci_cd/CICD_MANUAL.md** - Update pipeline documentation
- [ ] **ENVIRONMENT_SETUP.md** - Update setup instructions
- [ ] **CHANGELOG.md** - Document infrastructure changes

**May Update:**

- [ ] **QUICK_START.md** - If deployment process changed
- [ ] **README.md** - If deployment approach changed

**Create:**

- [ ] **docs/DEPLOYMENT_GUIDE.md** - If not exists
- [ ] **notes/CI_CD_[CHANGE]_[DATE].md** - CI/CD change details

### On Documentation Reorganization, Update Docs

**Must Update:**

- [ ] **notes/history/INDEX.md** - Document archived files
- [ ] **DOCUMENTATION_OVERVIEW.md** - Update navigation
- [ ] **All internal cross-references** - Point to new locations
- [ ] **CHANGELOG.md** - Document reorganization under `Changed`

**Create:**

- [ ] **Archive files** - Move old docs to `docs/history/FILENAME_YYYY-MM-DD.ext`
- [ ] **Redirect notices** - In new docs pointing to archived versions

---

## Archive Procedures

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

### When to Archive

Archive documentation in these scenarios:

#### 1. Major Version Changes

When project reaches new major version (e.g., 1.x → 2.x):

```bash
# Archive version-specific docs
mv API_REFERENCE.md docs/history/API_REFERENCE_v1_2025-11-05.md
mv DEPLOYMENT_GUIDE.md docs/history/DEPLOYMENT_GUIDE_v1_2025-11-05.md
```

#### 2. Documentation Consolidation

When merging multiple docs into one:

```bash
# Before consolidation - multiple files
REDIS_SETUP.md
REDIS_USAGE.md
REDIS_API.md

# Archive old files
mv REDIS_SETUP.md docs/history/REDIS_SETUP_2025-11-05.md
mv REDIS_USAGE.md docs/history/REDIS_USAGE_2025-11-05.md
mv REDIS_API.md docs/history/REDIS_API_2025-11-05.md

# Create consolidated
REDIS_MANUAL.md  # Contains all content
```

#### 3. Documentation Splits

When splitting one doc into multiple (inverse of consolidation):

```bash
# Before split - single file
TESTING_GUIDE_CONSOLIDATED.md

# Archive consolidated version
mv TESTING_GUIDE_CONSOLIDATED.md docs/history/TESTING_GUIDE_CONSOLIDATED_2025-11-04.md

# Create split files
TESTING_QUICK_START.md
TESTING_MANUAL.md
TESTING_REFERENCE.md
TESTING_ENVIRONMENT_SETUP.md
TESTING_REPORTS_COVERAGE.md
```

#### 4. Obsolete Documentation

When docs no longer apply to current system:

```bash
# Archive obsolete integration guide
mv BACKEND_INTEGRATION.md docs/history/BACKEND_INTEGRATION_2025-11-04.md

# Replaced by specific integration docs
CASCOR_BACKEND_MANUAL.md
```

### Archive Timestamp Format

Use ISO 8601 date format (YYYY-MM-DD):

```bash
# Correct formats
FILENAME_2025-11-04.md
FILENAME_v1.2_2025-11-04.md
FILENAME_CONSOLIDATED_2025-11-04.md

# Incorrect formats (don't use)
FILENAME_11-04-2025.md      # Wrong date order
FILENAME_2025-Nov-04.md     # Month abbreviation
FILENAME_20251104.md        # No separators
FILENAME_old.md             # No date
```

### Archive Process Steps

**1. Create Timestamped Filename:**

```bash
# Format: BASENAME_YYYY-MM-DD.ext
ORIGINAL="TESTING_GUIDE_CONSOLIDATED.md"
DATE=$(date +%Y-%m-%d)
ARCHIVED="TESTING_GUIDE_CONSOLIDATED_${DATE}.md"
```

**2. Move to Archive:**

```bash
# Ensure docs/history/ exists
mkdir -p docs/history/

# Move file
mv "$ORIGINAL" "docs/history/$ARCHIVED"
```

**3. Update Archive Index:**

Add entry to `notes/history/INDEX.md`:

```markdown
## 2025-11-04: Testing Documentation Split

**Archived Files:**

- **[TESTING_GUIDE_CONSOLIDATED_2025-11-04.md](TESTING_GUIDE_CONSOLIDATED_2025-11-04.md)**
  - Reason: Split into focused documents for better navigation
  - Replaced by:
    - [TESTING_QUICK_START.md](../TESTING_QUICK_START.md) - 5-minute setup
    - [TESTING_MANUAL.md](../TESTING_MANUAL.md) - Comprehensive guide
    - [TESTING_REFERENCE.md](../TESTING_REFERENCE.md) - Technical reference
    - [TESTING_ENVIRONMENT_SETUP.md](../TESTING_ENVIRONMENT_SETUP.md) - Environment config
    - [TESTING_REPORTS_COVERAGE.md](../TESTING_REPORTS_COVERAGE.md) - Coverage reports
  - Content: Comprehensive testing guide with all sections consolidated
```

**4. Add Redirect Notice:**

In replacement documentation, add note at top:

```markdown
# Testing Quick Start

**Last Updated:** 2025-11-04
**Version:** 1.0.0

> **Note:** This document is part of the split testing documentation, replacing the consolidated guide
> [Testing Guide](../docs/history/TESTING_GUIDE_CONSOLIDATED_2025-11-04.md) archived on 2025-11-04.
```

**5. Update Cross-References:**

Search and update all links to archived docs:

```bash
# Find all references to archived doc
grep -r "TESTING_GUIDE_CONSOLIDATED.md" .

# Update links to point to new docs
# TESTING_GUIDE_CONSOLIDATED.md → TESTING_MANUAL.md (or appropriate replacement)
```

**6. Update CHANGELOG.md:**

---

## Documentation Update Workflow

Relocated verbatim from `AGENTS.md` (P3 of the shared-session-memory plan) so it is read on demand rather than loaded into every session.

**On every change, update these files:**

1. **[CHANGELOG.md](CHANGELOG.md)** - Summarize changes and impact
   - What changed
   - Why it changed
   - Impact on users/developers

2. **[README.md](README.md)** - Update if run/test instructions change
   - Installation steps
   - Quick start commands
   - Current features

3. **[notes/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md](../notes/development/JUNIPER-CANOPY_POST-RELEASE_DEVELOPMENT-ROADMAP.md)** - Update status
   - Mark completed items
   - Update in-progress status
   - Add newly identified work

**Link relevant technical notes from "Recent Changes" section below.**

---

## Contact & Support

- **Author:** Paul Calnon
- **Project:** Juniper
- **Prototype:** juniper_canopy (Juniper Canopy)

**For Documentation Issues:**

1. Check this overview first
2. Search existing docs
3. Consult AGENTS.md for conventions
4. Check CHANGELOG.md for recent changes

---

**Last Updated:** January 29, 2026  
**Version:** 0.25.0  
**Maintainer:** Paul Calnon

---

## Recent Updates

### 2026-04-05: Release Readiness Documentation Index Refresh

- Added direct navigation links in "I Want To" for release-readiness review artifacts:
  - `notes/CODE_REVIEW_ANALYSIS_2026-04-04.md`
  - `notes/CODE_REVIEW_PLAN_2026-04-04.md`
- Expanded `notes/` document index to include these active maintenance documents.

### 2025-11-11: CI/CD Documentation Consolidation

- **Consolidated:** 12 CI/CD files → 4 focused documents
- **New location:** docs/ci_cd/ (single directory)
- **New structure:**
  - CICD_QUICK_START.md - Get running in 5 minutes
  - CICD_ENVIRONMENT_SETUP.md - Complete environment setup
  - CICD_MANUAL.md - Comprehensive usage guide
  - CICD_REFERENCE.md - Technical reference
- **Archived:** 8 legacy files to docs/history/ (2025-11-11)
