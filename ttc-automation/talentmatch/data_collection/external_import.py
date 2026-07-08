"""External data import — batch resume upload (zip/rar) + Boss/猎聘 chat import"""
from __future__ import annotations
import os
import re
import json
import uuid
import zipfile
import tempfile
import shutil
from typing import Optional, Callable
from loguru import logger


class BatchImporter:
    """Handles batch import of resume files from compressed archives.
    
    Supports:
      - .zip archives (native Python support)
      - Multiple resume files in a single archive
      - Automatic dedup by filename+size
      - Progress callback for Feishu notifications
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg"}

    def __init__(self, upload_dir: str = "/tmp/recruit-imports", 
                 extract_cb: Optional[Callable] = None):
        """
        Args:
            upload_dir: Directory to store extracted files
            extract_cb: Callback(filename, status, error) for each file
        """
        self.upload_dir = upload_dir
        self.extract_cb = extract_cb
        os.makedirs(upload_dir, exist_ok=True)

    def extract_zip(self, zip_path: str) -> list[dict]:
        """Extract resume files from a zip archive.
        
        Returns list of dicts: {filename, filepath, size, extension, status}
        """
        results = []
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Create a unique extraction subdirectory
                extract_id = uuid.uuid4().hex[:12]
                extract_dir = os.path.join(self.upload_dir, extract_id)
                os.makedirs(extract_dir, exist_ok=True)

                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    
                    ext = os.path.splitext(info.filename)[1].lower()
                    if ext not in self.SUPPORTED_EXTENSIONS:
                        continue

                    # Extract with safe name
                    safe_name = os.path.basename(info.filename)
                    out_path = os.path.join(extract_dir, safe_name)
                    
                    try:
                        zf.extract(info, extract_dir)
                        # Move file from any subdirectory to flat dir
                        actual_path = os.path.join(extract_dir, info.filename)
                        if actual_path != out_path:
                            shutil.move(actual_path, out_path)
                            # Clean up empty subdirectories
                            self._cleanup_empty_dirs(extract_dir)

                        results.append({
                            "filename": safe_name,
                            "filepath": out_path,
                            "size": info.file_size,
                            "extension": ext,
                            "status": "extracted",
                        })
                        
                        if self.extract_cb:
                            self.extract_cb(safe_name, "extracted", "")
                            
                    except Exception as e:
                        logger.warning(f"Failed to extract {info.filename}: {e}")
                        results.append({
                            "filename": safe_name,
                            "filepath": "",
                            "size": 0,
                            "extension": ext,
                            "status": f"error: {str(e)[:50]}",
                        })
                        if self.extract_cb:
                            self.extract_cb(safe_name, "error", str(e))

        except zipfile.BadZipFile:
            logger.error(f"Invalid zip file: {zip_path}")
            return [{"filename": os.path.basename(zip_path), "filepath": "",
                     "size": 0, "extension": ".zip", "status": "error: invalid zip"}]
        
        logger.info(f"Extracted {len(results)} files from {zip_path}")
        return results

    def extract_rar(self, rar_path: str) -> list[dict]:
        """Extract resume files from a RAR archive.
        
        Falls back to using `unrar` command if available, otherwise warns.
        """
        # Check if unrar is available
        import subprocess
        try:
            subprocess.run(["unrar", "--version"], capture_output=True, check=True)
            has_unrar = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            has_unrar = False

        if not has_unrar:
            logger.warning("unrar not available, cannot extract .rar files")
            return [{"filename": os.path.basename(rar_path), "filepath": "",
                     "size": 0, "extension": ".rar", "status": "error: unrar not installed"}]

        extract_id = uuid.uuid4().hex[:12]
        extract_dir = os.path.join(self.upload_dir, extract_id)
        os.makedirs(extract_dir, exist_ok=True)

        results = []
        try:
            result = subprocess.run(
                ["unrar", "x", "-y", rar_path, extract_dir + "/"],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"unrar failed: {result.stderr[:200]}")
                return [{"filename": os.path.basename(rar_path), "filepath": "",
                         "size": 0, "extension": ".rar", "status": "error: unrar failed"}]

            # Collect extracted files
            for fname in os.listdir(extract_dir):
                fpath = os.path.join(extract_dir, fname)
                if not os.path.isfile(fpath):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in self.SUPPORTED_EXTENSIONS:
                    os.unlink(fpath)
                    continue
                    
                results.append({
                    "filename": fname,
                    "filepath": fpath,
                    "size": os.path.getsize(fpath),
                    "extension": ext,
                    "status": "extracted",
                })

        except subprocess.TimeoutExpired:
            logger.error("unrar timed out")
            return [{"filename": os.path.basename(rar_path), "filepath": "",
                     "size": 0, "extension": ".rar", "status": "error: unrar timeout"}]
        except Exception as e:
            logger.error(f"RAR extraction failed: {e}")
            return [{"filename": os.path.basename(rar_path), "filepath": "",
                     "size": 0, "extension": ".rar", "status": f"error: {str(e)[:50]}"}]

        return results

    def _cleanup_empty_dirs(self, root_dir: str):
        """Remove empty subdirectories after extraction."""
        for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
            if dirpath != root_dir and not dirnames and not filenames:
                os.rmdir(dirpath)


class BossImportParser:
    """Parse Boss直聘 chat export files (JSON/CSV) into structured candidate data.
    
    Boss直聘聊天记录格式（导出JSON）:
    {
        "data": [{
            "candidate_name": "张三",
            "current_company": "字节跳动",
            "current_position": "高级工程师",
            "skills": ["Python", "Go"],
            "chat_content": "..."
        }]
    }
    """

    def parse_json(self, json_data: str) -> list[dict]:
        """Parse Boss直聘 JSON export into candidate dicts."""
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as e:
            logger.error(f"Boss JSON parse error: {e}")
            return []

        records = data if isinstance(data, list) else data.get("data", data.get("items", []))
        candidates = []
        
        for item in records:
            if not item.get("candidate_name") and not item.get("name"):
                continue
                
            candidate = {
                "name": item.get("candidate_name") or item.get("name", "未知"),
                "current_role": item.get("current_position") or item.get("position", ""),
                "current_company": item.get("current_company") or item.get("company", ""),
                "skills": item.get("skills", []),
                "source": "boss_zhipin",
                "source_id": item.get("id", str(uuid.uuid4())),
            }
            
            # Extract skills from chat content if present
            chat = item.get("chat_content", "")
            if chat and not candidate["skills"]:
                extracted = self._extract_skills_from_chat(chat)
                candidate["skills"] = extracted
            
            candidates.append(candidate)
        
        return candidates

    def _extract_skills_from_chat(self, text: str) -> list[str]:
        """Try to extract skill mentions from chat text."""
        # Common tech skills to look for
        common_skills = [
            "Python", "Java", "Go", "JavaScript", "TypeScript", "C++", "Rust",
            "React", "Vue", "Angular", "Node.js", "Django", "Flask", "Spring",
            "TensorFlow", "PyTorch", "Kubernetes", "Docker", "AWS", "GCP",
            "MySQL", "PostgreSQL", "MongoDB", "Redis", "Kafka", "Spark",
            "机器学习", "深度学习", "推荐系统", "NLP", "计算机视觉",
        ]
        found = []
        for skill in common_skills:
            if skill.lower() in text.lower():
                found.append(skill)
        return found


class LiepinImportParser:
    """Parse 猎聘 chat export files into structured candidate data.
    
    猎聘导出格式类似，字段名略有不同。
    """

    def parse_json(self, json_data: str) -> list[dict]:
        """Parse 猎聘 JSON export into candidate dicts."""
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as e:
            logger.error(f"Liepin JSON parse error: {e}")
            return []

        records = data if isinstance(data, list) else data.get("list", [])
        candidates = []
        
        for item in records:
            candidate = {
                "name": item.get("name") or item.get("candidateName", "未知"),
                "current_role": item.get("position") or item.get("title", ""),
                "current_company": item.get("company") or item.get("currentCompany", ""),
                "skills": item.get("skills", item.get("skillTags", [])),
                "source": "liepin",
                "source_id": item.get("id", str(uuid.uuid4())),
            }
            candidates.append(candidate)
        
        return candidates


def auto_detect_import_format(text: str) -> Optional[str]:
    """Auto-detect import format from text content."""
    if not text:
        return None
    
    text_stripped = text.strip()
    
    # Check JSON
    if text_stripped.startswith("{"):
        if '"data"' in text_stripped or '"items"' in text_stripped:
            return "boss_zhipin"
        if '"list"' in text_stripped:
            return "liepin"
        return "json_generic"
    
    if text_stripped.startswith("["):
        return "json_array"
    
    return None
