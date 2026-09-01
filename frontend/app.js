// Application State
let ws = null;
let isRecording = false;
let isPaused = false;
let sessionStartTime = null;
let sessionTimerInterval = null;
let autoScroll = true;
let currentFontSize = 1.25; // rem
let hudFontSize = 1.4; // rem
let allEntries = [];
let subjectsList = [];
let currentSubject = "General";

// DOM Elements
const tabLiveBtn = document.getElementById("tabLiveBtn");
const tabLibraryBtn = document.getElementById("tabLibraryBtn");
const liveViewSection = document.getElementById("liveViewSection");
const libraryViewSection = document.getElementById("libraryViewSection");
const libCountBadge = document.getElementById("libCountBadge");

const recordBtn = document.getElementById("mainRecordBtn");
const recordBtnText = document.getElementById("recordBtnText");
const pauseResumeBtn = document.getElementById("pauseResumeBtn");
const quickBookmarkBtn = document.getElementById("quickBookmarkBtn");
const heroBookmarkBtn = document.getElementById("heroBookmarkBtn");
const hudBookmarkBtn = document.getElementById("hudBookmarkBtn");

const micStatusIcon = document.getElementById("micStatusIcon");
const audioMonitor = document.getElementById("audioMonitor");
const volumeBadge = document.getElementById("volumeBadge");
const waveformBars = document.querySelectorAll(".waveform-bars .bar");

const livePulseDot = document.getElementById("livePulseDot");
const liveStatusText = document.getElementById("liveStatusText");
const liveKoreanText = document.getElementById("liveKoreanText");
const liveVietnameseText = document.getElementById("liveVietnameseText");
const liveEnglishText = document.getElementById("liveEnglishText");

const transcriptFeed = document.getElementById("transcriptFeed");
const emptyState = document.getElementById("emptyState");
const sentenceCountEl = document.getElementById("sentenceCount");
const bookmarkCountEl = document.getElementById("bookmarkCount");
const sessionTimerEl = document.getElementById("sessionTimer");

const subjectSelect = document.getElementById("subjectSelect");
const lectureTitleInput = document.getElementById("lectureTitle");
const newSessionBtn = document.getElementById("newSessionBtn");
const openAddSubjectModalBtn = document.getElementById("openAddSubjectModalBtn");

const deviceSelect = document.getElementById("deviceSelect");
const refreshDevicesBtn = document.getElementById("refreshDevicesBtn");
const btnModeMic = document.getElementById("btnModeMic");
const btnModeOnline = document.getElementById("btnModeOnline");
const openSoundSettingsBtn = document.getElementById("openSoundSettingsBtn");

const modelSelect = document.getElementById("modelSelect");
const vocabPrompt = document.getElementById("vocabPrompt");
const savePromptBtn = document.getElementById("savePromptBtn");

const exportMdBtn = document.getElementById("exportMdBtn");
const copyAiPromptBtn = document.getElementById("copyAiPromptBtn");
const searchInput = document.getElementById("searchTranscript");
const autoScrollBtn = document.getElementById("autoScrollToggle");

const fontIncBtn = document.getElementById("fontIncBtn");
const fontDecBtn = document.getElementById("fontDecBtn");
const clearViewBtn = document.getElementById("clearViewBtn");

const hudToggleBtn = document.getElementById("hudToggleBtn");
const hudOverlayContainer = document.getElementById("hudOverlayContainer");
const hudVietnameseText = document.getElementById("hudVietnameseText");
const hudEnglishText = document.getElementById("hudEnglishText");
const hudKoreanText = document.getElementById("hudKoreanText");
const hudCloseBtn = document.getElementById("hudCloseBtn");
const hudOpacitySlider = document.getElementById("hudOpacitySlider");
const hudFontInc = document.getElementById("hudFontInc");
const hudFontDec = document.getElementById("hudFontDec");

// Library elements
const libSubjectFilter = document.getElementById("libSubjectFilter");
const lecturesGrid = document.getElementById("lecturesGrid");
const globalAudioPlayer = document.getElementById("globalAudioPlayer");
const mainAudioElement = document.getElementById("mainAudioElement");
const playerLectureTitle = document.getElementById("playerLectureTitle");
const playerSubjectTitle = document.getElementById("playerSubjectTitle");
const closePlayerBtn = document.getElementById("closePlayerBtn");

// Modal elements
const addSubjectModal = document.getElementById("addSubjectModal");
const closeAddSubjectModalBtn = document.getElementById("closeAddSubjectModalBtn");
const cancelSubjectBtn = document.getElementById("cancelSubjectBtn");
const saveNewSubjectBtn = document.getElementById("saveNewSubjectBtn");
const newSubjectName = document.getElementById("newSubjectName");
const newSubjectGlossary = document.getElementById("newSubjectGlossary");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    initWebSocket();
    loadSubjects();
    loadDevices();
    loadLecturesArchive();
    setupEventListeners();
    setupHotkeys();
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
        setTimeout(initWebSocket, 2000);
    };
}

function handleWsMessage(data) {
    switch (data.type) {
        case "init":
            updateRecordingState(data.is_recording, data.is_paused || false);
            if (data.model_size) modelSelect.value = data.model_size;
            if (data.initial_prompt) vocabPrompt.value = data.initial_prompt;
            if (data.lecture_title) lectureTitleInput.value = data.lecture_title;
            if (data.subject) {
                currentSubject = data.subject;
                subjectSelect.value = data.subject;
            }
            if (data.history && data.history.length > 0) {
                allEntries = data.history;
                renderAllEntries();
            }
            break;
            
        case "volume_level":
            updateVolumeVisualizer(data.level, data.is_recording && !isPaused);
            break;
            
        case "status":
            if (!isPaused) {
                if (data.status === "translating") {
                    liveStatusText.textContent = "AI Translating (Hàn → Việt/Anh)...";
                    livePulseDot.className = "pulse-dot active";
                } else if (data.status === "listening") {
                    liveStatusText.textContent = `Đang nghe bài giảng: ${currentSubject}...`;
                    livePulseDot.className = "pulse-dot active";
                }
            }
            break;
            
        case "translation":
            appendTranslationEntry(data.entry);
            break;
            
        case "state_change":
            updateRecordingState(data.is_recording, data.is_paused || false);
            if (!data.is_recording) {
                // Refresh library when stopped
                loadLecturesArchive();
            }
            break;
            
        case "bookmark_update":
        case "bookmark_toggle":
            updateEntryBookmark(data.entry ? data.entry.id : data.id, data.entry ? data.entry.is_bookmark : data.is_bookmark);
            break;
    }
}

// Visualizer
function updateVolumeVisualizer(level, active) {
    if (!active) {
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

// Translation Handling
function appendTranslationEntry(entry) {
    allEntries.push(entry);
    
    // Update live hero banner
    liveKoreanText.textContent = entry.korean;
    liveVietnameseText.textContent = entry.vietnamese || entry.english;
    liveEnglishText.textContent = entry.english;
    
    // Update HUD overlay
    hudKoreanText.textContent = entry.korean;
    hudVietnameseText.textContent = entry.vietnamese || entry.english;
    hudEnglishText.textContent = entry.english;
    
    // Hide empty state
    if (emptyState) emptyState.style.display = "none";
    
    // Append to transcript list
    const itemEl = createEntryElement(entry);
    transcriptFeed.appendChild(itemEl);
    
    updateCounts();
    
    if (autoScroll) {
        transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
    }
}

function createEntryElement(entry) {
    const div = document.createElement("div");
    div.className = `transcript-item ${entry.is_bookmark ? 'bookmarked' : ''}`;
    div.id = `entry-${entry.id}`;
    
    const starClass = entry.is_bookmark ? 'btn-star active' : 'btn-star';
    
    div.innerHTML = `
        <div class="t-time">${entry.timestamp}</div>
        <div class="t-korean">${escapeHtml(entry.korean)}</div>
        <div class="t-vietnamese">${escapeHtml(entry.vietnamese || entry.english)}</div>
        <div class="t-english">${escapeHtml(entry.english)}</div>
        <div class="t-actions">
            <button class="btn-icon ${starClass}" title="Đánh dấu điểm thi" onclick="toggleSentenceBookmark(${entry.id})">
                <i class="fa-solid fa-star"></i>
            </button>
            <button class="btn-icon" title="Copy câu này" onclick="copyText('${escapeJs(entry.vietnamese || entry.english)}')">
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
        liveVietnameseText.textContent = last.vietnamese || last.english;
        liveEnglishText.textContent = last.english;
        hudKoreanText.textContent = last.korean;
        hudVietnameseText.textContent = last.vietnamese || last.english;
        hudEnglishText.textContent = last.english;
    }
    updateCounts();
}

function updateCounts() {
    sentenceCountEl.textContent = allEntries.length;
    const bCount = allEntries.filter(e => e.is_bookmark).length;
    bookmarkCountEl.textContent = `${bCount} ⭐`;
}

// Bookmarking
async function bookmarkLastSentence() {
    if (allEntries.length === 0) return;
    try {
        const res = await fetch("/api/bookmark/last", { method: "POST" });
        const data = await res.json();
        if (data.status === "success") {
            updateEntryBookmark(data.entry.id, true);
            showToast("⭐ Đã đánh dấu điểm thi cử quan trọng!");
        }
    } catch (e) {}
}

async function toggleSentenceBookmark(id) {
    try {
        const res = await fetch(`/api/bookmark/${id}`, { method: "POST" });
        const data = await res.json();
        if (data.status === "success") {
            updateEntryBookmark(id, data.is_bookmark);
        }
    } catch (e) {}
}

function updateEntryBookmark(id, isBookmarked) {
    const item = allEntries.find(e => e.id === id);
    if (item) item.is_bookmark = isBookmarked;
    
    const el = document.getElementById(`entry-${id}`);
    if (el) {
        if (isBookmarked) el.classList.add("bookmarked");
        else el.classList.remove("bookmarked");
        
        const starBtn = el.querySelector(".btn-star");
        if (starBtn) {
            starBtn.className = isBookmarked ? "btn-icon btn-star active" : "btn-icon btn-star";
        }
    }
    updateCounts();
}

// Subjects Management
async function loadSubjects() {
    try {
        const res = await fetch("/api/subjects");
        const data = await res.json();
        subjectsList = data.subjects || [];
        
        subjectSelect.innerHTML = "";
        libSubjectFilter.innerHTML = '<option value="">Tất Cả Môn Học</option>';
        
        subjectsList.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.name;
            opt.textContent = s.name;
            subjectSelect.appendChild(opt);
            
            const optFilter = document.createElement("option");
            optFilter.value = s.name;
            optFilter.textContent = s.name;
            libSubjectFilter.appendChild(optFilter);
        });
        
        // Populate glossary for current selection
        updateGlossaryFromSelection();
    } catch (e) {
        console.error("Error loading subjects:", e);
    }
}

function updateGlossaryFromSelection() {
    const selectedName = subjectSelect.value;
    currentSubject = selectedName;
    const sub = subjectsList.find(s => s.name === selectedName);
    if (sub && sub.glossary) {
        vocabPrompt.value = sub.glossary;
    }
}

// Lectures Archive (Library View)
async function loadLecturesArchive() {
    try {
        const res = await fetch("/api/lectures");
        const data = await res.json();
        const lectures = data.lectures || [];
        
        libCountBadge.textContent = lectures.length;
        renderLecturesGrid(lectures);
    } catch (e) {
        console.error("Error loading archive:", e);
    }
}

function renderLecturesGrid(lectures) {
    lecturesGrid.innerHTML = "";
    const filterSubject = libSubjectFilter.value;
    
    const filtered = filterSubject 
        ? lectures.filter(l => l.subject === filterSubject || l.subject.includes(filterSubject))
        : lectures;
        
    if (filtered.length === 0) {
        lecturesGrid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <i class="fa-solid fa-folder-open"></i>
                <p>Chưa có file ghi âm nào cho môn học này. Hãy bắt đầu thu âm bài giảng đầu tiên!</p>
            </div>
        `;
        return;
    }
    
    filtered.forEach(lec => {
        const card = document.createElement("div");
        card.className = "lecture-card";
        
        const audioBtn = lec.has_audio 
            ? `<button class="btn btn-sm btn-accent" onclick="playAudio('${lec.audio_url}', '${escapeJs(lec.title)}', '${escapeJs(lec.subject)}')"><i class="fa-solid fa-play"></i> Nghe Ghi Âm (.wav)</button>`
            : `<span class="badge">Không có audio</span>`;
            
        card.innerHTML = `
            <div class="lecture-card-header">
                <div>
                    <h3 style="font-size: 1.05rem; font-weight: 700; margin-bottom: 0.2rem;">${escapeHtml(lec.title)}</h3>
                    <span style="font-size: 0.75rem; color: var(--text-dim);"><i class="fa-regular fa-clock"></i> ${lec.date}</span>
                </div>
                <span class="lecture-subject-tag">${escapeHtml(lec.subject)}</span>
            </div>
            <div class="lecture-stats">
                <div><strong>⏱️ ${lec.duration}</strong><br><span style="color: var(--text-dim);">Thời lượng</span></div>
                <div><strong>📝 ${lec.sentence_count}</strong><br><span style="color: var(--text-dim);">Số câu</span></div>
                <div><strong class="text-gold">⭐ ${lec.bookmark_count}</strong><br><span style="color: var(--text-dim);">Điểm thi</span></div>
            </div>
            <div class="lecture-actions">
                ${audioBtn}
                <a href="${lec.md_download_url}" target="_blank" class="btn btn-sm btn-outline"><i class="fa-brands fa-markdown"></i> Tải .md</a>
            </div>
        `;
        lecturesGrid.appendChild(card);
    });
}

function playAudio(url, title, subject) {
    globalAudioPlayer.style.display = "flex";
    playerLectureTitle.textContent = title;
    playerSubjectTitle.textContent = `Môn: ${subject}`;
    mainAudioElement.src = url;
    mainAudioElement.play();
}

// Event Listeners
function setupEventListeners() {
    // Tab Switchers
    tabLiveBtn.addEventListener("click", () => {
        tabLiveBtn.classList.add("active");
        tabLibraryBtn.classList.remove("active");
        liveViewSection.style.display = "grid";
        libraryViewSection.style.display = "none";
    });
    
    tabLibraryBtn.addEventListener("click", () => {
        tabLibraryBtn.classList.add("active");
        tabLiveBtn.classList.remove("active");
        liveViewSection.style.display = "none";
        libraryViewSection.style.display = "block";
        loadLecturesArchive();
    });
    
    libSubjectFilter.addEventListener("change", () => loadLecturesArchive());
    closePlayerBtn.addEventListener("click", () => {
        mainAudioElement.pause();
        globalAudioPlayer.style.display = "none";
    });
    
    // Subject Selection
    subjectSelect.addEventListener("change", updateGlossaryFromSelection);
    
    // Add Subject Modal
    openAddSubjectModalBtn.addEventListener("click", () => addSubjectModal.style.display = "flex");
    closeAddSubjectModalBtn.addEventListener("click", () => addSubjectModal.style.display = "none");
    cancelSubjectBtn.addEventListener("click", () => addSubjectModal.style.display = "none");
    
    saveNewSubjectBtn.addEventListener("click", async () => {
        const name = newSubjectName.value.trim();
        const glossary = newSubjectGlossary.value.trim();
        if (!name) {
            showToast("Vui lòng nhập tên môn học!");
            return;
        }
        
        try {
            await fetch("/api/subjects", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: name, glossary: glossary })
            });
            addSubjectModal.style.display = "none";
            newSubjectName.value = "";
            newSubjectGlossary.value = "";
            await loadSubjects();
            subjectSelect.value = name;
            updateGlossaryFromSelection();
            showToast(`Đã thêm môn học: ${name}`);
        } catch (e) {
            showToast("Lỗi thêm môn học");
        }
    });
    
    // Record button toggle
    recordBtn.addEventListener("click", toggleRecording);
    pauseResumeBtn.addEventListener("click", togglePauseResume);
    
    // Bookmark buttons
    quickBookmarkBtn.addEventListener("click", bookmarkLastSentence);
    heroBookmarkBtn.addEventListener("click", bookmarkLastSentence);
    hudBookmarkBtn.addEventListener("click", bookmarkLastSentence);
    
    // Refresh Devices
    refreshDevicesBtn.addEventListener("click", loadDevices);
    
    // Preset Mode Buttons
    btnModeMic.addEventListener("click", () => {
        btnModeMic.classList.add("active");
        btnModeOnline.classList.remove("active");
        deviceSelect.value = "";
        showToast("🎙️ Đã chuyển sang Chế độ Giảng Đường (Thu giọng giáo sư qua Micro)");
    });

    btnModeOnline.addEventListener("click", async () => {
        btnModeOnline.classList.add("active");
        btnModeMic.classList.remove("active");
        
        let foundIndex = -1;
        for (let i = 0; i < deviceSelect.options.length; i++) {
            const text = deviceSelect.options[i].textContent.toLowerCase();
            if (text.includes("stereo mix") || text.includes("waveout") || text.includes("system audio")) {
                foundIndex = i;
                break;
            }
        }

        if (foundIndex !== -1) {
            deviceSelect.selectedIndex = foundIndex;
            showToast("💻 Đã chọn Chế độ Học Online (Bắt âm thanh Youtube/Zoom)");
        } else {
            showToast("⚠️ Stereo Mix chưa được bật. Đã mở Cài đặt Windows để bạn bật trong 10s!");
            try {
                await fetch("/api/open_sound_settings", { method: "POST" });
            } catch (e) {}
        }
    });

    openSoundSettingsBtn.addEventListener("click", async () => {
        try {
            await fetch("/api/open_sound_settings", { method: "POST" });
            showToast("Đã mở Cài đặt Windows! Nhấp chuột phải vào Stereo Mix chọn Enable.");
        } catch (e) {}
    });
    
    // Model Select
    modelSelect.addEventListener("change", async () => {
        const model = modelSelect.value;
        showToast(`Đang tải model Whisper [${model}]...`);
        try {
            const res = await fetch("/api/model", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_size: model })
            });
            const data = await res.json();
            if (data.status === "success") {
                showToast(`Đã chuyển sang model: ${model}`);
            }
        } catch (e) {
            showToast("Lỗi chuyển model");
        }
    });
    
    // Save Prompt
    savePromptBtn.addEventListener("click", async () => {
        const prompt = vocabPrompt.value;
        const currentSubName = subjectSelect.value;
        
        try {
            await fetch("/api/prompt", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: prompt })
            });
            // Also update subject glossary
            await fetch("/api/subjects", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: currentSubName, glossary: prompt })
            });
            showToast("Đã lưu từ điển môn học!");
        } catch (e) {
            showToast("Lỗi lưu từ điển");
        }
    });
    
    // New Session
    newSessionBtn.addEventListener("click", async () => {
        if (confirm("Bắt đầu buổi học mới?")) {
            const title = lectureTitleInput.value;
            const subject = subjectSelect.value;
            await fetch("/api/session/new", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: title, subject: subject })
            });
            allEntries = [];
            renderAllEntries();
            resetTimer();
            showToast("Đã tạo buổi học mới!");
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
    
    // Copy AI Prompt
    copyAiPromptBtn.addEventListener("click", copyFullAiPrompt);
    
    // Auto-scroll
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
        liveVietnameseText.style.fontSize = `${currentFontSize}rem`;
    });
    fontDecBtn.addEventListener("click", () => {
        currentFontSize = Math.max(0.9, currentFontSize - 0.15);
        liveVietnameseText.style.fontSize = `${currentFontSize}rem`;
    });
    clearViewBtn.addEventListener("click", () => {
        liveKoreanText.textContent = "...";
        liveVietnameseText.textContent = "...";
        liveEnglishText.textContent = "...";
    });
    
    // HUD
    hudToggleBtn.addEventListener("click", toggleHudOverlay);
    hudCloseBtn.addEventListener("click", () => hudOverlayContainer.style.display = "none");
    hudOpacitySlider.addEventListener("input", (e) => {
        hudOverlayContainer.style.background = `rgba(10, 14, 26, ${e.target.value})`;
    });
    hudFontInc.addEventListener("click", () => {
        hudFontSize = Math.min(3.0, hudFontSize + 0.2);
        hudVietnameseText.style.fontSize = `${hudFontSize}rem`;
    });
    hudFontDec.addEventListener("click", () => {
        hudFontSize = Math.max(1.0, hudFontSize - 0.2);
        hudVietnameseText.style.fontSize = `${hudFontSize}rem`;
    });
    makeDraggable(hudOverlayContainer);
}

function setupHotkeys() {
    document.addEventListener("keydown", (e) => {
        // Press B or Space (when not typing in an input) to bookmark
        if (e.key === "b" || e.key === "B") {
            const activeTag = document.activeElement.tagName.toLowerCase();
            if (activeTag !== "input" && activeTag !== "textarea") {
                e.preventDefault();
                bookmarkLastSentence();
            }
        }
    });
}

// Recording & Pause Toggle
async function toggleRecording() {
    if (!isRecording) {
        const devId = deviceSelect.value ? parseInt(deviceSelect.value) : null;
        const subject = subjectSelect.value;
        const title = lectureTitleInput.value;
        
        try {
            recordBtn.disabled = true;
            const res = await fetch("/api/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ device_id: devId, subject: subject, title: title })
            });
            const data = await res.json();
            if (data.status === "started") {
                updateRecordingState(true, false);
                startTimer();
                showToast(`Bắt đầu thu âm & dịch môn: ${subject}!`);
            }
        } catch (e) {
            showToast("Không thể mở microphone.");
        } finally {
            recordBtn.disabled = false;
        }
    } else {
        try {
            recordBtn.disabled = true;
            const res = await fetch("/api/stop", { method: "POST" });
            const data = await res.json();
            updateRecordingState(false, false);
            stopTimer();
            showToast("Đã lưu bài giảng và file ghi âm WAV!");
        } catch (e) {
            showToast("Lỗi dừng thu âm");
        } finally {
            recordBtn.disabled = false;
        }
    }
}

async function togglePauseResume() {
    if (!isRecording) return;
    
    if (!isPaused) {
        try {
            await fetch("/api/pause", { method: "POST" });
            updateRecordingState(true, true);
            showToast("Đã tạm dừng nghe.");
        } catch (e) {}
    } else {
        try {
            await fetch("/api/resume", { method: "POST" });
            updateRecordingState(true, false);
            showToast("Tiếp tục nghe giảng...");
        } catch (e) {}
    }
}

function updateRecordingState(rec, paused) {
    isRecording = rec;
    isPaused = paused;
    
    if (isRecording) {
        pauseResumeBtn.style.display = "inline-flex";
        recordBtn.classList.add("recording");
        recordBtn.innerHTML = '<i class="fa-solid fa-stop"></i> <span>Stop & Save WAV</span>';
        
        if (isPaused) {
            pauseResumeBtn.innerHTML = '<i class="fa-solid fa-play"></i> <span>Resume</span>';
            pauseResumeBtn.className = "btn btn-accent";
            liveStatusText.textContent = "Paused (Click Resume để tiếp tục)";
            livePulseDot.className = "pulse-dot";
            updateVolumeVisualizer(0, false);
        } else {
            pauseResumeBtn.innerHTML = '<i class="fa-solid fa-pause"></i> <span>Pause</span>';
            pauseResumeBtn.className = "btn btn-secondary";
            liveStatusText.textContent = `Đang nghe bài giảng: ${currentSubject}...`;
            livePulseDot.className = "pulse-dot active";
        }
    } else {
        pauseResumeBtn.style.display = "none";
        recordBtn.classList.remove("recording");
        recordBtn.innerHTML = '<i class="fa-solid fa-play"></i> <span>Start Listening</span>';
        liveStatusText.textContent = "Ready to listen";
        livePulseDot.className = "pulse-dot";
        updateVolumeVisualizer(0, false);
    }
}

// Devices
async function loadDevices() {
    try {
        const res = await fetch("/api/devices");
        const data = await res.json();
        deviceSelect.innerHTML = "";
        
        const defOpt = document.createElement("option");
        defOpt.value = "";
        defOpt.textContent = "Default Microphone (Mặc định hệ thống)";
        deviceSelect.appendChild(defOpt);
        
        if (data.devices && Array.isArray(data.devices)) {
            data.devices.forEach(dev => {
                const opt = document.createElement("option");
                opt.value = dev.id;
                opt.textContent = `${dev.name}`;
                if (dev.is_default) opt.textContent += " [Default]";
                deviceSelect.appendChild(opt);
            });
        }
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
    if (header) header.onmousedown = dragMouseDown;
    
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
    
    const subject = subjectSelect.value;
    const title = lectureTitleInput.value;
    
    let prompt = `Dưới đây là toàn bộ transcript bài giảng môn [${subject}] - [${title}] được ghi lại tại trường đại học ở Hàn Quốc (bao gồm tiếng Hàn gốc, tiếng Việt và tiếng Anh).

Nhiệm vụ của bạn:
1. Tóm tắt toàn diện nội dung bài học thành các đề mục logic, ngắn gọn, dễ nhớ bằng tiếng Việt.
2. Trích xuất bảng thuật ngữ chuyên ngành quan trọng (Hàn - Anh - Việt) kèm giải thích chi tiết.
3. ĐẶC BIỆT CHÚ Ý các câu có đánh dấu [⭐ THI CỬ / QUAN TRỌNG] để dự đoán câu hỏi thi và bài tập.
4. Viết sơ đồ tư duy hoặc bullet points hệ thống hóa toàn bộ kiến thức của buổi học.

---
TRANSCRIPT BÀI GIẢNG:
`;
    
    allEntries.forEach(item => {
        const tag = item.is_bookmark ? "[⭐ THI CỬ / QUAN TRỌNG] " : "";
        prompt += `[${item.timestamp}] ${tag}\n   🇰🇷 ${item.korean}\n   🇻🇳 ${item.vietnamese || item.english}\n\n`;
    });
    
    navigator.clipboard.writeText(prompt).then(() => {
        showToast("Đã copy toàn bộ Prompt Ôn Thi + Transcript vào Clipboard!");
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
    if (!sessionStartTime || isPaused) return;
    const diffSec = Math.floor((Date.now() - sessionStartTime) / 1000);
    const hrs = Math.floor(diffSec / 3600);
    const mins = Math.floor((diffSec % 3600) / 60);
    const secs = diffSec % 60;
    sessionTimerEl.textContent = `${pad(hrs)}:${pad(mins)}:${pad(secs)}`;
}

function pad(num) {
    return num.toString().padStart(2, "0");
}

function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.innerHTML = `<i class="fa-solid fa-circle-info"></i> ${msg}`;
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
    div.textContent = text || "";
    return div.innerHTML;
}

function escapeJs(text) {
    return (text || "").replace(/'/g, "\\'").replace(/"/g, '\\"');
}
