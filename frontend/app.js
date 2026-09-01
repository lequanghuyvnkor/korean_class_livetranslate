// Application State
let ws = null;
let isRecording = false;
let sessionStartTime = null;
let sessionTimerInterval = null;
let autoScroll = true;
let currentFontSize = 1.35; // rem
let hudFontSize = 1.5; // rem
let allEntries = [];

// DOM Elements
const recordBtn = document.getElementById("mainRecordBtn");
const recordBtnText = document.getElementById("recordBtnText");
const micStatusIcon = document.getElementById("micStatusIcon");
const audioMonitor = document.getElementById("audioMonitor");
const volumeBadge = document.getElementById("volumeBadge");
const waveformBars = document.querySelectorAll(".waveform-bars .bar");

const livePulseDot = document.getElementById("livePulseDot");
const liveStatusText = document.getElementById("liveStatusText");
const liveKoreanText = document.getElementById("liveKoreanText");
const liveEnglishText = document.getElementById("liveEnglishText");

const transcriptFeed = document.getElementById("transcriptFeed");
const emptyState = document.getElementById("emptyState");
const sentenceCountEl = document.getElementById("sentenceCount");
const sessionTimerEl = document.getElementById("sessionTimer");
const sessionStatusBadge = document.getElementById("sessionStatusBadge");

const deviceSelect = document.getElementById("deviceSelect");
const refreshDevicesBtn = document.getElementById("refreshDevicesBtn");
const modelSelect = document.getElementById("modelSelect");
const vocabPrompt = document.getElementById("vocabPrompt");
const savePromptBtn = document.getElementById("savePromptBtn");
const lectureTitleInput = document.getElementById("lectureTitle");
const newSessionBtn = document.getElementById("newSessionBtn");

const exportMdBtn = document.getElementById("exportMdBtn");
const exportSrtBtn = document.getElementById("exportSrtBtn");
const copyAiPromptBtn = document.getElementById("copyAiPromptBtn");
const searchInput = document.getElementById("searchTranscript");
const autoScrollBtn = document.getElementById("autoScrollToggle");

const fontIncBtn = document.getElementById("fontIncBtn");
const fontDecBtn = document.getElementById("fontDecBtn");
const clearViewBtn = document.getElementById("clearViewBtn");

const hudToggleBtn = document.getElementById("hudToggleBtn");
const hudOverlayContainer = document.getElementById("hudOverlayContainer");
const hudEnglishText = document.getElementById("hudEnglishText");
const hudKoreanText = document.getElementById("hudKoreanText");
const hudCloseBtn = document.getElementById("hudCloseBtn");
const hudOpacitySlider = document.getElementById("hudOpacitySlider");
const hudFontInc = document.getElementById("hudFontInc");
const hudFontDec = document.getElementById("hudFontDec");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    initWebSocket();
    loadDevices();
    setupEventListeners();
});

// WebSocket Connection
function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log("Connected to Live Translation WebSocket");
        showToast("Đã kết nối máy chủ Live Translation!");
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWsMessage(data);
        } catch (e) {
            console.error("Error parsing WS message:", e);
        }
    };
    
    ws.onclose = () => {
        console.log("WebSocket disconnected. Retrying in 2s...");
        setTimeout(initWebSocket, 2000);
    };
}

function handleWsMessage(data) {
    switch (data.type) {
        case "init":
            updateRecordingState(data.is_recording);
            if (data.model_size) modelSelect.value = data.model_size;
            if (data.initial_prompt) vocabPrompt.value = data.initial_prompt;
            if (data.lecture_title) lectureTitleInput.value = data.lecture_title;
            if (data.history && data.history.length > 0) {
                allEntries = data.history;
                renderAllEntries();
            }
            break;
            
        case "volume_level":
            updateVolumeVisualizer(data.level, data.is_recording);
            break;
            
        case "status":
            if (data.status === "translating") {
                liveStatusText.textContent = "AI Translating...";
                livePulseDot.classList.add("active");
            } else if (data.status === "listening") {
                liveStatusText.textContent = "Listening to lecture...";
                livePulseDot.classList.add("active");
            }
            break;
            
        case "translation":
            appendTranslationEntry(data.entry);
            break;
            
        case "state_change":
            updateRecordingState(data.is_recording);
            break;
    }
}

// Visualizer
function updateVolumeVisualizer(level, isRec) {
    if (!isRec) {
        audioMonitor.classList.remove("active");
        micStatusIcon.className = "fa-solid fa-microphone-slash mic-status-icon";
        volumeBadge.textContent = "0%";
        waveformBars.forEach(bar => bar.style.height = "4px");
        return;
    }
    
    audioMonitor.classList.add("active");
    micStatusIcon.className = "fa-solid fa-microphone mic-status-icon active";
    const percent = Math.min(100, Math.round(level * 100));
    volumeBadge.textContent = `${percent}%`;
    
    waveformBars.forEach((bar, idx) => {
        const factor = (idx % 2 === 0 ? 1 : 0.7) * (0.5 + Math.random() * 0.5);
        const barHeight = Math.max(4, Math.min(22, level * 28 * factor));
        bar.style.height = `${barHeight}px`;
    });
}

// Translations Handling
function appendTranslationEntry(entry) {
    allEntries.push(entry);
    
    // Update live hero banner
    liveKoreanText.textContent = entry.korean;
    liveEnglishText.textContent = entry.english;
    
    // Update HUD overlay
    hudKoreanText.textContent = entry.korean;
    hudEnglishText.textContent = entry.english;
    
    // Hide empty state
    if (emptyState) emptyState.style.display = "none";
    
    // Append to transcript list
    const itemEl = createEntryElement(entry);
    transcriptFeed.appendChild(itemEl);
    
    // Update count
    sentenceCountEl.textContent = allEntries.length;
    
    if (autoScroll) {
        transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
    }
}

function createEntryElement(entry) {
    const div = document.createElement("div");
    div.className = "transcript-item";
    div.id = `entry-${entry.id}`;
    div.innerHTML = `
        <div class="t-time">${entry.timestamp}</div>
        <div class="t-korean">${escapeHtml(entry.korean)}</div>
        <div class="t-english">${escapeHtml(entry.english)}</div>
        <div class="t-actions">
            <button class="btn-icon" title="Copy câu này" onclick="copyText('${escapeJs(entry.english)}')">
                <i class="fa-solid fa-copy"></i>
            </button>
        </div>
    `;
    return div;
}

function renderAllEntries() {
    transcriptFeed.innerHTML = "";
    if (allEntries.length === 0) {
        if (emptyState) transcriptFeed.appendChild(emptyState);
        emptyState.style.display = "flex";
    } else {
        allEntries.forEach(entry => {
            transcriptFeed.appendChild(createEntryElement(entry));
        });
        const last = allEntries[allEntries.length - 1];
        liveKoreanText.textContent = last.korean;
        liveEnglishText.textContent = last.english;
        hudKoreanText.textContent = last.korean;
        hudEnglishText.textContent = last.english;
    }
    sentenceCountEl.textContent = allEntries.length;
}

// Event Listeners
function setupEventListeners() {
    // Record button toggle
    recordBtn.addEventListener("click", toggleRecording);
    
    // Refresh Devices
    refreshDevicesBtn.addEventListener("click", loadDevices);
    
    // Model Select
    modelSelect.addEventListener("change", async () => {
        const model = modelSelect.value;
        showToast(`Đang tải model Faster-Whisper [${model}]...`);
        try {
            const res = await fetch("/api/model", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_size: model })
            });
            const data = await res.json();
            if (data.status === "success") {
                showToast(`Đã chuyển sang model Whisper: ${model}`);
            }
        } catch (e) {
            showToast("Lỗi chuyển model");
        }
    });
    
    // Save Prompt
    savePromptBtn.addEventListener("click", async () => {
        const prompt = vocabPrompt.value;
        try {
            await fetch("/api/prompt", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: prompt })
            });
            showToast("Đã lưu từ điển chuyên ngành!");
        } catch (e) {
            showToast("Lỗi lưu từ điển");
        }
    });
    
    // New Session
    newSessionBtn.addEventListener("click", async () => {
        if (confirm("Bắt đầu một phiên ghi bài giảng mới?")) {
            const title = lectureTitleInput.value;
            await fetch("/api/session/new", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: title })
            });
            allEntries = [];
            renderAllEntries();
            resetTimer();
            showToast("Đã tạo phiên học mới!");
        }
    });
    
    // Export Markdown
    exportMdBtn.addEventListener("click", async () => {
        try {
            const res = await fetch("/api/session/export/markdown", { method: "POST" });
            const data = await res.json();
            if (data.download_url) {
                window.open(data.download_url, "_blank");
                showToast(`Đã xuất file Markdown: ${data.filename}`);
            }
        } catch (e) {
            showToast("Lỗi xuất Markdown");
        }
    });
    
    // Export SRT
    exportSrtBtn.addEventListener("click", async () => {
        try {
            const res = await fetch("/api/session/export/srt", { method: "POST" });
            const data = await res.json();
            if (data.download_url) {
                window.open(data.download_url, "_blank");
                showToast(`Đã xuất file Phụ đề: ${data.filename}`);
            }
        } catch (e) {
            showToast("Lỗi xuất SRT");
        }
    });
    
    // Copy AI Prompt
    copyAiPromptBtn.addEventListener("click", copyFullAiPrompt);
    
    // Auto-scroll toggle
    autoScrollBtn.addEventListener("click", () => {
        autoScroll = !autoScroll;
        autoScrollBtn.innerHTML = autoScroll 
            ? '<i class="fa-solid fa-angles-down"></i> Auto-Scroll: ON' 
            : '<i class="fa-solid fa-pause"></i> Auto-Scroll: OFF';
    });
    
    // Search
    searchInput.addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase();
        const items = document.querySelectorAll(".transcript-item");
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(query) ? "grid" : "none";
        });
    });
    
    // Font controls
    fontIncBtn.addEventListener("click", () => {
        currentFontSize = Math.min(2.5, currentFontSize + 0.15);
        liveEnglishText.style.fontSize = `${currentFontSize}rem`;
    });
    fontDecBtn.addEventListener("click", () => {
        currentFontSize = Math.max(0.9, currentFontSize - 0.15);
        liveEnglishText.style.fontSize = `${currentFontSize}rem`;
    });
    clearViewBtn.addEventListener("click", () => {
        liveKoreanText.textContent = "...";
        liveEnglishText.textContent = "...";
    });
    
    // HUD Overlay Controls
    hudToggleBtn.addEventListener("click", toggleHudOverlay);
    hudCloseBtn.addEventListener("click", () => hudOverlayContainer.style.display = "none");
    hudOpacitySlider.addEventListener("input", (e) => {
        hudOverlayContainer.style.background = `rgba(10, 14, 24, ${e.target.value})`;
    });
    hudFontInc.addEventListener("click", () => {
        hudFontSize = Math.min(3.0, hudFontSize + 0.2);
        hudEnglishText.style.fontSize = `${hudFontSize}rem`;
    });
    hudFontDec.addEventListener("click", () => {
        hudFontSize = Math.max(1.0, hudFontSize - 0.2);
        hudEnglishText.style.fontSize = `${hudFontSize}rem`;
    });
    
    // Make HUD draggable
    makeDraggable(hudOverlayContainer);
}

// Recording Toggle
async function toggleRecording() {
    if (!isRecording) {
        const devId = deviceSelect.value ? parseInt(deviceSelect.value) : null;
        try {
            recordBtn.disabled = true;
            const res = await fetch("/api/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ device_id: devId })
            });
            const data = await res.json();
            if (data.status === "started") {
                updateRecordingState(true);
                startTimer();
                showToast("Bắt đầu thu âm bài giảng!");
            }
        } catch (e) {
            showToast("Không thể mở microphone. Kiểm tra cài đặt quyền!");
        } finally {
            recordBtn.disabled = false;
        }
    } else {
        try {
            recordBtn.disabled = true;
            await fetch("/api/stop", { method: "POST" });
            updateRecordingState(false);
            stopTimer();
            showToast("Đã tạm dừng thu âm.");
        } catch (e) {
            showToast("Lỗi dừng thu âm");
        } finally {
            recordBtn.disabled = false;
        }
    }
}

function updateRecordingState(rec) {
    isRecording = rec;
    if (isRecording) {
        recordBtn.classList.add("recording");
        recordBtn.innerHTML = '<i class="fa-solid fa-stop"></i> <span>Stop Listening</span>';
        sessionStatusBadge.textContent = "Recording";
        sessionStatusBadge.classList.add("active");
        liveStatusText.textContent = "Listening to lecture...";
        livePulseDot.classList.add("active");
    } else {
        recordBtn.classList.remove("recording");
        recordBtn.innerHTML = '<i class="fa-solid fa-play"></i> <span>Start Listening</span>';
        sessionStatusBadge.textContent = "Paused";
        sessionStatusBadge.classList.remove("active");
        liveStatusText.textContent = "Paused / Ready";
        livePulseDot.classList.remove("active");
        updateVolumeVisualizer(0, false);
    }
}

// Device list
async function loadDevices() {
    try {
        const res = await fetch("/api/devices");
        const data = await res.json();
        deviceSelect.innerHTML = "";
        
        const defOpt = document.createElement("option");
        defOpt.value = "";
        defOpt.textContent = "Default Microphone (Mặc định)";
        deviceSelect.appendChild(defOpt);
        
        data.devices.forEach(dev => {
            const opt = document.createElement("option");
            opt.value = dev.id;
            opt.textContent = `${dev.name} (${dev.channels}ch)`;
            if (dev.is_default) opt.textContent += " [Default]";
            deviceSelect.appendChild(opt);
        });
        showToast("Đã cập nhật danh sách micro");
    } catch (e) {
        console.error("Error loading devices:", e);
    }
}

// HUD Mode
function toggleHudOverlay() {
    const isVisible = hudOverlayContainer.style.display !== "none";
    hudOverlayContainer.style.display = isVisible ? "none" : "block";
}

function makeDraggable(el) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    const header = el.querySelector(".hud-drag-handle");
    if (header) {
        header.onmousedown = dragMouseDown;
    }
    
    function dragMouseDown(e) {
        e.preventDefault();
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        document.onmousemove = elementDrag;
    }
    
    function elementDrag(e) {
        e.preventDefault();
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        el.style.top = (el.offsetTop - pos2) + "px";
        el.style.left = (el.offsetLeft - pos1) + "px";
        el.style.bottom = "auto";
        el.style.transform = "none";
    }
    
    function closeDragElement() {
        document.onmouseup = null;
        document.onmousemove = null;
    }
}

// AI Prompt Generation
function copyFullAiPrompt() {
    if (allEntries.length === 0) {
        showToast("Chưa có transcript nào để copy!");
        return;
    }
    
    let prompt = `Dưới đây là toàn bộ transcript bài giảng được ghi lại tại trường đại học ở Hàn Quốc (tiếng Hàn gốc và bản dịch tiếng Anh).
Tên bài giảng: ${lectureTitleInput.value}

Nhiệm vụ của bạn:
1. Tóm tắt toàn diện nội dung bài giảng thành các đề mục rõ ràng, dễ hiểu bằng tiếng Việt.
2. Trích xuất danh sách thuật ngữ chuyên ngành quan trọng nhất (kèm giải thích tiếng Hàn - Anh - Việt).
3. Liệt kê các ý quan trọng, ví dụ thực tế hoặc dặn dò thi cử của giáo sư.

---
TRANSCRIPT BÀI GIẢNG:
`;
    
    allEntries.forEach(item => {
        prompt += `[${item.timestamp}] 🇰🇷 ${item.korean}\n    🇬🇧 ${item.english}\n\n`;
    });
    
    navigator.clipboard.writeText(prompt).then(() => {
        showToast("Đã copy toàn bộ Prompt + Transcript vào Clipboard!");
    });
}

// Timer
function startTimer() {
    if (sessionStartTime === null) sessionStartTime = Date.now();
    clearInterval(sessionTimerInterval);
    sessionTimerInterval = setInterval(updateTimer, 1000);
}

function stopTimer() {
    clearInterval(sessionTimerInterval);
}

function resetTimer() {
    stopTimer();
    sessionStartTime = null;
    sessionTimerEl.textContent = "00:00:00";
}

function updateTimer() {
    if (!sessionStartTime) return;
    const diffSec = Math.floor((Date.now() - sessionStartTime) / 1000);
    const hrs = Math.floor(diffSec / 3600);
    const mins = Math.floor((diffSec % 3600) / 60);
    const secs = diffSec % 60;
    sessionTimerEl.textContent = `${pad(hrs)}:${pad(mins)}:${pad(secs)}`;
}

function pad(num) {
    return num.toString().padStart(2, "0");
}

// Helpers
function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.innerHTML = `<i class="fa-solid fa-info-circle"></i> ${msg}`;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3000);
}

function copyText(txt) {
    navigator.clipboard.writeText(txt).then(() => {
        showToast("Đã copy câu dịch!");
    });
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function escapeJs(text) {
    return text.replace(/'/g, "\\'").replace(/"/g, '\\"');
}
