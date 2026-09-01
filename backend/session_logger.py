import os
import time
from datetime import datetime
from typing import List, Dict, Any

class SessionLogger:
    def __init__(self, export_dir: str = "transcripts"):
        self.export_dir = export_dir
        os.makedirs(self.export_dir, exist_ok=True)
        
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start = datetime.now()
        self.entries: List[Dict[str, Any]] = []
        self.lecture_title = f"Lecture_{datetime.now().strftime('%Y-%m-%d_%H%M')}"
        
    def start_new_session(self, title: str = None):
        """Reset and start a new lecture recording session"""
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start = datetime.now()
        self.entries = []
        if title and title.strip():
            self.lecture_title = title.strip()
        else:
            self.lecture_title = f"Lecture_{datetime.now().strftime('%Y-%m-%d_%H%M')}"

    def add_entry(self, entry: Dict[str, Any]):
        """Add a translation entry to the session"""
        entry_with_id = {
            "id": len(self.entries) + 1,
            "timestamp": entry.get("timestamp", datetime.now().strftime("%H:%M:%S")),
            "korean": entry.get("korean", "").strip(),
            "english": entry.get("english", "").strip(),
            "duration": entry.get("duration", 0),
            "inference_time": entry.get("inference_time", 0)
        }
        self.entries.append(entry_with_id)
        return entry_with_id

    def get_history(self) -> List[Dict[str, Any]]:
        """Return all logged entries"""
        return self.entries

    def export_markdown(self) -> str:
        """Export lecture transcript as a rich Markdown study document"""
        filename = f"{self.session_id}_{self.lecture_title}.md".replace(" ", "_")
        filepath = os.path.join(self.export_dir, filename)
        
        duration = datetime.now() - self.session_start
        total_seconds = int(duration.total_seconds())
        hrs, rem = divmod(total_seconds, 3600)
        mins, secs = divmod(rem, 60)
        duration_str = f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs > 0 else f"{mins:02d}:{secs:02d}"
        
        lines = [
            f"# 🎓 Lecture Transcript: {self.lecture_title}",
            f"",
            f"- **Date & Time**: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **Duration**: {duration_str}",
            f"- **Total Sentences Captured**: {len(self.entries)}",
            f"- **Source Language**: 🇰🇷 Korean (한국어)",
            f"- **Translated Language**: 🇬🇧 English",
            f"",
            f"---",
            f"",
            f"## 🤖 AI Summary Prompt Template",
            f"> *Copy prompt bên dưới và dán vào ChatGPT / Gemini / Claude kèm theo file Slide bài giảng:*",
            f"",
            f"```text",
            f"Dưới đây là toàn bộ transcript bài giảng được ghi lại trực tiếp tại trường đại học ở Hàn Quốc (tiếng Hàn gốc và bản dịch tiếng Anh).",
            f"Hãy giúp tôi:",
            f"1. Tóm tắt toàn diện nội dung bài giảng thành các đề mục rõ ràng, mạch lạc.",
            f"2. Trích xuất các khái niệm chính, thuật ngữ chuyên ngành quan trọng (kèm giải thích tiếng Hàn - Anh - Việt).",
            f"3. Liệt kê các ví dụ, lưu ý thi hoặc dặn dò của giáo sư nếu có trong bài.",
            f"4. Viết lại bài học dưới dạng sơ đồ tư duy hoặc bullet points dễ ôn tập.",
            f"```",
            f"",
            f"---",
            f"",
            f"## 📝 Transcript Song Ngữ (Korean → English)",
            f"",
            f"| # | Giờ | Tiếng Hàn gốc (Korean) | Tiếng Anh (English Translation) |",
            f"|---|-----|------------------------|---------------------------------|"
        ]
        
        for item in self.entries:
            ko = item['korean'].replace("|", "\\|")
            en = item['english'].replace("|", "\\|")
            lines.append(f"| {item['id']} | `{item['timestamp']}` | **{ko}** | {en} |")
            
        lines.append("")
        content = "\n".join(lines)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        return filepath

    def export_srt(self) -> str:
        """Export as SRT subtitle file"""
        filename = f"{self.session_id}_{self.lecture_title}.srt".replace(" ", "_")
        filepath = os.path.join(self.export_dir, filename)
        
        lines = []
        current_time_sec = 0.0
        
        for item in self.entries:
            dur = max(2.0, float(item.get("duration", 3.0)))
            start_sec = current_time_sec
            end_sec = start_sec + dur
            current_time_sec = end_sec + 0.5
            
            def format_time(sec):
                hrs = int(sec // 3600)
                mins = int((sec % 3600) // 60)
                s = int(sec % 60)
                ms = int((sec - int(sec)) * 1000)
                return f"{hrs:02d}:{mins:02d}:{s:02d},{ms:03d}"
                
            lines.append(str(item['id']))
            lines.append(f"{format_time(start_sec)} --> {format_time(end_sec)}")
            lines.append(f"{item['english']}")
            lines.append(f"({item['korean']})")
            lines.append("")
            
        content = "\n".join(lines)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        return filepath
