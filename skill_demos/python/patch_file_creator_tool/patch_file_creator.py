import json
import os
import io
import difflib
from pathlib import Path

# Load JSON files
with open('vanilla_scan.json', 'r', encoding='utf-8') as f:
    original = json.load(f)

with open('project_scan_v001.json', 'r', encoding='utf-8') as f:
    improved = json.load(f)

# Create temporary directories
os.makedirs('original', exist_ok=True)
os.makedirs('improved', exist_ok=True)

# Extract files from JSON scans
def extract_files(scan_data, output_dir):
    for file_info in scan_data:
        path = file_info['path']
        content = file_info['content']
        
        # Create directory structure
        full_path = os.path.join(output_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Write file content
        with open(full_path, 'w', encoding='utf-8', errors='replace') as f:
            f.write(content)
    return [file_info['path'] for file_info in scan_data]

# Extract both versions
original_files = extract_files(original, 'original')
improved_files = extract_files(improved, 'improved')

# Generate diff using Python's difflib
with open('payment_processor_improvements.patch', 'w', encoding='utf-8') as patch_file:
    # Find all unique files across both versions
    all_files = set(original_files) | set(improved_files)
    
    for file_path in sorted(all_files):
        original_file_path = os.path.join('original', file_path)
        improved_file_path = os.path.join('improved', file_path)
        
        # File exists in both versions - create diff
        if os.path.exists(original_file_path) and os.path.exists(improved_file_path):
            with open(original_file_path, 'r', encoding='utf-8', errors='replace') as f1:
                original_lines = f1.readlines()
            with open(improved_file_path, 'r', encoding='utf-8', errors='replace') as f2:
                improved_lines = f2.readlines()
            
            # Generate unified diff
            diff = difflib.unified_diff(
                original_lines, 
                improved_lines,
                fromfile=f'a/{file_path}',
                tofile=f'b/{file_path}',
                n=3  # Context lines
            )
            
            # Write diff to patch file
            diff_content = ''.join(diff)
            if diff_content:
                patch_file.write(diff_content + '\n')
        
        # File only in improved version - mark as new
        elif os.path.exists(improved_file_path):
            with open(improved_file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.readlines()
            
            patch_file.write(f'--- /dev/null\n')
            patch_file.write(f'+++ b/{file_path}\n')
            patch_file.write('@@ -0,0 +1,{} @@\n'.format(len(content)))
            for line in content:
                patch_file.write(f'+{line}')
            patch_file.write('\n')
        
        # File only in original version - mark as deleted
        elif os.path.exists(original_file_path):
            with open(original_file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.readlines()
            
            patch_file.write(f'--- a/{file_path}\n')
            patch_file.write(f'+++ /dev/null\n')
            patch_file.write('@@ -1,{} +0,0 @@\n'.format(len(content)))
            for line in content:
                patch_file.write(f'-{line}')
            patch_file.write('\n')

# Clean up
import shutil
shutil.rmtree('original')
shutil.rmtree('improved')

print("Patch file created: payment_processor_improvements.patch")