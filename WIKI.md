# Power BI PBIP / Fabric Dataset Conflict, Duplicate, Staging & Health Resolver
> **Official Wiki & User Manual** for [`PBIP-ConflictsResolve.py`](file:///c:/Users/shiva/Documents/Projects/USDT-Manager/PBIP-ConflictsResolve.py) (Version 5.0 Production Release)

Welcome to the comprehensive Wiki user guide for **Power BI PBIP Master Resolver** (`PBIP-ConflictsResolve.py`). This production-grade Python utility automates and simplifies Git merge conflict resolution, duplicate object removal, Field Parameter metadata alignment, JSON syntax formatting, pre-commit health diagnostics, and ultra-fast file staging across Power BI PBIP and Microsoft Fabric datasets (`.tmdl`, `.json`, `.pbir`, `.pbip`, `.platform`, `.fabric`, `.definition`, `.item`, `.report`).

---

## Table of Contents
1. [Overview & Highlights](#1-overview--highlights)
2. [Quick Start & Basic Usage](#2-quick-start--basic-usage)
3. [Mode Guide & Technical Capabilities](#3-mode-guide--technical-capabilities)
   - [Mode 1: Git Conflict Marker Resolution](#mode-1-git-conflict-marker-resolution)
   - [Mode 2: Duplicate Objects & Field Parameter / JSON Auto-Formatter](#mode-2-duplicate-objects--field-parameter--json-auto-formatter)
   - [Mode 3: Stage Clean Files to Git (Ultra-Fast)](#mode-3-stage-clean-files-to-git-ultra-fast)
   - [Mode 4: Power BI PBIP Metadata Health & Diagnostic Check](#mode-4-power-bi-pbip-metadata-health--diagnostic-check)
   - [Mode 5: Detailed Conflict Review & Visual Diff Viewer](#mode-5-detailed-conflict-review--visual-diff-viewer)
4. [Interactive Controls & Shortcuts](#4-interactive-controls--shortcuts)
5. [CLI Command-Line Options](#5-cli-command-line-options)
6. [Step-by-Step Practical Workflows](#6-step-by-step-practical-workflows)
7. [Troubleshooting & FAQ](#7-troubleshooting--faq)

---

## 1. Overview & Highlights

Power BI PBIP and Microsoft Fabric projects use developer-friendly text files (TMDL and JSON). However, when multiple developers collaborate using Git, merge conflicts and duplicate definitions often occur in metadata properties (`lineageTag`, `logicalId`, `$schema`, `name` bookmark IDs, Field Parameter arrays, and JSON comma lists).

`PBIP-ConflictsResolve.py` is a **zero-dependency, single-file Python script** designed to resolve these issues safely and efficiently:

- **100% Guaranteed Option Consistency**: Option `[1]` is **ALWAYS** Incoming Change (Top), and Option `[2]` is **ALWAYS** Current Branch / HEAD (Bottom).
- **Category-Scoped Auto-Keep (`1A`/`2A`)**: In Combo Mode (Option 6), typing `1A` or `2A` auto-resolves conflicts **strictly within THAT specific property category** (Lineage, LogicalId, Bookmark, Additions, etc.) and prompts again when transitioning to a new category.
- **Addition Sub-Types (Subset vs Empty-Side)**: Distinguishes Subset Additions (base content identical + extra lines added) from Empty-Side Additions (one branch has content, other branch is blank/empty), highlighting recommended choices interactively.
- **Field Parameter & JSON Auto-Formatter**: Automatically calculates and updates Field Parameter `"length"` metadata properties to match actual projection counts, re-sequences `"index"` values (`0, 1, 2, 3... N-1`), fixes missing commas (`}\n{` $\rightarrow$ `},\n{`), removes duplicate commas, and strips invalid trailing commas.
- **Bookmark Content Divergence Protection**: Pauses `1A`/`2A` auto-keep and displays a red warning if bookmark IDs differ alongside property content differences.
- **Ultra-Fast Git Staging**: Runs `git status --porcelain` once at the repo root (~10ms), bypassing unmodified and already-staged files for a **12,000x speedup**.
- **Sub-Menu Back Navigation**: Enter `b`, `back`, or `0` at any prompt to return to the Main Menu.

---

## 2. Quick Start & Basic Usage

### Requirements
- **Python 3.8+** (Standard Library only - zero external package installation required).
- Works on Windows, macOS, and Linux.

### Launching Interactively
To start the interactive menu, simply run:

```bash
python PBIP-ConflictsResolve.py
```
Or specify your PBIP dataset folder directly:

```bash
python PBIP-ConflictsResolve.py "C:\Path\To\MyReport.Dataset"
```

When launched, the Main Menu displays:

```text
================================================================================
               Power BI PBIP Master Conflict & Duplicate Resolver
================================================================================
Select resolution action to perform:
 1 - Resolve Git Conflict Markers (lineageTag, logicalId, $schema, bookmark IDs, additions, and all conflicts)
 2 - Resolve Duplicate Objects & Auto-Format Field Parameter / JSON Metadata
 3 - Stage Clean Files to Git (Automatically git add files with 0 remaining conflict markers)
 4 - Power BI PBIP Metadata Health & Diagnostic Check (Scan for all remaining issues)
 5 - Detailed Conflict Review & Visual Diff Viewer (Review remaining conflicts one-by-one with diff highlights)
```

---

## 3. Mode Guide & Technical Capabilities

### Mode 1: Git Conflict Marker Resolution
Scans files for Git merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) using index-based line range deletion.

#### Target Property Filters:
- `1 - LineageTags`: Resolves `lineageTag` and `sourceLineageTag` conflict lines in TMDL files.
- `2 - LogicalIds`: Resolves `logicalId` and `sourceLogicalId` conflict lines in TMDL, JSON, and `.platform` files.
- `3 - SchemaTags`: Resolves `"$schema": "https://..."` conflict lines in PBIP JSON report files.
- `4 - Bookmark / Object Name IDs`: Resolves `"name": "<hex-hash>"` conflict lines in `bookmarks.json`, `page.json`, `visual.json`.
- `5 - Additions Only`:
  - `5.1 - Subset Additions`: Base content is identical between branches, but extra lines were added on one side.
  - `5.2 - Empty-Side Additions`: One side contains code/text while the opposite side is completely blank/empty.
  - `5.3 - All Additions`: Both Subset & Empty-Side Additions.
- `6 - All Conflict Markers (Combo Mode)`: Resolves all conflict marker types. Features **Category-Scoped Auto-Keep**!

#### Special Features in Mode 1:
- **Category-Scoped `1A` / `2A`**: Typing `1A` while resolving LineageTags applies Option 1 only to remaining LineageTags. When transitioning to Bookmark IDs or Additions, the script prompts you again!
- **Bookmark Content Divergence Protection**: If bookmark IDs differ BUT their properties also differ, the script pauses bulk auto-keep and displays:
  `[!] BOOKMARK DIVERGENCE DETECTED: Name is DIFFERENT AND Content/Properties are ALSO DIFFERENT!`
  forcing interactive approval (`1`, `2`, or `s`).
- **Partial Fix (`1P` / `2P`)**: For mixed conflicts (where property tags and visual code are inside the same conflict block), `1P` or `2P` updates the tag line while preserving conflict markers around visual changes.
- **Cross-Reference Propagation**: Prompts `(y/n)` or accepts `--propagate-refs` to scan all dataset files and update cross-references of discarded bookmark/object IDs.

---

### Mode 2: Duplicate Objects & Field Parameter / JSON Auto-Formatter
Scans for duplicate object definitions when Git conflict markers are absent, and performs metadata auto-formatting.

#### Target Options:
- `1 - Columns`: Scans TMDL files for duplicate `column` definitions.
- `2 - Expressions`: Scans TMDL files for duplicate `expression` definitions.
- `3 - Relationships`: Scans TMDL files for duplicate `relationship` definitions (uses canonical pair matching `TableA[ColA] <-> TableB[ColB]` regardless of direction).
- `4 - Field Parameter & JSON Auto-Formatter`:
  - **Field Parameter `"length"`**: Auto-updates `"length"` to equal `len(projections)`.
  - **Field Parameter `"index"`**: Re-sequences projection items to `0, 1, 2, 3... N-1`.
  - **JSON Syntax & Commas**: Auto-fixes `}\n{` $\rightarrow$ `},\n{`, removes duplicate commas (`,,`), and strips trailing commas before brackets.
- `5 - All`: Performs all object deduplication and formatting tasks.

---

### Mode 3: Stage Clean Files to Git (Ultra-Fast)
Automatically stages files with 0 remaining conflicts to Git index (`git add`).

#### Performance Highlights:
- Runs `git status --porcelain` **ONCE** at the repository root (~10ms).
- Bypasses unmodified files and skips already-staged files (`M  `, `A  `).
- Displays live real-time progress feedback (`[X/N] Checking...`).
- Batches clean files into `git add` calls of 50 files per process for maximum speed.

---

### Mode 4: Power BI PBIP Metadata Health & Diagnostic Check
Performs a comprehensive dataset health scan without modifying files, reporting exact line numbers for:
1. **Unresolved Git Conflict Markers** (`<<<<<<<`, `=======`, `>>>>>>>`).
2. **Duplicate TMDL Object Definitions** (Columns, Expressions, Relationships).
3. **Field Parameter Length Mismatches** (`"length"` property vs actual projection item count).
4. **Field Parameter Index Errors** (Duplicate or non-sequential projection `index` values).
5. **JSON Syntax Parse Errors**.
6. **Missing LineageTags** on TMDL columns.

---

### Mode 5: Detailed Conflict Review & Visual Diff Viewer
Provides an interactive visual review for remaining conflicts:
- Displays line-by-line diff highlights (`* <-- DIFFERENT`).
- Option `[1]` is **ALWAYS** Incoming Change (Top).
- Option `[2]` is **ALWAYS** Current Branch / HEAD (Bottom).
- Supports interactive selection: `1`, `2`, `1A`, `2A`, `s`.

---

## 4. Interactive Controls & Shortcuts

| Input | Action |
| :--- | :--- |
| `1` | Keep Option 1 (Incoming Change / Top) for current item |
| `2` | Keep Option 2 (Current Branch / HEAD / Bottom) for current item |
| `1A` / `a1` | Auto-keep Option 1 for all remaining items in the active category / session |
| `2A` / `a2` | Auto-keep Option 2 for all remaining items in the active category / session |
| `1P` / `p1` | Partial Fix: Update property line to Option 1, keep conflict markers around visual changes |
| `2P` / `p2` | Partial Fix: Update property line to Option 2, keep conflict markers around visual changes |
| `s` / `skip` | Skip current conflict/duplicate untouched |
| `b` / `back` / `0` | Return to Main Menu from any sub-menu prompt |

---

## 5. CLI Command-Line Options

You can automate or run the script non-interactively using CLI flags:

```bash
python PBIP-ConflictsResolve.py [path] [flags]
```

### Argument Reference:

| Flag | Values | Description |
| :--- | :--- | :--- |
| `path` | File/Folder path | Path to dataset directory or target file |
| `--mode` | `1`, `2`, `3`, `4`, `5` | Mode selection (`1` Conflict Markers, `2` Dedupe/Format, `3` Stage, `4` Diag, `5` Review) |
| `--conflict-type` | `1`, `2`, `3`, `4`, `5.1`, `5.2`, `5.3`, `6` | Target filter for Mode 1 (`lineage`, `logical`, `schema`, `bookmark`, `subset`, `empty`, `addition`, `all`) |
| `--type` | `1`, `2`, `3`, `4`, `5` | Target object type for Mode 2 (`column`, `expression`, `relationship`, `formatter`, `all`) |
| `--propagate-refs` | Flag | Enable cross-reference propagation for discarded Bookmark/Object IDs |
| `--dry-run` | Flag | Simulate actions and report without saving file changes |
| `--keep-first` | Flag | Non-interactive auto-keep Option 1 (Incoming) |
| `--keep-last` | Flag | Non-interactive auto-keep Option 2 (Current Branch) |
| `--extensions` | Extension list | Comma-separated extensions to scan (default: `tmdl,json,pbir,pbip,platform,fabric,definition,item,report`) |

### Example CLI Commands:

1. **Non-Interactive LineageTag Conflict Resolution**:
   ```bash
   python PBIP-ConflictsResolve.py "C:\Projects\Sales.Report" --mode 1 --conflict-type 1 --keep-first
   ```

2. **Run Metadata Diagnostic Health Check**:
   ```bash
   python PBIP-ConflictsResolve.py "C:\Projects\Sales.Report" --mode 4
   ```

3. **Ultra-Fast Staging of Clean Files**:
   ```bash
   python PBIP-ConflictsResolve.py "C:\Projects\Sales.Report" --mode 3
   ```

---

## 6. Step-by-Step Practical Workflows

### Workflow A: Resolving Git Merge Conflicts
1. Run `python PBIP-ConflictsResolve.py`.
2. Select **Option 1 (Resolve Git Conflict Markers)**.
3. Select **Option 6 (All Conflict Markers - Combo Mode)**.
4. Review property conflicts. Use `1A` or `2A` to quickly auto-resolve LineageTags, LogicalIds, and SchemaTags within each category.
5. For Additions or Divergent Bookmarks, inspect the visual badges and select `1` or `2`.
6. Select **Option 3 (Stage Clean Files to Git)** to stage resolved files in milliseconds.

### Workflow B: Post-Merge Field Parameter & JSON Auto-Fixing
1. Run `python PBIP-ConflictsResolve.py`.
2. Select **Option 2 (Resolve Duplicate Objects & Auto-Format)**.
3. Select **Option 4 (Field Parameter & JSON Auto-Formatter)**.
4. The script will automatically scan all JSON and TMDL files, align Field Parameter `length` and `index` sequences, fix missing commas, and remove duplicate commas.

---

## 7. Troubleshooting & FAQ

### Q: Why is Mode 3 (Staging) so fast?
**A**: Mode 3 runs `git status --porcelain` once at the repository root (~10ms) to identify modified files, completely bypassing unmodified files and skipping already-staged files without reading them on disk.

### Q: Does this script preserve UTF-8 BOM encoding?
**A**: Yes. The script detects UTF-8 Byte Order Marks (`\xef\xbb\xbf`) on disk and preserves BOM byte-for-byte upon writing.

### Q: Will `1A` in Combo Mode overwrite all conflict types blindly?
**A**: No. Auto-keep (`1A`/`2A`) in Combo Mode is **Category-Scoped**. Typing `1A` while resolving LineageTags applies only to LineageTags and will prompt you again when transitioning to Bookmarks or Additions.

### Q: What if a bookmark ID and its properties both differ?
**A**: The script detects bookmark content divergence, pauses bulk auto-keep, displays a red `[!] BOOKMARK DIVERGENCE DETECTED` warning, and prompts you interactively to choose `1`, `2`, or `s` (skip).

---
*Created for Power BI PBIP & Fabric Development Teams.*
