import os
import json
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SubjectManager")

DEFAULT_SUBJECTS = [
    {
        "id": "korean_history",
        "name": "Lịch Sử Hàn Quốc (한국사)",
        "glossary": "한국사, 구석기, 신석기, 뗀석기, 슴베찌르개, 빗살무늬토기, 단군왕검, 고조선, 삼국시대, 고구려, 백제, 신라",
        "color": "#f59e0b"
    },
    {
        "id": "computer_science",
        "name": "Khoa Học Máy Tính (컴퓨터공학)",
        "glossary": "컴퓨터공학, 운영체제, 알고리즘, 자료구조, 데이터베이스, 네트워크, 인공지능, 프로세스, 메모리",
        "color": "#3b82f6"
    },
    {
        "id": "business_economics",
        "name": "Kinh Tế & Quản Trị (경영학 / 경제학)",
        "glossary": "경영학, 경제학, 재무제표, 마케팅, 회계, 손익분기점, 공급망, 거시경제, 미시경제",
        "color": "#10b981"
    },
    {
        "id": "general_lecture",
        "name": "Môn Học Chung (일반 강의)",
        "glossary": "한국어 대학교 강의, 학술 용어, 전공 수업, 과제, 중간고사, 기말고사",
        "color": "#8b5cf6"
    }
]

class SubjectManager:
    def __init__(self, data_dir="data", transcripts_dir="transcripts", recordings_dir="recordings"):
        self.data_dir = data_dir
        self.transcripts_dir = transcripts_dir
        self.recordings_dir = recordings_dir
        
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.transcripts_dir, exist_ok=True)
        os.makedirs(self.recordings_dir, exist_ok=True)
        
        self.subjects_file = os.path.join(self.data_dir, "subjects.json")
        self.subjects = self._load_subjects()

    def _load_subjects(self) -> List[Dict[str, Any]]:
        """Load subjects list from JSON or initialize with defaults"""
        if os.path.exists(self.subjects_file):
            try:
                with open(self.subjects_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading subjects file: {e}")
        
        # Save defaults
        self._save_subjects(DEFAULT_SUBJECTS)
        return DEFAULT_SUBJECTS

    def _save_subjects(self, subjects: List[Dict[str, Any]]):
        """Save subjects to file"""
        try:
            with open(self.subjects_file, "w", encoding="utf-8") as f:
                json.dump(subjects, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving subjects: {e}")

    def get_all_subjects(self) -> List[Dict[str, Any]]:
        return self.subjects

    def get_subject_by_name_or_id(self, identifier: str) -> Dict[str, Any]:
        for s in self.subjects:
            if s["id"] == identifier or s["name"] == identifier:
                return s
        return self.subjects[-1] # Fallback to general

    def add_subject(self, name: str, glossary: str = "", color: str = "#06b6d4") -> Dict[str, Any]:
        """Create a new subject"""
        safe_id = "".join(c for c in name.lower() if c.isalnum() or c == '_').strip()
        if not safe_id:
            safe_id = f"sub_{len(self.subjects) + 1}"
            
        new_sub = {
            "id": safe_id,
            "name": name.strip(),
            "glossary": glossary.strip(),
            "color": color
        }
        
        # Check if already exists, update instead
        exists = False
        for idx, s in enumerate(self.subjects):
            if s["id"] == safe_id or s["name"] == name.strip():
                self.subjects[idx] = new_sub
                exists = True
                break
                
        if not exists:
            self.subjects.append(new_sub)
            
        self._save_subjects(self.subjects)
        return new_sub

    def list_all_lectures(self) -> List[Dict[str, Any]]:
        """Scans transcripts & recordings to return all recorded lectures grouped by subject"""
        lectures = []
        
        if not os.path.exists(self.transcripts_dir):
            return lectures
            
        # Scan subject folders
        for root, dirs, files in os.walk(self.transcripts_dir):
            for file in files:
                if file.endswith(".json") or file.endswith(".md"):
                    filepath = os.path.join(root, file)
                    rel_dir = os.path.relpath(root, self.transcripts_dir)
                    subject_folder = rel_dir if rel_dir != "." else "General"
                    
                    stat = os.stat(filepath)
                    mtime = stat.st_mtime
                    file_size = stat.st_size
                    
                    # Corresponding recording WAV if available
                    base_no_ext = os.path.splitext(file)[0]
                    wav_filename = f"{base_no_ext}.wav"
                    wav_path = os.path.join(self.recordings_dir, subject_folder, wav_filename)
                    has_audio = os.path.exists(wav_path)
                    
                    if file.endswith(".json"):
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                data = json.load(f)
                                lectures.append({
                                    "id": data.get("session_id", base_no_ext),
                                    "title": data.get("title", base_no_ext),
                                    "subject": data.get("subject", subject_folder),
                                    "date": data.get("date", ""),
                                    "duration": data.get("duration", "00:00:00"),
                                    "sentence_count": len(data.get("entries", [])),
                                    "bookmark_count": sum(1 for e in data.get("entries", []) if e.get("is_bookmark")),
                                    "has_audio": has_audio,
                                    "audio_url": f"/api/audio/{subject_folder}/{wav_filename}" if has_audio else None,
                                    "json_file": file,
                                    "md_download_url": f"/api/download_md/{subject_folder}/{base_no_ext}.md",
                                    "mtime": mtime
                                })
                        except Exception:
                            pass

        # Sort newest first
        lectures.sort(key=lambda x: x.get("mtime", 0), reverse=True)
        return lectures
