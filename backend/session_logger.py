import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any

class SessionLogger:
    def __init__(self, base_transcripts_dir: str = "transcripts"):
        self.base_transcripts_dir = base_transcripts_dir
        os.makedirs(self.base_transcripts_dir, exist_ok=True)
        
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start = datetime.now()
        self.entries: List[Dict[str, Any]] = []
        self.lecture_title = f"Lecture_{datetime.now().strftime('%Y-%m-%d_%H%M')}"
        self.subject_name = "General"
        
    def start_new_session(self, title: str = None, subject_name: str = "General"):
        """Reset and start a new lecture session grouped by subject"""
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start = datetime.now()
        self.entries = []
        self.subject_name = re_sanitize(subject_name) if subject_name else "General"
        if title and title.strip():
            self.lecture_title = title.strip()
        else:
            self.lecture_title = f"Lecture_{datetime.now().strftime('%Y-%m-%d_%H%M')}"

    def add_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Add a translation entry to the session"""
        entry_with_id = {
            "id": len(self.entries) + 1,
            "timestamp": entry.get("timestamp", datetime.now().strftime("%H:%M:%S")),
            "korean": entry.get("korean", "").strip(),
            "english": entry.get("english", "").strip(),
            "vietnamese": entry.get("vietnamese", "").strip(),
            "duration": entry.get("duration", 0),
            "inference_time": entry.get("inference_time", 0),
            "is_bookmark": bool(entry.get("is_bookmark", False))
        }
        self.entries.append(entry_with_id)
        # Auto save JSON state
        self._auto_save_state()
        return entry_with_id

    def toggle_bookmark(self, entry_id: int) -> bool:
        """Toggle bookmark on a specific sentence"""
        for item in self.entries:
            if item["id"] == entry_id:
                item["is_bookmark"] = not item.get("is_bookmark", False)
                self._auto_save_state()
                return item["is_bookmark"]
        return False

    def bookmark_last_entry(self) -> Dict[str, Any]:
        """Bookmark the most recent sentence"""
        if len(self.entries) > 0:
            self.entries[-1]["is_bookmark"] = True
            self._auto_save_state()
            return self.entries[-1]
        return None

    def get_history(self) -> List[Dict[str, Any]]:
        return self.entries

    def get_duration_str(self) -> str:
        duration = datetime.now() - self.session_start
        total_seconds = int(duration.total_seconds())
        hrs, rem = divmod(total_seconds, 3600)
        mins, secs = divmod(rem, 60)
        return f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs > 0 else f"{mins:02d}:{secs:02d}"

    def _get_subject_folder(self) -> str:
        folder = os.path.join(self.base_transcripts_dir, self.subject_name)
        os.makedirs(folder, exist_ok=True)
        return folder

    def _auto_save_state(self):
        """Saves session state to JSON in subject folder"""
        try:
            folder = self._get_subject_folder()
            safe_title = re_sanitize(self.lecture_title)
            filepath = os.path.join(folder, f"{self.session_id}_{safe_title}.json")
            
            data = {
                "session_id": self.session_id,
                "title": self.lecture_title,
                "subject": self.subject_name,
                "date": self.session_start.strftime('%Y-%m-%d %H:%M:%S'),
                "duration": self.get_duration_str(),
                "entries": self.entries
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            # Also update Markdown file
            self.export_markdown()
        except Exception:
            pass

    def export_markdown(self) -> str:
        """Export lecture transcript as a rich 3-language Markdown study document"""
        folder = self._get_subject_folder()
        safe_title = re_sanitize(self.lecture_title)
        filename = f"{self.session_id}_{safe_title}.md"
        filepath = os.path.join(folder, filename)
        
        duration_str = self.get_duration_str()
        bookmark_count = sum(1 for e in self.entries if e.get("is_bookmark"))
        
        lines = [
            f"# 🎓 Bài Giảng: {self.lecture_title}",
            f"",
            f"- **Môn Học**: 📚 `{self.subject_name}`",
            f"- **Thời Gian**: 📅 {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **Thời Lượng**: ⏱️ {duration_str}",
            f"- **Tổng Số Câu Đã Thu**: {len(self.entries)} câu",
            f"- **Điểm Trọng Tâm Thi Cử (Bookmarks)**: ⭐ {bookmark_count} điểm lưu ý",
            f"",
            f"---",
            f"",
            f"## 🤖 AI Exam Summary Prompt (Prompt Tóm Tắt & Ôn Thi)",
            f"> *Copy prompt này và dán vào ChatGPT / Gemini kèm file Slide bài giảng để nhận bản tóm tắt ôn thi tốt nhất:*",
            f"",
            f"```text",
            f"Dưới đây là toàn bộ transcript bài giảng môn [{self.subject_name}] được ghi lại tại trường đại học ở Hàn Quốc (bao gồm tiếng Hàn gốc, tiếng Anh và tiếng Việt).",
            f"",
            f"Nhiệm vụ của bạn:",
            f"1. Tóm tắt toàn diện nội dung bài học thành các đề mục logic, ngắn gọn, dễ nhớ bằng tiếng Việt.",
            f"2. Trích xuất bảng thuật ngữ chuyên ngành quan trọng (Hàn - Anh - Việt) kèm giải thích chi tiết.",
            f"3. ĐẶC BIỆT CHÚ Ý các câu có đánh dấu [⭐ THI CỬ / QUAN TRỌNG] để dự đoán câu hỏi thi và bài tập.",
            f"4. Viết sơ đồ tư duy hoặc bullet points hệ thống hóa toàn bộ kiến thức của buổi học.",
            f"```",
            f"",
            f"---",
            f"",
            f"## 📝 Transcript Đa Ngữ (Korean → English → Vietnamese)",
            f"",
            f"| # | Giờ | Tiếng Hàn Gốc (Korean) | Tiếng Việt (Vietnamese) | Tiếng Anh (English) |",
            f"|---|-----|------------------------|-------------------------|---------------------|"
        ]
        
        for item in self.entries:
            ko = item['korean'].replace("|", "\\|")
            en = item['english'].replace("|", "\\|")
            vi = item.get('vietnamese', '').replace("|", "\\|")
            
            tag = "⭐ **[THI CỬ]** " if item.get("is_bookmark") else ""
            lines.append(f"| {item['id']} | `{item['timestamp']}` | {tag}**{ko}** | {vi} | {en} |")
            
        lines.append("")
        content = "\n".join(lines)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        return filepath

def re_sanitize(text: str) -> str:
    """Sanitize names"""
    if not text:
        return "General"
    keepcharacters = (' ', '.', '_', '-')
    clean = "".join(c for c in text if c.isalnum() or c in keepcharacters).rstrip()
    return clean.replace(" ", "_") if clean else "General"
