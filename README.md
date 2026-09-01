# 🇰🇷 Korean Live Lecture Translator (실시간 한국어 강의 번역기)

Hệ thống hỗ trợ sinh viên / du học sinh tại Hàn Quốc nghe giảng trực tiếp trong lớp học bằng cách thu âm giọng giáo sư qua Microphone, nhận diện tiếng Hàn và dịch trực tiếp sang tiếng Anh thời gian thực.

---

## ✨ Tính Năng Nổi Bật
1. **Thu âm Microphone trực tiếp**: Bắt trọn vẹn giọng giảng viên từ Laptop Microphone, Micro cài áo (USB/Bluetooth), hoặc Micro điện thoại đặt gần bục giảng.
2. **Offline 100% (Faster-Whisper)**: Chạy hoàn toàn trên máy tính của bạn thông qua CTranslate2 tối ưu hóa CPU Intel Iris Xe / đa nhân, không phụ thuộc vào Wi-Fi giảng đường.
3. **Chế độ Lớp Học (HUD Floating Overlay)**: Cửa sổ phụ đề bán trong suốt ghim nổi trên màn hình, có thể kéo thả đè lên Slide bài giảng (PowerPoint, PDF) mà không che khuất bài học.
4. **Hiển thị Song Ngữ Song Song**:
   - Câu gốc tiếng Hàn (`ko`)
   - Bản dịch tiếng Anh (`en`)
5. **Bộ Từ Điển Môn Học (Glossary Booster)**: Cho phép nhập trước các thuật ngữ chuyên ngành (ví dụ: CNTT, Y khoa, Kinh tế...) để AI nhận diện chính xác tuyệt đối các từ vựng khó.
6. **Tự Động Lưu & Xuất Transcript**:
   - **Markdown (`.md`)**: Định dạng bảng song ngữ sạch đẹp kèm Template Prompt để ném vào ChatGPT/Gemini tóm tắt bài giảng sau giờ học.
   - **Phụ đề (`.srt`)**: Đồng bộ thời gian để ghép vào file ghi âm/video nếu có quay lại.

---

## 🚀 Cách Sử Dụng (Quick Start)

### Cách 1: Chạy 1-Click (Khuyên Dùng)
Chỉ cần nhấp đúp vào file:
👉 `run.bat`

Trình duyệt sẽ tự động mở trang giao diện tại: `http://localhost:8000`

### Cách 2: Chạy qua Terminal / Command Prompt
```bash
cd C:\Users\PC\.gemini\antigravity-ide\scratch\korean-live-translator
python main.py
```

---

## 🎧 Hướng dẫn Tối Ưu Khi Đi Học Trên Lớp

1. **Vị trí Micro**: Đặt laptop hoặc micro không dây hướng về phía giáo sư. Nếu ngồi xa, bạn có thể dùng tai nghe bluetooth/mic kẹp áo đặt gần giáo sư rồi kết nối bluetooth với laptop.
2. **Chọn Micro**: Trong giao diện, tại mục **"Microphone Setup"**, chọn đúng thiết bị micro của bạn.
3. **Kích hoạt HUD Overlay**: Bấm nút **"HUD Overlay"** ở góc phải để mở cửa sổ phụ đề nổi khi đang xem slide bài giảng.
4. **Sau buổi học**: Bấm **"Copy Prompt Tóm Tắt AI"** hoặc **"Xuất Markdown (.md)"** rồi dán vào ChatGPT / Gemini kèm file Slide bài giảng để AI tóm tắt ôn thi.
