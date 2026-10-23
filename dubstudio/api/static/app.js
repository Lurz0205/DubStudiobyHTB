// DubStudio Pro Studio Frontend Engine (25 Vieneu Voices & Draggable/Resizable Subtitle Box)
let currentJobId = null;
let segmentsData = [];
let videoDuration = 60.0;
let pxPerSec = 40;
let eventSource = null;

// Official 25 Vieneu Voices
const VIENEU_VOICES = [
  { name: "Minh Đức", gender: "male", region: "Bắc" },
  { name: "Hải Đăng", gender: "male", region: "Nam" },
  { name: "Quốc Tuấn", gender: "male", region: "Bắc" },
  { name: "Quang Sơn", gender: "male", region: "Trung" },
  { name: "Thiện Minh", gender: "male", region: "Bắc" },
  { name: "Minh Triết", gender: "male", region: "Nam" },
  { name: "Đức Trí", gender: "male", region: "Bắc" },
  { name: "Thái Sơn", gender: "male", region: "Bắc" },
  { name: "Xuân Vĩnh", gender: "male", region: "Bắc" },
  { name: "Thanh Bình", gender: "male", region: "Trung" },
  { name: "Phạm Tuyên", gender: "male", region: "Bắc" },
  { name: "Thiền Tâm Đức", gender: "male", region: "Bắc" },
  { name: "Adam", gender: "male", region: "Bắc" },
  { name: "Adam bựa", gender: "male", region: "Bắc" },
  { name: "Quỳnh Anh", gender: "female", region: "Bắc" },
  { name: "Mai Anh", gender: "female", region: "Bắc" },
  { name: "Trúc Ly", gender: "female", region: "Nam" },
  { name: "Thùy Dung", gender: "female", region: "Bắc" },
  { name: "Ngọc Huyền", gender: "female", region: "Bắc" },
  { name: "Ngọc Trân", gender: "female", region: "Nam" },
  { name: "Ngọc Linh", gender: "female", region: "Bắc" },
  { name: "Đoan Trang", gender: "female", region: "Bắc" },
  { name: "Thục Đoan", gender: "female", region: "Nam" },
  { name: "Mỹ Duyên", gender: "female", region: "Nam" },
  { name: "Kim Thanh", gender: "female", region: "Bắc" },
];

function buildVoiceSelectHTML(selectedVoice) {
  let maleOpts = '';
  let femaleOpts = '';
  VIENEU_VOICES.forEach(v => {
    const isSel = (v.name === selectedVoice) ? 'selected' : '';
    const opt = `<option value="${v.name}" ${isSel}>${v.name} (${v.region})</option>`;
    if (v.gender === 'male') maleOpts += opt;
    else femaleOpts += opt;
  });
  return `<optgroup label="👨 Giọng Nam">${maleOpts}</optgroup><optgroup label="👩 Giọng Nữ">${femaleOpts}</optgroup>`;
}

const videoPlayer = document.getElementById("preview-player");
const videoWrapper = document.getElementById("video-wrapper");
const subtitleBox = document.getElementById("subtitle-box");
const subtitleText = document.getElementById("subtitle-text");
const subDragHandle = document.getElementById("sub-drag-handle");
const playhead = document.getElementById("timeline-playhead");
const timecodeEl = document.getElementById("tl-timecode");
const timelineCanvas = document.getElementById("timeline-canvas");
const trackVoice = document.getElementById("track-voice");
const ruler = document.getElementById("timeline-ruler");

// Tab Navigation
document.querySelectorAll(".nav-item").forEach(item => {
  item.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach(i => i.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

    item.classList.add("active");
    const tabName = item.getAttribute("data-tab");
    document.getElementById(`tab-${tabName}`).classList.add("active");

    if (tabName === "settings") loadSettings();
    if (tabName === "dub") refreshJobs();
  });
});

function formatTime(secs) {
  if (isNaN(secs) || secs < 0) secs = 0;
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  const ms = Math.floor((secs - Math.floor(secs)) * 100);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
}

// -------------------------------------------------------------
// 1. JOB SELECTION & LOADING
// -------------------------------------------------------------
async function refreshJobs() {
  try {
    const res = await fetch("/api/jobs");
    const data = await res.json();
    const select = document.getElementById("job-select");
    select.innerHTML = '<option value="">-- Chọn tác vụ video --</option>';

    data.jobs.forEach(j => {
      const opt = document.createElement("option");
      opt.value = j.id;
      opt.textContent = `${j.id} ${j.has_video ? "✅ (Đã xuất)" : ""}`;
      select.appendChild(opt);
    });

    if (data.jobs.length > 0 && !currentJobId) {
      select.value = data.jobs[0].id;
      selectJob(data.jobs[0].id);
    }
  } catch (err) {
    console.error("Lỗi tải danh sách job:", err);
  }
}

document.getElementById("job-select").addEventListener("change", (e) => {
  if (e.target.value) selectJob(e.target.value);
});

async function selectJob(jobId) {
  currentJobId = jobId;
  document.getElementById("current-job-title").textContent = `Tác vụ: ${jobId}`;

  videoPlayer.src = `/api/jobs/${jobId}/preview-video`;
  videoPlayer.load();

  loadSubtitleStyle(jobId);
  await loadSegments(jobId);
}

videoPlayer.addEventListener("loadedmetadata", () => {
  videoDuration = videoPlayer.duration || 60.0;
  renderTimeline();
});

videoPlayer.addEventListener("timeupdate", () => {
  const cur = videoPlayer.currentTime;
  const total = videoPlayer.duration || videoDuration;
  timecodeEl.textContent = `${formatTime(cur)} / ${formatTime(total)}`;

  const leftPx = cur * pxPerSec;
  playhead.style.left = `${leftPx}px`;

  let activeSeg = null;
  for (const s of segmentsData) {
    if (cur >= s.start && cur <= s.end) {
      activeSeg = s;
      break;
    }
  }

  if (activeSeg) {
    const rawText = activeSeg.vi_text || activeSeg.src_text || "";
    subtitleText.textContent = getSubtitleSliceForTime(rawText, activeSeg.start, activeSeg.end, cur);
    subtitleBox.style.display = "flex";
    highlightActiveSegment(activeSeg.id);
  } else {
    subtitleText.textContent = "...";
  }
});

function getSubtitleSliceForTime(text, start, end, curTime) {
  if (!text) return "";
  const words = text.trim().split(/\s+/);
  if (words.length <= 15) return text;

  const punctChars = [".", "!", "?", ",", ";", ":", "—", "-", "…"];
  const conjunctions = new Set(["và", "nhưng", "mà", "nên", "thì", "rồi", "để", "bởi", "do", "vì", "nếu", "tuy", "dù", "hoặc", "hay", "khi"]);
  const slices = [];
  let cur = 0;
  const total = words.length;

  while (cur < total) {
    const rem = total - cur;
    if (rem <= 17) {
      if (rem <= 15) {
        slices.push(words.slice(cur));
        break;
      } else {
        const half = Math.floor(rem / 2);
        slices.push(words.slice(cur, cur + half));
        slices.push(words.slice(cur + half));
        break;
      }
    } else {
      let targetK = cur + 12;
      let minK = cur + 8;
      let maxK = Math.min(total - 4, cur + 17);
      let bestK = targetK;
      let bestScore = -999;
      for (let k = minK; k <= maxK; k++) {
        const prevW = words[k - 1];
        const nextW = (words[k] || "").toLowerCase();
        let score = 0;
        if (punctChars.some(p => prevW.endsWith(p))) score += 8;
        if (conjunctions.has(nextW)) score += 5;
        score -= Math.abs(k - targetK) * 0.6;
        if (score > bestScore) {
          bestScore = score;
          bestK = k;
        }
      }
      slices.push(words.slice(cur, bestK));
      cur = bestK;
    }
  }

  const totalDur = Math.max(0.2, end - start);
  let runningStart = start;
  for (let i = 0; i < slices.length; i++) {
    const slWords = slices[i];
    const durRatio = slWords.length / total;
    const slEnd = (i === slices.length - 1) ? end : runningStart + (totalDur * durRatio);
    if (curTime >= runningStart && curTime <= slEnd) {
      return slWords.join(" ");
    }
    runningStart = slEnd;
  }
  return text;
}


function highlightActiveSegment(id) {
  document.querySelectorAll(".segment-item").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".timeline-clip").forEach(el => el.classList.remove("selected"));

  const segEl = document.getElementById(`seg-item-${id}`);
  if (segEl) segEl.classList.add("active");
  const clipEl = document.getElementById(`clip-${id}`);
  if (clipEl) clipEl.classList.add("selected");
}

// -------------------------------------------------------------
// 2. DRAGGABLE & RESIZABLE SUBTITLE BOX + STYLING
// -------------------------------------------------------------
const fontNameSelect = document.getElementById("sub-font-name");
const fontSizeInput = document.getElementById("sub-font-size");
const colorPrimaryInput = document.getElementById("sub-color-primary");
const colorOutlineInput = document.getElementById("sub-color-outline");
const colorBgInput = document.getElementById("sub-color-bg");
const bgOpacityInput = document.getElementById("sub-bg-opacity");
const boxRadiusInput = document.getElementById("sub-box-radius");
const boxBlurInput = document.getElementById("sub-box-blur");
const textAlignSelect = document.getElementById("sub-text-align");

function hexToRgba(hex, alphaPercent) {
  hex = hex.replace("#", "");
  if (hex.length === 3) hex = hex.split("").map(c => c + c).join("");
  const r = parseInt(hex.substring(0, 2), 16) || 0;
  const g = parseInt(hex.substring(2, 4), 16) || 0;
  const b = parseInt(hex.substring(4, 6), 16) || 0;
  return `rgba(${r}, ${g}, ${b}, ${alphaPercent / 100})`;
}

function applyStyleToSubtitleBox() {
  subtitleText.style.fontFamily = fontNameSelect.value;
  subtitleText.style.fontSize = `${fontSizeInput.value}px`;
  subtitleText.style.color = colorPrimaryInput.value;
  subtitleText.style.textAlign = textAlignSelect.value;

  const outline = colorOutlineInput.value;
  subtitleText.style.textShadow = `2px 2px 3px ${outline}, -2px -2px 3px ${outline}, 2px -2px 3px ${outline}, -2px 2px 3px ${outline}`;

  const bgColor = hexToRgba(colorBgInput.value, parseInt(bgOpacityInput.value) || 65);
  subtitleBox.style.backgroundColor = bgColor;
  subtitleBox.style.borderRadius = `${boxRadiusInput.value}px`;
  const blurVal = `${boxBlurInput.value}px`;
  subtitleBox.style.backdropFilter = `blur(${blurVal})`;
  subtitleBox.style.webkitBackdropFilter = `blur(${blurVal})`;
}

let autoSaveStyleTimer = null;
function autoSaveSubtitleStyle() {
  clearTimeout(autoSaveStyleTimer);
  autoSaveStyleTimer = setTimeout(async () => {
    const rect = subtitleBox.getBoundingClientRect();
    const parentRect = videoWrapper.getBoundingClientRect();

    const payload = {
      font_name: fontNameSelect.value,
      font_size: parseInt(fontSizeInput.value) || 22,
      primary_color: colorPrimaryInput.value,
      outline_color: colorOutlineInput.value,
      box_color: hexToRgba(colorBgInput.value, parseInt(bgOpacityInput.value) || 65),
      box_radius: parseInt(boxRadiusInput.value) || 8,
      box_blur: parseInt(boxBlurInput.value) || 6,
      text_align: textAlignSelect.value,
      pos_x: Math.round(rect.left - parentRect.left),
      pos_y: Math.round(rect.top - parentRect.top),
      box_width: Math.round(subtitleBox.offsetWidth),
      box_height: Math.round(subtitleBox.offsetHeight),
    };

    try {
      localStorage.setItem("dubstudio_subtitle_style", JSON.stringify(payload));
    } catch (e) {}

    if (currentJobId) {
      try {
        await fetch(`/api/jobs/${currentJobId}/style`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } catch (err) {}
    }
  }, 400);
}

[fontNameSelect, fontSizeInput, colorPrimaryInput, colorOutlineInput, colorBgInput, bgOpacityInput, boxRadiusInput, boxBlurInput, textAlignSelect].forEach(el => {
  el.addEventListener("input", () => {
    applyStyleToSubtitleBox();
    autoSaveSubtitleStyle();
  });
  el.addEventListener("change", () => {
    applyStyleToSubtitleBox();
    autoSaveSubtitleStyle();
  });
});

// Dragging the Subtitle Box inside Video Wrapper
let isDraggingBox = false;
let dragStartX = 0, dragStartY = 0;
let boxStartLeft = 0, boxStartTop = 0;

subDragHandle.addEventListener("mousedown", (e) => {
  isDraggingBox = true;
  dragStartX = e.clientX;
  dragStartY = e.clientY;

  const rect = subtitleBox.getBoundingClientRect();
  const parentRect = videoWrapper.getBoundingClientRect();

  boxStartLeft = rect.left - parentRect.left;
  boxStartTop = rect.top - parentRect.top;

  subtitleBox.style.bottom = "auto";
  subtitleBox.style.transform = "none";
  subtitleBox.style.left = `${boxStartLeft}px`;
  subtitleBox.style.top = `${boxStartTop}px`;

  e.preventDefault();
});

// Resizing the Subtitle Box
let isResizingBox = false;
let currentResizer = null;
let resizeStartX = 0, resizeStartY = 0;
let resizeStartWidth = 0, resizeStartHeight = 0;

document.querySelectorAll(".sub-resizer").forEach(handle => {
  handle.addEventListener("mousedown", (e) => {
    isResizingBox = true;
    currentResizer = handle.getAttribute("data-handle");
    resizeStartX = e.clientX;
    resizeStartY = e.clientY;

    resizeStartWidth = subtitleBox.offsetWidth;
    resizeStartHeight = subtitleBox.offsetHeight;

    e.stopPropagation();
    e.preventDefault();
  });
});

window.addEventListener("mousemove", (e) => {
  if (isDraggingBox) {
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;

    const maxLeft = videoWrapper.clientWidth - subtitleBox.offsetWidth;
    const maxTop = videoWrapper.clientHeight - subtitleBox.offsetHeight;

    const newLeft = Math.max(0, Math.min(maxLeft, boxStartLeft + dx));
    const newTop = Math.max(0, Math.min(maxTop, boxStartTop + dy));

    subtitleBox.style.left = `${newLeft}px`;
    subtitleBox.style.top = `${newTop}px`;
  } else if (isResizingBox) {
    const dx = e.clientX - resizeStartX;
    const dy = e.clientY - resizeStartY;

    if (currentResizer === "se") {
      subtitleBox.style.width = `${Math.max(120, resizeStartWidth + dx)}px`;
      subtitleBox.style.height = `${Math.max(40, resizeStartHeight + dy)}px`;
    } else if (currentResizer === "sw") {
      subtitleBox.style.width = `${Math.max(120, resizeStartWidth - dx)}px`;
      subtitleBox.style.height = `${Math.max(40, resizeStartHeight + dy)}px`;
    } else if (currentResizer === "ne") {
      subtitleBox.style.width = `${Math.max(120, resizeStartWidth + dx)}px`;
      subtitleBox.style.height = `${Math.max(40, resizeStartHeight - dy)}px`;
    }
  }
});

window.addEventListener("mouseup", () => {
  if (isDraggingBox || isResizingBox) {
    autoSaveSubtitleStyle();
  }
  isDraggingBox = false;
  isResizingBox = false;
});

async function loadSubtitleStyle(jobId) {
  try {
    let s = null;
    const res = await fetch(`/api/jobs/${jobId}/style`);
    if (res.ok) {
      s = await res.json();
    }
    // If job does not have custom style yet, restore user preferences from localStorage
    if (!s || !s.font_name) {
      const saved = localStorage.getItem("dubstudio_subtitle_style");
      if (saved) s = JSON.parse(saved);
    }

    if (s) {
      if (s.font_name) fontNameSelect.value = s.font_name;
      if (s.font_size) fontSizeInput.value = s.font_size;
      if (s.primary_color) colorPrimaryInput.value = s.primary_color;
      if (s.outline_color) colorOutlineInput.value = s.outline_color;
      if (s.box_radius !== undefined) boxRadiusInput.value = s.box_radius;
      if (s.box_blur !== undefined) boxBlurInput.value = s.box_blur;
      if (s.text_align) textAlignSelect.value = s.text_align;

      if (s.pos_x !== null && s.pos_y !== null && s.pos_x !== undefined) {
        subtitleBox.style.bottom = "auto";
        subtitleBox.style.transform = "none";
        subtitleBox.style.left = `${s.pos_x}px`;
        subtitleBox.style.top = `${s.pos_y}px`;
      }
      if (s.box_width) subtitleBox.style.width = `${s.box_width}px`;
      if (s.box_height) subtitleBox.style.height = `${s.box_height}px`;
    }

    applyStyleToSubtitleBox();
  } catch (e) {}
}

const resetStyleBtn = document.getElementById("btn-reset-style");
if (resetStyleBtn) {
  resetStyleBtn.addEventListener("click", () => {
    fontNameSelect.value = "Arial";
    fontSizeInput.value = "22";
    colorPrimaryInput.value = "#ffffff";
    colorOutlineInput.value = "#000000";
    colorBgInput.value = "#000000";
    bgOpacityInput.value = "65";
    boxRadiusInput.value = "8";
    boxBlurInput.value = "6";
    textAlignSelect.value = "center";

    subtitleBox.style.left = "50%";
    subtitleBox.style.top = "auto";
    subtitleBox.style.bottom = "35px";
    subtitleBox.style.transform = "translateX(-50%)";
    subtitleBox.style.width = "85%";
    subtitleBox.style.height = "auto";

    applyStyleToSubtitleBox();
    autoSaveSubtitleStyle();
  });
}

document.getElementById("btn-save-style").addEventListener("click", async () => {
  if (!currentJobId) return;
  autoSaveSubtitleStyle();
  alert("Đã lưu vị trí và toàn bộ kiểu dáng phụ đề thành công!");
});

// -------------------------------------------------------------
// 3. SUBTITLE & VOICE EDITOR (25 VIENEU VOICES)
// -------------------------------------------------------------
async function loadSegments(jobId) {
  const container = document.getElementById("segments-scroll-list");
  container.innerHTML = '<p style="color:var(--text-muted); padding:10px;">Đang tải danh sách câu thoại...</p>';

  try {
    const res = await fetch(`/api/jobs/${jobId}/segments`);
    const data = await res.json();
    segmentsData = data.segments || [];
    document.getElementById("segments-count-badge").textContent = `${segmentsData.length} câu`;

    if (segmentsData.length === 0) {
      container.innerHTML = '<p style="color:var(--text-muted); padding:10px;">Chưa có dữ liệu câu thoại.</p>';
      renderTimeline();
      return;
    }

    container.innerHTML = "";
    const speeds = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5];

    segmentsData.forEach(s => {
      const item = document.createElement("div");
      item.className = "segment-item";
      item.id = `seg-item-${s.id}`;

      const ttsUrl = s.tts_file ? `/media/workspace/${jobId}/${s.tts_file}?t=${Date.now()}` : null;
      const currentVoice = s.voice || (s.gender === "female" ? "Quỳnh Anh" : "Minh Đức");
      const currentSpeed = s.speed || 1.0;

      const voiceOptionsHTML = buildVoiceSelectHTML(currentVoice);
      const speedOptionsHTML = speeds.map(sp => `<option value="${sp}" ${Math.abs(sp - currentSpeed) < 0.05 ? "selected" : ""}>${sp}x</option>`).join("");

      item.innerHTML = `
        <div class="seg-meta">
          <span style="font-weight:600; color:var(--text-bright);">#${s.id}</span>
          <span id="seg-time-${s.id}" style="color:var(--accent); font-family:monospace;">${s.start.toFixed(2)}s - ${s.end.toFixed(2)}s</span>
          <div class="seg-controls">
            <label style="font-size:0.75rem;">Giọng:</label>
            <select id="seg-voice-${s.id}">${voiceOptionsHTML}</select>
            <label style="font-size:0.75rem;">Tốc độ:</label>
            <select id="seg-speed-${s.id}">${speedOptionsHTML}</select>
          </div>
        </div>
        <div class="seg-src">${s.src_text || ""}</div>
        <input type="text" class="seg-input" id="seg-input-${s.id}" value="${(s.vi_text || "").replace(/"/g, '&quot;')}" />
        <div class="seg-bottom-actions">
          ${ttsUrl ? `<audio id="audio-${s.id}" src="${ttsUrl}" preload="none"></audio><button class="btn btn-sm btn-secondary" onclick="playAudioSnippet(${s.id})">🔊 Nghe</button>` : ""}
          <button class="btn btn-sm btn-secondary" onclick="openSplitModal(${s.id})">✂️ Tách câu</button>
          <button class="btn btn-sm btn-secondary" onclick="saveAndRegenerateLine(${s.id})">Lưu & Đọc lại</button>
        </div>
      `;
      container.appendChild(item);
    });

    renderTimeline();
  } catch (err) {
    container.innerHTML = `<p style="color:var(--danger)">Lỗi: ${err.message}</p>`;
  }
}

window.playAudioSnippet = function(id) {
  const audio = document.getElementById(`audio-${id}`);
  if (audio) {
    audio.currentTime = 0;
    audio.play();
  }
};

window.saveAndRegenerateLine = async function(segId) {
  if (!currentJobId) return;
  const newText = document.getElementById(`seg-input-${segId}`).value;
  const newVoice = document.getElementById(`seg-voice-${segId}`).value;
  const newSpeed = parseFloat(document.getElementById(`seg-speed-${segId}`).value) || 1.0;

  try {
    // 1. Update text, voice & speed in segments.json
    await fetch(`/api/jobs/${currentJobId}/segments/${segId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vi_text: newText, voice: newVoice, speed: newSpeed }),
    });

    // 2. Regenerate audio with chosen voice and speed
    const res = await fetch(`/api/jobs/${currentJobId}/segments/${segId}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voice: newVoice, speed: newSpeed }),
    });
    const data = await res.json();

    if (data.status === "regenerated") {
      alert(`Đã đổi giọng và tạo lại câu #${segId} thành công!\nGiọng: ${data.voice} | Tốc độ: ${data.speed}x | Độ dài: ${data.tts_dur}s`);
      loadSegments(currentJobId);
    } else {
      alert("Lỗi: " + (data.detail || "Không rõ nguyên nhân"));
    }
  } catch (err) {
    alert("Lỗi kết nối: " + err.message);
  }
};

// -------------------------------------------------------------
// 4. MULTI-TRACK INTERACTIVE TIMELINE
// -------------------------------------------------------------
function renderTimeline() {
  const totalSecs = Math.max(videoDuration, 30);
  const totalWidth = totalSecs * pxPerSec + 200;
  timelineCanvas.style.minWidth = `${totalWidth}px`;

  ruler.innerHTML = "";
  const step = pxPerSec >= 30 ? 5 : 10;
  for (let s = 0; s <= totalSecs; s += step) {
    const tick = document.createElement("div");
    tick.className = "ruler-tick";
    tick.style.left = `${s * pxPerSec}px`;
    tick.textContent = formatTime(s).slice(0, 5);
    ruler.appendChild(tick);
  }

  const videoBlock = document.getElementById("video-clip-block");
  videoBlock.style.width = `${totalSecs * pxPerSec}px`;

  trackVoice.querySelectorAll(".timeline-clip").forEach(el => el.remove());

  segmentsData.forEach(seg => {
    const clip = document.createElement("div");
    clip.className = "timeline-clip";
    clip.id = `clip-${seg.id}`;
    const left = seg.start * pxPerSec;
    const width = Math.max(20, (seg.end - seg.start) * pxPerSec);

    clip.style.left = `${left}px`;
    clip.style.width = `${width}px`;
    clip.title = `#${seg.id}: ${seg.vi_text || seg.src_text}`;
    clip.textContent = `#${seg.id} ${seg.vi_text || seg.src_text}`;

    clip.addEventListener("click", (e) => {
      e.stopPropagation();
      videoPlayer.currentTime = seg.start;
      highlightActiveSegment(seg.id);
      const segItem = document.getElementById(`seg-item-${seg.id}`);
      if (segItem) segItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });

    makeClipDraggable(clip, seg);
    trackVoice.appendChild(clip);
  });
}

function makeClipDraggable(element, seg) {
  let isDragging = false;
  let startX = 0;
  let initialLeft = 0;

  element.addEventListener("mousedown", (e) => {
    isDragging = true;
    startX = e.clientX;
    initialLeft = parseFloat(element.style.left) || 0;
    element.classList.add("selected");
    e.preventDefault();
  });

  window.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    const deltaX = e.clientX - startX;
    let newLeft = Math.max(0, initialLeft + deltaX);
    element.style.left = `${newLeft}px`;

    const newStart = Math.max(0, newLeft / pxPerSec);
    const duration = seg.end - seg.start;
    const newEnd = newStart + duration;

    seg.start = Math.round(newStart * 100) / 100;
    seg.end = Math.round(newEnd * 100) / 100;

    const timeBadge = document.getElementById(`seg-time-${seg.id}`);
    if (timeBadge) timeBadge.textContent = `${seg.start.toFixed(2)}s - ${seg.end.toFixed(2)}s`;
  });

  window.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      if (currentJobId) {
        fetch(`/api/jobs/${currentJobId}/segments/${seg.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ start: seg.start, end: seg.end }),
        });
      }
    }
  });
}

timelineCanvas.addEventListener("click", (e) => {
  const rect = timelineCanvas.getBoundingClientRect();
  const clickX = e.clientX - rect.left;
  const seekTime = Math.max(0, clickX / pxPerSec);
  videoPlayer.currentTime = seekTime;
});

const btnPlay = document.getElementById("tl-btn-play");
btnPlay.addEventListener("click", () => {
  if (videoPlayer.paused) {
    videoPlayer.play();
    btnPlay.textContent = "⏸ Tạm dừng";
  } else {
    videoPlayer.pause();
    btnPlay.textContent = "▶ Phát";
  }
});

document.getElementById("tl-zoom-in").addEventListener("click", () => {
  pxPerSec = Math.min(120, pxPerSec + 10);
  renderTimeline();
});

document.getElementById("tl-zoom-out").addEventListener("click", () => {
  pxPerSec = Math.max(15, pxPerSec - 10);
  renderTimeline();
});

document.getElementById("tl-btn-save-timing").addEventListener("click", () => {
  alert("Mốc thời gian kéo thả đã được tự động lưu vào hệ thống!");
});

// -------------------------------------------------------------
// 5. PRE-PROCESS MODAL & POPULATING VOICES
// -------------------------------------------------------------
const preprocessModal = document.getElementById("preprocess-modal");
document.getElementById("btn-open-preprocess").addEventListener("click", () => {
  preprocessModal.classList.add("open");
});
document.getElementById("btn-close-modal").addEventListener("click", () => preprocessModal.classList.remove("open"));
document.getElementById("btn-cancel-modal").addEventListener("click", () => preprocessModal.classList.remove("open"));

function initVoiceSelectors() {
  const modalMale = document.getElementById("modal-male-voice");
  const modalFemale = document.getElementById("modal-female-voice");
  const setMale = document.getElementById("set-male-voice");
  const setFemale = document.getElementById("set-female-voice");

  let males = '';
  let females = '';
  VIENEU_VOICES.forEach(v => {
    const opt = `<option value="${v.name}">${v.name} (${v.region})</option>`;
    if (v.gender === 'male') males += opt;
    else females += opt;
  });

  if (modalMale) modalMale.innerHTML = males;
  if (setMale) setMale.innerHTML = males;
  if (modalFemale) modalFemale.innerHTML = females;
  if (setFemale) setFemale.innerHTML = females;

  if (modalMale) modalMale.value = "Minh Đức";
  if (setMale) setMale.value = "Minh Đức";
  if (modalFemale) modalFemale.value = "Quỳnh Anh";
  if (setFemale) setFemale.value = "Quỳnh Anh";
}

document.getElementById("btn-confirm-start").addEventListener("click", async () => {
  const path = document.getElementById("modal-video-path").value.trim();
  const tone = document.getElementById("modal-tone-select").value;
  const male = document.getElementById("modal-male-voice").value;
  const female = document.getElementById("modal-female-voice").value;

  if (!path) return alert("Vui lòng nhập đường dẫn video.");

  try {
    const res = await fetch("/api/jobs/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_path: path }),
    });
    const jobData = await res.json();
    const jobId = jobData.job_id;

    await fetch(`/api/jobs/${jobId}/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ translation_tone: tone, default_male_voice: male, default_female_voice: female }),
    });

    await fetch(`/api/jobs/${jobId}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_path: jobData.video_path }),
    });

    preprocessModal.classList.remove("open");
    selectJob(jobId);
    alert(`Đã khởi chạy tác vụ với văn phong: "${tone}"!\nGiọng Nam (${male}) | Giọng Nữ (${female}).`);
  } catch (err) {
    alert("Lỗi: " + err.message);
  }
});

// Merge & Settings
document.getElementById("btn-merge").addEventListener("click", async () => {
  const v1 = document.getElementById("merge-v1").value.trim();
  const v2 = document.getElementById("merge-v2").value.trim();
  const out = document.getElementById("merge-out").value.trim() || "merged.mp4";
  const reencode = document.getElementById("merge-reencode").checked;
  const statusEl = document.getElementById("merge-status");

  if (!v1 || !v2) return alert("Vui lòng nhập đường dẫn ít nhất 2 video.");

  statusEl.textContent = "⏳ Đang ghép nối...";
  try {
    const res = await fetch("/api/tools/merge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ videos: [v1, v2], output_name: out, force_reencode: reencode }),
    });
    const data = await res.json();
    if (res.ok) {
      statusEl.textContent = `✅ Ghép thành công: ${data.merged_file}`;
    } else {
      statusEl.textContent = `❌ ${data.detail || "Ghép thất bại"}`;
    }
  } catch (e) {
    statusEl.textContent = `❌ Lỗi: ${e.message}`;
  }
});

// -------------------------------------------------------------
// 7. VIDEO EDITOR (CROP / COLOR BOX / IMAGE OVERLAY)
// -------------------------------------------------------------
const btnModeCrop = document.getElementById("btn-mode-crop");
const btnModeMerge = document.getElementById("btn-mode-merge");
const paneCrop = document.getElementById("editor-pane-crop");
const paneMerge = document.getElementById("editor-pane-merge");

if (btnModeCrop && btnModeMerge) {
  btnModeCrop.addEventListener("click", () => {
    paneCrop.style.display = "flex";
    paneMerge.style.display = "none";
    btnModeCrop.className = "btn btn-sm btn-success";
    btnModeMerge.className = "btn btn-sm btn-secondary";
  });
  btnModeMerge.addEventListener("click", () => {
    paneCrop.style.display = "none";
    paneMerge.style.display = "flex";
    btnModeCrop.className = "btn btn-sm btn-secondary";
    btnModeMerge.className = "btn btn-sm btn-success";
  });
}

const editVideoInput = document.getElementById("edit-video-input");
const editVideoPlayer = document.getElementById("edit-video-player");
const editNoVideo = document.getElementById("edit-no-video");
const editCanvasWrapper = document.getElementById("edit-canvas-wrapper");

const btnEditLoadCurrent = document.getElementById("btn-edit-load-current");
const btnEditLoadVideo = document.getElementById("btn-edit-load-video");

if (btnEditLoadCurrent) {
  btnEditLoadCurrent.addEventListener("click", () => {
    if (currentJobId) {
      editVideoInput.value = `out/${currentJobId}_vi.mp4`;
      loadVideoIntoEditor();
    } else {
      alert("Chưa có tác vụ lồng tiếng nào đang mở.");
    }
  });
}

if (btnEditLoadVideo) {
  btnEditLoadVideo.addEventListener("click", loadVideoIntoEditor);
}

function loadVideoIntoEditor() {
  const p = (editVideoInput.value || "").trim();
  if (!p) return alert("Vui lòng nhập đường dẫn video.");

  let srcUrl = p;
  if (!p.startsWith("http://") && !p.startsWith("https://") && !p.startsWith("/")) {
    if (p.startsWith("out/")) srcUrl = `/media/${p}`;
    else if (p.startsWith("samples/")) srcUrl = `/media/${p}`;
    else srcUrl = `/media/samples/${p}`;
  }

  editVideoPlayer.src = srcUrl;
  editVideoPlayer.onloadedmetadata = () => {
    if (editNoVideo) editNoVideo.style.display = "none";
    resetCropBoxToFit();
  };
  editVideoPlayer.onerror = () => {
    alert("Không thể tải video từ đường dẫn đã nhập.");
  };
}

// Interactive boxes: Crop, Color box, Image overlay
const editCropBox = document.getElementById("edit-crop-box");
const editColorBox = document.getElementById("edit-color-box");
const editImgBox = document.getElementById("edit-img-box");

const checkEnableCrop = document.getElementById("edit-enable-crop");
const checkEnableColor = document.getElementById("edit-enable-color-box");
const checkEnableImg = document.getElementById("edit-enable-img");

if (checkEnableCrop) {
  checkEnableCrop.addEventListener("change", (e) => {
    editCropBox.style.display = e.target.checked ? "block" : "none";
    if (e.target.checked && editCropBox.offsetWidth < 20) resetCropBoxToFit();
  });
}

if (checkEnableColor) {
  checkEnableColor.addEventListener("change", (e) => {
    editColorBox.style.display = e.target.checked ? "block" : "none";
    if (e.target.checked && editColorBox.offsetWidth < 20) {
      editColorBox.style.left = "40px";
      editColorBox.style.top = "260px";
      editColorBox.style.width = "400px";
      editColorBox.style.height = "50px";
    }
    updateColorBoxStyle();
  });
}

if (checkEnableImg) {
  checkEnableImg.addEventListener("change", (e) => {
    editImgBox.style.display = e.target.checked ? "block" : "none";
    if (e.target.checked && editImgBox.offsetWidth < 20) {
      editImgBox.style.left = "30px";
      editImgBox.style.top = "30px";
      editImgBox.style.width = "100px";
      editImgBox.style.height = "50px";
    }
  });
}

function resetCropBoxToFit() {
  if (!editCanvasWrapper) return;
  const w = editCanvasWrapper.clientWidth;
  const h = editCanvasWrapper.clientHeight;
  editCropBox.style.left = "0px";
  editCropBox.style.top = "0px";
  editCropBox.style.width = `${w}px`;
  editCropBox.style.height = `${h}px`;
  syncCropInputs();
}

const btnResetCrop = document.getElementById("btn-edit-reset-crop");
if (btnResetCrop) btnResetCrop.addEventListener("click", resetCropBoxToFit);

function syncCropInputs() {
  const cx = document.getElementById("crop-x");
  const cy = document.getElementById("crop-y");
  const cw = document.getElementById("crop-w");
  const ch = document.getElementById("crop-h");
  if (cx) cx.value = parseInt(editCropBox.style.left) || 0;
  if (cy) cy.value = parseInt(editCropBox.style.top) || 0;
  if (cw) cw.value = editCropBox.offsetWidth || 100;
  if (ch) ch.value = editCropBox.offsetHeight || 100;
}

["crop-x", "crop-y", "crop-w", "crop-h"].forEach(id => {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener("input", () => {
      editCropBox.style.left = `${document.getElementById("crop-x").value}px`;
      editCropBox.style.top = `${document.getElementById("crop-y").value}px`;
      editCropBox.style.width = `${document.getElementById("crop-w").value}px`;
      editCropBox.style.height = `${document.getElementById("crop-h").value}px`;
    });
  }
});

// Color box style updater
function updateColorBoxStyle() {
  const col = document.getElementById("edit-color-val").value;
  const op = (parseInt(document.getElementById("edit-color-opacity").value) || 100) / 100;
  const rad = parseInt(document.getElementById("edit-color-radius").value) || 0;
  document.getElementById("edit-color-opacity-val").textContent = `${Math.round(op * 100)}%`;

  editColorBox.style.backgroundColor = col;
  editColorBox.style.opacity = op;
  editColorBox.style.borderRadius = `${rad}px`;
}

["edit-color-val", "edit-color-opacity", "edit-color-radius"].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("input", updateColorBoxStyle);
});

// Image upload
const editImgUpload = document.getElementById("edit-img-upload");
const editImgElement = document.getElementById("edit-img-element");
if (editImgUpload) {
  editImgUpload.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      editImgElement.src = evt.target.result;
      checkEnableImg.checked = true;
      editImgBox.style.display = "block";
    };
    reader.readAsDataURL(file);
  });
}

// Generic Drag & Resize Manager for Editor Overlays
let activeEditTarget = null;
let isDraggingEdit = false;
let isResizingEdit = false;
let editHandleType = null;
let editStartX = 0, editStartY = 0;
let editBoxStartLeft = 0, editBoxStartTop = 0;
let editBoxStartW = 0, editBoxStartH = 0;
let editAspectRatio = 1.0;

document.querySelectorAll("#editor-pane-crop .interactive-overlay-box").forEach(box => {
  box.addEventListener("mousedown", (e) => {
    if (e.target.classList.contains("edit-resizer")) return;
    activeEditTarget = box;
    isDraggingEdit = true;
    editStartX = e.clientX;
    editStartY = e.clientY;
    const rect = box.getBoundingClientRect();
    const parentRect = editCanvasWrapper.getBoundingClientRect();
    editBoxStartLeft = rect.left - parentRect.left;
    editBoxStartTop = rect.top - parentRect.top;
    e.preventDefault();
  });
});

document.querySelectorAll("#editor-pane-crop .edit-resizer").forEach(resizer => {
  resizer.addEventListener("mousedown", (e) => {
    const targetKey = resizer.getAttribute("data-target");
    if (targetKey === "crop") activeEditTarget = editCropBox;
    else if (targetKey === "color") activeEditTarget = editColorBox;
    else if (targetKey === "img") activeEditTarget = editImgBox;

    isResizingEdit = true;
    editHandleType = resizer.getAttribute("data-handle");
    editStartX = e.clientX;
    editStartY = e.clientY;
    editBoxStartW = activeEditTarget.offsetWidth;
    editBoxStartH = activeEditTarget.offsetHeight;
    editAspectRatio = Math.max(0.1, editBoxStartW / Math.max(1, editBoxStartH));
    e.stopPropagation();
    e.preventDefault();
  });
});

window.addEventListener("mousemove", (e) => {
  if (!activeEditTarget) return;

  if (isDraggingEdit) {
    const dx = e.clientX - editStartX;
    const dy = e.clientY - editStartY;
    const maxLeft = editCanvasWrapper.clientWidth - activeEditTarget.offsetWidth;
    const maxTop = editCanvasWrapper.clientHeight - activeEditTarget.offsetHeight;
    const newL = Math.max(0, Math.min(maxLeft, editBoxStartLeft + dx));
    const newT = Math.max(0, Math.min(maxTop, editBoxStartTop + dy));
    activeEditTarget.style.left = `${newL}px`;
    activeEditTarget.style.top = `${newT}px`;
    if (activeEditTarget === editCropBox) syncCropInputs();
  } else if (isResizingEdit) {
    const dx = e.clientX - editStartX;
    const dy = e.clientY - editStartY;
    let newW = editBoxStartW;
    let newH = editBoxStartH;

    if (editHandleType === "se") {
      newW = Math.max(20, editBoxStartW + dx);
      newH = Math.max(20, editBoxStartH + dy);
    } else if (editHandleType === "sw") {
      newW = Math.max(20, editBoxStartW - dx);
      newH = Math.max(20, editBoxStartH + dy);
    } else if (editHandleType === "ne") {
      newW = Math.max(20, editBoxStartW + dx);
      newH = Math.max(20, editBoxStartH - dy);
    } else if (editHandleType === "nw") {
      newW = Math.max(20, editBoxStartW - dx);
      newH = Math.max(20, editBoxStartH - dy);
    }

    if (activeEditTarget === editImgBox && document.getElementById("edit-img-fix-scale").checked) {
      newH = Math.round(newW / editAspectRatio);
    }

    activeEditTarget.style.width = `${newW}px`;
    activeEditTarget.style.height = `${newH}px`;
    if (activeEditTarget === editCropBox) syncCropInputs();
  }
});

window.addEventListener("mouseup", () => {
  isDraggingEdit = false;
  isResizingEdit = false;
  activeEditTarget = null;
});

// Run Video Editor API Call
const btnRunEditVideo = document.getElementById("btn-run-edit-video");
if (btnRunEditVideo) {
  btnRunEditVideo.addEventListener("click", async () => {
    const vPath = editVideoInput.value.trim();
    if (!vPath) return alert("Vui lòng nhập đường dẫn video cần sửa.");

    const statusEl = document.getElementById("edit-process-status");
    statusEl.innerHTML = `<span style="color:var(--accent);">⏳ Đang xử lý chỉnh sửa qua FFmpeg...</span>`;

    const payload = {
      video_path: vPath,
      preview_width: editCanvasWrapper.clientWidth,
      preview_height: editCanvasWrapper.clientHeight,
      output_name: document.getElementById("edit-output-name").value.trim() || "edited_video.mp4",
      crop: {
        enabled: checkEnableCrop.checked,
        x: parseInt(editCropBox.style.left) || 0,
        y: parseInt(editCropBox.style.top) || 0,
        width: editCropBox.offsetWidth,
        height: editCropBox.offsetHeight,
      },
      color_box: {
        enabled: checkEnableColor.checked,
        x: parseInt(editColorBox.style.left) || 0,
        y: parseInt(editColorBox.style.top) || 0,
        width: editColorBox.offsetWidth,
        height: editColorBox.offsetHeight,
        color: document.getElementById("edit-color-val").value,
        opacity: (parseInt(document.getElementById("edit-color-opacity").value) || 100) / 100,
      },
      image_overlay: {
        enabled: checkEnableImg.checked,
        x: parseInt(editImgBox.style.left) || 0,
        y: parseInt(editImgBox.style.top) || 0,
        width: editImgBox.offsetWidth,
        height: editImgBox.offsetHeight,
        image_data: editImgElement.src || "",
      },
    };

    try {
      const res = await fetch("/api/tools/edit-video", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Lỗi chỉnh sửa video");

      statusEl.innerHTML = `
        <span style="color:var(--accent); font-weight:600;">✓ Xuất video thành công: ${data.file}</span>
        <div style="margin-top:6px;">
          <a href="${data.url}" download="${data.file}" class="btn btn-sm btn-success">⬇️ Tải video đã sửa</a>
        </div>
      `;
    } catch (err) {
      statusEl.innerHTML = `<span style="color:var(--danger);">❌ Lỗi: ${err.message}</span>`;
    }
  });
}

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();
    document.getElementById("set-key-masked").textContent = data.gemini_api_key_masked || "Chưa thiết lập";
    document.getElementById("set-model").value = data.translation_model || "gemini-2.5-flash";
    if (data.default_male_voice) document.getElementById("set-male-voice").value = data.default_male_voice;
    if (data.default_female_voice) document.getElementById("set-female-voice").value = data.default_female_voice;
  } catch (e) {}
}

document.getElementById("btn-test-key").addEventListener("click", async () => {
  const statusEl = document.getElementById("key-test-status");
  statusEl.textContent = "Đang kiểm tra...";
  try {
    const res = await fetch("/api/settings/test-key", { method: "POST" });
    const data = await res.json();
    statusEl.textContent = data.message;
    statusEl.style.color = (data.status === "ok") ? "var(--accent)" : "var(--danger)";
  } catch (e) {
    statusEl.textContent = "Lỗi kết nối";
  }
});

document.getElementById("btn-save-settings").addEventListener("click", async () => {
  const key = document.getElementById("set-new-key").value.trim();
  const model = document.getElementById("set-model").value.trim();
  const male = document.getElementById("set-male-voice").value;
  const female = document.getElementById("set-female-voice").value;

  const payload = { translation_model: model, default_male_voice: male, default_female_voice: female };
  if (key) payload.gemini_api_key = key;

  try {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    alert("Đã lưu cài đặt thành công!");
    document.getElementById("set-new-key").value = "";
    loadSettings();
  } catch (e) {
    alert("Lỗi lưu cài đặt: " + e.message);
  }
});

// -------------------------------------------------------------
// 6. SPLIT SENTENCE MODAL (MULTI-PART ENTER BREAK)
// -------------------------------------------------------------
let currentSplitSegId = null;
const splitModal = document.getElementById("split-modal");
const splitTextarea = document.getElementById("split-modal-textarea");
const splitPreview = document.getElementById("split-modal-preview");

window.openSplitModal = function(segId) {
  const s = segmentsData.find(x => x.id === segId);
  if (!s) return;
  currentSplitSegId = segId;
  const titleEl = document.getElementById("split-modal-title");
  if (titleEl) titleEl.textContent = `✂️ Tách câu thoại #${s.id} (${s.start.toFixed(2)}s - ${s.end.toFixed(2)}s)`;
  if (splitTextarea) splitTextarea.value = s.vi_text || s.src_text || "";
  updateSplitPreview();
  if (splitModal) {
    splitModal.classList.add("open");
    setTimeout(() => splitTextarea && splitTextarea.focus(), 50);
  }
};

function updateSplitPreview() {
  if (!splitTextarea || !splitPreview) return;
  const s = segmentsData.find(x => x.id === currentSplitSegId);
  const totalDur = s ? Math.max(0.2, s.end - s.start) : 1.0;
  const lines = splitTextarea.value.split("\n").map(l => l.trim()).filter(Boolean);

  if (lines.length <= 1) {
    splitPreview.innerHTML = `
      <div style="color:var(--text-muted);">
        📍 Chưa có điểm tách nào. Hãy đặt con trỏ chuột vào vị trí ngắt câu và nhấn phím <strong>Enter</strong> để tách thành 2 hay nhiều câu.
      </div>
    `;
    return;
  }

  const wordCounts = lines.map(l => Math.max(1, l.split(/\s+/).length));
  const totalWords = wordCounts.reduce((a, b) => a + b, 0);

  let html = `<div style="font-weight:600; color:var(--accent); margin-bottom: 6px;">Sẽ tách thành ${lines.length} câu:</div>`;
  let runningStart = s ? s.start : 0;
  lines.forEach((l, idx) => {
    const dur = totalDur * (wordCounts[idx] / totalWords);
    const endT = (idx === lines.length - 1 && s) ? s.end : (runningStart + dur);
    html += `
      <div style="padding: 4px 0; border-bottom: 1px dotted rgba(255,255,255,0.1);">
        <strong>Phần ${idx + 1}</strong> (${wordCounts[idx]} từ - ~${runningStart.toFixed(2)}s đến ${endT.toFixed(2)}s): 
        <span style="color:var(--text-bright);">${l}</span>
      </div>
    `;
    runningStart = endT;
  });
  splitPreview.innerHTML = html;
}

if (splitTextarea) {
  splitTextarea.addEventListener("input", updateSplitPreview);
  splitTextarea.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key === "Enter") {
      e.preventDefault();
      const confirmBtn = document.getElementById("btn-confirm-split");
      if (confirmBtn) confirmBtn.click();
    }
  });
}

const closeSplitBtn = document.getElementById("btn-close-split-modal");
if (closeSplitBtn) closeSplitBtn.addEventListener("click", () => splitModal && splitModal.classList.remove("open"));

const cancelSplitBtn = document.getElementById("btn-cancel-split-modal");
if (cancelSplitBtn) cancelSplitBtn.addEventListener("click", () => splitModal && splitModal.classList.remove("open"));

const confirmSplitBtn = document.getElementById("btn-confirm-split");
if (confirmSplitBtn) {
  confirmSplitBtn.addEventListener("click", async () => {
    if (!currentJobId || !currentSplitSegId) return;
    const lines = splitTextarea.value.split("\n").map(l => l.trim()).filter(Boolean);
    if (lines.length < 2) {
      alert("Vui lòng nhấn Enter để chia câu thành ít nhất 2 dòng trước khi xác nhận!");
      return;
    }

    try {
      const res = await fetch(`/api/jobs/${currentJobId}/segments/${currentSplitSegId}/split`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seg_id: currentSplitSegId, parts: lines }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Lỗi tách câu");
      }

      if (splitModal) splitModal.classList.remove("open");
      await loadSegments(currentJobId);
    } catch (err) {
      alert("Không thể tách câu: " + err.message);
    }
  });
}

// Boot
initVoiceSelectors();
refreshJobs();

