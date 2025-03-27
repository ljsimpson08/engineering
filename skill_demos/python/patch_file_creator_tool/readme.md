# Patch File Creator

**Filename:** `patch_file_creator.py`  
**Description:**  
This script generates a patch file (unified diff) by comparing two sets of project files. One set represents the “original” version, and the other the “improved” version. The JSON scans (e.g., `vanilla_scan.json` and `project_scan_v001.json`) describe file paths and contents; the script uses them to reconstruct the directories before creating diffs.

## Features

- **JSON-Based Directory Reconstruction:** Reads two JSON files describing file paths and contents.
- **Unified Diff Generation:** Creates a `.patch` file showing differences between the two versions.
- **Detects New/Removed Files:** Marks files that exist only in one version as new or deleted.

## Requirements

- Python 3.x
- No external libraries (uses the Python standard library: `json`, `os`, `difflib`, `shutil`, etc.).

## Installation

No special steps required. Just have Python 3 installed, plus two JSON files describing your original and improved directories.

## Usage

1. **Prepare two JSON scan files**:
   - `vanilla_scan.json` (original)
   - `project_scan_v001.json` (improved)
2. **Run the script**:
   ```bash
   python patch_file_creator.py

## The script will:
- Read both JSON files.
- Temporarily create original and improved directories.
- Compare them file by file using difflib.unified_diff.
- Write the patch to payment_processor_improvements.patch.
- Remove the temporary directories.

## JSON File Structure
- Each JSON file is expected to be a list of objects like:
   json
   Copy
   Edit
   {
   "path": "relative/path/to/file.rb",
   "content": "file contents here..."
   }
   The script uses this information to reconstruct each file before generating diffs.