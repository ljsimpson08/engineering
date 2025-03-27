import os
import json
import logging
import ast
from tqdm import tqdm
from pathlib import Path
from typing import Dict, List, Optional

# Constants
SCAN_DIR = "scans"
IGNORED_DIRECTORIES = {'.git', '.venv', 'node_modules', '__pycache__', 'venv', 'env'}
IGNORED_FILES = {'.DS_Store', '.gitignore', '.env'}

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class ProjectScanner:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.scan_dir = self.root_dir / SCAN_DIR
        self.ext_mapping = {
            ".py": "python", ".js": "javascript", ".ts": "typescript", ".html": "html",
            ".css": "css", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
            ".tf": "terraform", ".sh": "shell", ".rb": "ruby", ".go": "golang",
            ".java": "java", ".c": "c", ".cpp": "cpp", ".rs": "rust", ".php": "php",
            ".sql": "sql", ".md": "markdown", ".xml": "xml"
        }

        self.scan_dir.mkdir(exist_ok=True)

    def get_latest_scan_filename(self) -> Path:
        """Generate incremented scan filename."""
        existing_scans = sorted(self.scan_dir.glob("project_scan_v*.json"))
        next_version = len(existing_scans) + 1
        return self.scan_dir / f"project_scan_v{next_version:03}.json"

    def get_file_type(self, filename: str) -> str:
        """Return file type based on extension."""
        return self.ext_mapping.get(Path(filename).suffix.lower(), "unknown")

    def should_ignore_path(self, path: str) -> bool:
        """Check if a path should be ignored."""
        return any(part in IGNORED_DIRECTORIES for part in Path(path).parts) or Path(path).name in IGNORED_FILES

    def extract_python_ast(self, content: str) -> Optional[str]:
        """Generate AST for Python files."""
        try:
            tree = ast.parse(content)
            return ast.dump(tree)
        except SyntaxError:
            logger.warning("Syntax error in Python file, AST not generated.")
            return None

    def read_file_content(self, file_path: Path) -> Dict[str, Optional[str]]:
        """Read file content and extract AST for Python files."""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
                ast_data = self.extract_python_ast(content) if self.get_file_type(file_path.name) == "python" else None
                return {"content": content, "ast": ast_data}
        except UnicodeDecodeError:
            logger.warning(f"Binary file detected, skipping content: {file_path}")
            return {"content": "[Binary file]", "ast": None}
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            return {"content": f"[Could not read file: {str(e)}]", "ast": None}

    def scan_directory(self) -> List[Dict]:
        """Scan directory and return project structure data."""
        project_data = []
        all_files = list(self.root_dir.rglob("*"))

        with tqdm(all_files, desc="Scanning Project") as files:
            for path in files:
                if path.is_file() and not self.should_ignore_path(str(path)):
                    rel_path = str(path.relative_to(self.root_dir))
                    file_info = {
                        "name": path.name,
                        "file_type": self.get_file_type(path.name),
                        "path": rel_path,
                        **self.read_file_content(path)
                    }
                    project_data.append(file_info)
                    logger.info(f"Processed file: {rel_path}")

        return project_data

    def save_project_structure(self, project_data: List[Dict]) -> None:
        """Save project structure to JSON with versioning."""
        output_file = self.get_latest_scan_filename()
        try:
            with open(output_file, "w", encoding="utf-8") as json_file:
                json.dump(project_data, json_file, indent=4)
            logger.info(f"Project scan saved in {output_file}")
        except Exception as e:
            logger.error(f"Error saving project structure: {str(e)}")

def main():
    scanner = ProjectScanner(os.getcwd())
    project_data = scanner.scan_directory()
    scanner.save_project_structure(project_data)

if __name__ == "__main__":
    main()