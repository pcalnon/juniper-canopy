# Documentation Overview

## Complete Navigation Guide to Juniper Canopy Documentation

**Version:** 0.25.0  
**Last Updated:** January 29, 2026  
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
| **See version history**      | [CHANGELOG.md](../CHANGELOG.md)                                           | Root           |
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
- Version history (0.4.0, 0.3.0, 0.2.1, 0.2.0, 0.1.4)
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
| **ci_cd/CICD_QUICK_START.md**            | ~400   | Tutorial  | Developers     | ✅ **Active** |
| **ci_cd/CICD_ENVIRONMENT_SETUP.md**      | ~870   | Guide     | DevOps         | ✅ **Active** |
| **ci_cd/CICD_MANUAL.md**                 | ~1,688 | Guide     | Developers     | ✅ **Active** |
| **ci_cd/CICD_REFERENCE.md**              | ~1,058 | Reference | All            | ✅ **Active** |
| **testing/TESTING_QUICK_START.md**       | ~180   | Tutorial  | Developers     | ✅ **Active** |
| **testing/TESTING_ENVIRONMENT_SETUP.md** | ~550   | Guide     | Developers     | ✅ **Active** |
| **testing/TESTING_MANUAL.md**            | ~900   | Guide     | Developers     | ✅ **Active** |
| **testing/TESTING_REFERENCE.md**         | ~1,200 | Reference | Developers     | ✅ **Active** |
| **testing/TESTING_REPORTS_COVERAGE.md**  | ~900   | Guide     | Developers     | ✅ **Active** |

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

### 2025-11-11: CI/CD Documentation Consolidation

- **Consolidated:** 12 CI/CD files → 4 focused documents
- **New location:** docs/ci_cd/ (single directory)
- **New structure:**
  - CICD_QUICK_START.md - Get running in 5 minutes
  - CICD_ENVIRONMENT_SETUP.md - Complete environment setup
  - CICD_MANUAL.md - Comprehensive usage guide
  - CICD_REFERENCE.md - Technical reference
- **Archived:** 8 legacy files to docs/history/ (2025-11-11)
