import React, { useState, useEffect } from 'react';
import { WYSIWYGPlayer, SubtitleStyle, ColorBoxItem } from '../video/WYSIWYGPlayer';
import { CueItem } from '../subtitles/SubtitleEditor';
import { AudioMixerDeck } from '../audio/AudioMixerDeck';
import { 
  IconFilm, IconFolder, IconDownload, 
  IconCheck, IconPlay, IconPlus, IconTrash 
} from '../icons/StudioIcons';
import { bridge, PipelineEvent } from '../../api/bridge';

interface MergeExportViewProps {
  jobId: string;
  projectTitle: string;
  videoSrc?: string;
  voiceSrc?: string;
  bgmSrc?: string;
  cues?: CueItem[];
  activeSubtitle?: string;
  subtitleStyle?: SubtitleStyle;
  aspectRatio: string;
  onAspectRatioChange: (ratio: string) => void;
  voiceVol: number;
  bgmVol: number;
  onVoiceVolChange: (vol: number) => void;
  onBgmVolChange: (vol: number) => void;
  isActiveTab?: boolean;
}

const ASPECT_RATIO_PRESETS = [
  { label: 'Tỉ lệ gốc', value: 'original' },
  { label: '9:16 Shorts / TikTok', value: '9:16' },
  { label: '16:9 YouTube', value: '16:9' },
  { label: '1:1 Vuông Feed', value: '1:1' },
  { label: '4:5 Dọc Instagram', value: '4:5' },
  { label: '4:3 Cổ điển', value: '4:3' },
  { label: 'Tùy chỉnh (W:H)', value: 'custom' },
];

export const MergeExportView: React.FC<MergeExportViewProps> = ({
  jobId,
  projectTitle,
  videoSrc,
  voiceSrc,
  bgmSrc,
  cues = [],
  activeSubtitle = '',
  subtitleStyle = {},
  aspectRatio = 'original',
  onAspectRatioChange,
  voiceVol,
  bgmVol,
  isActiveTab = true,
  onVoiceVolChange,
  onBgmVolChange,
}) => {
  const [outputTitle, setOutputTitle] = useState(projectTitle);
  const [targetDir, setTargetDir] = useState('');
  const [burnSubtitles, setBurnSubtitles] = useState(true);

  // Aspect ratio customization
  const [customAR, setCustomAR] = useState('21:9');
  const [canvasColor, setCanvasColor] = useState('#000000');

  // 4-track audio mixing
  const [customBgmPath, setCustomBgmPath] = useState('');
  const [customBgmVol, setCustomBgmVol] = useState(50);
  const [origVoiceVol, setOrigVoiceVol] = useState(0);

  // Playback state
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  // Automatically pause playback when switching away from this tab
  useEffect(() => {
    if (!isActiveTab) {
      setIsPlaying(false);
    }
  }, [isActiveTab]);

  // Sequential Sub-segment Timing based on word-count ratio
  const effectiveSubtitle = (() => {
    if (!cues || cues.length === 0) return activeSubtitle;
    const currentCue = cues.find((c) => currentTime >= c.start && currentTime <= c.end);
    if (!currentCue || currentCue.mute_sub || (currentCue as any).muted_sub) return '';
    const raw = (currentCue.text || '').trim();
    if (!raw) return '';

    // 1. Explicit sub-cues with timestamps
    if (currentCue.cues && Array.isArray(currentCue.cues) && currentCue.cues.length > 0) {
      const match = currentCue.cues.find((sc: any) => currentTime >= sc.start && currentTime <= sc.end);
      if (match && match.text) return match.text.trim();
    }

    // 2. Sequential Sub-segment Timing based on _effective_weight matching cue_split.py 1:1
    if (raw.includes('\n')) {
      const lines = raw.split('\n').map((l) => l.trim()).filter(Boolean);
      if (lines.length > 1) {
        const totalDur = Math.max(0.1, currentCue.end - currentCue.start);
        const commaSet = new Set([',', '，', ';', '；', '—', '-']);
        const termSet = new Set(['.', '。', '?', '？', '!', '！', '…']);

        const weights = lines.map((l) => {
          const clean = l.replace(/\s+/g, '');
          let base = Math.max(1, clean.length);
          const lastChar = l.slice(-1);
          if (commaSet.has(lastChar)) base += 2.5;
          else if (termSet.has(lastChar)) base += 4.0;
          return base;
        });
        const totalW = weights.reduce((acc, w) => acc + w, 0);

        let currT = currentCue.start;
        for (let i = 0; i < lines.length; i++) {
          const ratio = weights[i] / totalW;
          const lineDur = (i === lines.length - 1) ? (currentCue.end - currT) : (totalDur * ratio);
          const segEnd = currT + lineDur;
          if (currentTime >= currT && currentTime < segEnd) {
            return lines[i];
          }
          currT = segEnd;
        }
        return lines[lines.length - 1];
      }
    }

    return raw;
  })();

  // Logo / Watermark
  const [logoConfig, setLogoConfig] = useState<{
    path?: string;
    position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
    margin: number;
    scale_pct: number;
    opacity: number;
  }>({
    path: '',
    position: 'top-right',
    margin: 20,
    scale_pct: 15,
    opacity: 1.0,
  });

  // Recent 4 canvas colors
  const [recentCanvasColors, setRecentCanvasColors] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem('dubstudio_recent_canvas_colors');
      if (stored) return JSON.parse(stored);
    } catch {}
    return ['#000000', '#121214', '#1E293B', '#FFFFFF'];
  });

  const handleSelectCanvasColor = (hex: string) => {
    setCanvasColor(hex);
    setRecentCanvasColors((prev) => {
      const filtered = prev.filter((c) => c.toLowerCase() !== hex.toLowerCase());
      const next = [hex, ...filtered].slice(0, 4);
      try {
        localStorage.setItem('dubstudio_recent_canvas_colors', JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  // Multi color/text box overlays (Khối che chữ gốc / Watermark)
  const [colorBoxes, setColorBoxes] = useState<ColorBoxItem[]>([]);
  const [selectedBoxIndex, setSelectedBoxIndex] = useState<number>(0);

  const handleAddBox = () => {
    const newBox: ColorBoxItem = {
      id: `box_${Date.now()}`,
      x: 20,
      y: 75,
      w: 60,
      h: 12,
      color: '#000000',
      opacity: 0.85,
      radius: 6,
      rotation: 0,
      text: '',
      font_name: 'Arial',
      font_size: 14,
      text_color: '#FFFFFF',
      text_outline_color: '#000000',
      text_outline_width: 2,
      enabled: true,
    };
    const updated = [...colorBoxes, newBox];
    setColorBoxes(updated);
    setSelectedBoxIndex(updated.length - 1);
    if (jobId) {
      bridge.saveProjectStyle(jobId, { color_boxes: updated });
    }
  };

  const handleDeleteBox = (index: number) => {
    const updated = colorBoxes.filter((_, i) => i !== index);
    setColorBoxes(updated);
    setSelectedBoxIndex(Math.max(0, index - 1));
    if (jobId) {
      bridge.saveProjectStyle(jobId, { color_boxes: updated });
    }
  };

  const handleUpdateBoxAtIndex = (index: number, updates: Partial<ColorBoxItem>) => {
    if (index < 0 || index >= colorBoxes.length) return;
    const updated = colorBoxes.map((b, i) => (i === index ? { ...b, ...updates } : b));
    setColorBoxes(updated);
    if (jobId) {
      bridge.saveProjectStyle(jobId, { color_boxes: updated });
    }
  };

  const handleUpdateSelectedBox = (updates: Partial<ColorBoxItem>) => {
    handleUpdateBoxAtIndex(selectedBoxIndex, updates);
  };

  // Original audio ranges for seamless preview
  const [origRanges, setOrigRanges] = useState<{ start: number; end: number }[]>([]);

  useEffect(() => {
    if (!jobId) return;
    bridge.getProjectData(jobId).then((data) => {
      if (data && data.style) {
        if (Array.isArray(data.style.keep_original_ranges)) {
          setOrigRanges(
            data.style.keep_original_ranges.map((r: any) => ({
              start: Number(r[0] || 0),
              end: Number(r[1] || 0),
            }))
          );
        }
        if (Array.isArray(data.style.color_boxes)) {
          setColorBoxes(data.style.color_boxes);
        } else if (data.style.color_box && typeof data.style.color_box === 'object') {
          setColorBoxes([data.style.color_box]);
        }
      }
    });
  }, [jobId]);

  // Export progress
  const [isExporting, setIsExporting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [exportSuccessPath, setExportSuccessPath] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setOutputTitle(projectTitle);
    bridge.getAppSettings().then((s) => {
      if (s && s.out_dir) setTargetDir(s.out_dir);
    });
  }, [projectTitle]);

  // Subscribe to real-time rendering events
  useEffect(() => {
    const unsubscribe = bridge.onPipelineEvent((ev: PipelineEvent) => {
      if (ev.job_id && ev.job_id !== jobId) return;

      if (ev.stage === 'render') {
        setProgress(Math.round(ev.progress));
        setStatusMessage(ev.message);

        if (ev.level === 'success') {
          setIsExporting(false);
          setExportSuccessPath(ev.out_path || '');
        } else if (ev.level === 'error') {
          setIsExporting(false);
          setErrorMessage(ev.message);
        }
      }
    });

    return unsubscribe;
  }, [jobId]);

  const handleBrowseDir = async () => {
    const dir = await bridge.openFolderDialog(targetDir);
    if (dir) setTargetDir(dir);
  };

  const handleBrowseCustomBgm = async () => {
    const f = await bridge.openVideoDialog(); // Opens file picker
    if (f) setCustomBgmPath(f);
  };

  const handleBrowseLogo = async () => {
    const f = await bridge.openImageDialog(); // Opens native image file picker (PNG, JPG, WebP)
    if (f) setLogoConfig((prev) => ({ ...prev, path: f }));
  };

  const handleSeek = (t: number) => {
    setCurrentTime(t);
  };

  const effectiveAR = aspectRatio === 'custom' ? customAR : aspectRatio;

  const handleStartExport = async () => {
    if (!jobId) {
      setErrorMessage('Không tìm thấy dự án hợp lệ để xuất.');
      return;
    }

    setIsExporting(true);
    setProgress(5);
    setStatusMessage('Đang khởi tạo bộ mã hóa FFmpeg...');
    setErrorMessage(null);
    setExportSuccessPath(null);

    try {
      await bridge.exportProjectVideo(jobId, {
        title: outputTitle,
        aspect_ratio: effectiveAR,
        canvas_color: canvasColor.replace('#', ''),
        burn_subtitles: burnSubtitles,
        color_boxes: colorBoxes,
        voice_volume: voiceVol,
        bgm_volume: bgmVol,
        custom_bgm_path: customBgmPath || null,
        custom_bgm_volume: customBgmVol,
        orig_voice_volume: origVoiceVol,
        target_dir: targetDir,
        logo: logoConfig.path ? logoConfig : null,
        subtitle_style: subtitleStyle,
      });
    } catch (err: any) {
      setIsExporting(false);
      setErrorMessage(err?.message || 'Lỗi khi bắt đầu xuất video.');
    }
  };

  return (
    <div className="flex-1 w-full h-full flex overflow-hidden bg-[#121214] p-3 gap-3 select-none min-h-0">
      {/* ── LEFT PANE: Full Preview (Spacious & Natural) ── */}
      <section className="flex-1 h-full min-h-0 bg-[#161619] border border-white/[0.06] rounded-xl flex flex-col overflow-hidden">
        <div className="px-4 py-2 border-b border-white/[0.06] flex items-center justify-between shrink-0 bg-[#1A1A1E]">
          <div className="flex items-center gap-2">
            <IconFilm size={15} className="text-cyan-300" />
            <span className="text-xs font-semibold text-zinc-100">
              Xem trước
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#25252B] text-zinc-300">
              Tỉ lệ: {effectiveAR === 'original' ? 'Gốc' : effectiveAR}
            </span>
          </div>
        </div>

        {/* Video Canvas Stretches Fully */}
        <div className="flex-1 w-full h-full min-h-0 overflow-hidden flex flex-col">
          <WYSIWYGPlayer
            videoSrc={videoSrc}
            activeSubtitle={burnSubtitles ? effectiveSubtitle : ''}
            cues={cues}
            subtitleStyle={subtitleStyle}
            aspectRatio={effectiveAR}
            onAspectRatioChange={onAspectRatioChange}
            canvasColor={canvasColor}
            colorBoxes={colorBoxes}
            selectedBoxIndex={selectedBoxIndex}
            onSelectBoxIndex={setSelectedBoxIndex}
            onUpdateColorBox={handleUpdateBoxAtIndex}
            logo={logoConfig.path ? logoConfig : undefined}
            voiceSrc={voiceSrc}
            bgmSrc={bgmSrc}
            voiceVol={voiceVol}
            bgmVol={bgmVol}
            origRanges={origRanges}
            customBgmSrc={customBgmPath ? `/api/local-file?path=${encodeURIComponent(customBgmPath)}` : undefined}
            customBgmVol={customBgmVol}
            currentTime={currentTime}
            duration={duration || 1}
            isPlaying={isPlaying}
            onPlayPauseToggle={() => setIsPlaying(!isPlaying)}
            onSeek={(t) => handleSeek(t)}
            onTimeUpdate={(t) => setCurrentTime(t)}
            onDurationChange={(d) => setDuration(d)}
            hideHeader={true}
          />
        </div>
      </section>

      {/* ── RIGHT PANE: Audio Mixer, Aspect Ratio & Export Controls ── */}
      <aside className="w-96 bg-[#161619] border border-white/[0.06] rounded-xl p-4 flex flex-col justify-between shrink-0 overflow-y-auto min-h-0">
        <div className="space-y-4">
          <div className="pb-2.5 border-b border-white/[0.06]">
            <h3 className="text-sm font-semibold text-zinc-100">Chỉnh sửa & Xuất video</h3>
            <p className="text-[11px] text-zinc-500 mt-0.5">
              Hòa âm âm thanh 4 kênh và định dạng tỉ lệ xuất video thành phẩm.
            </p>
          </div>

          {/* 1. Tỉ lệ khung hình xuất ra */}
          <div className="space-y-2">
            <label className="block text-xs font-medium text-zinc-300">
              Tỉ lệ khung hình xuất ra
            </label>
            <div className="grid grid-cols-2 gap-1.5">
              {ASPECT_RATIO_PRESETS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  disabled={isExporting}
                  onClick={() => onAspectRatioChange(p.value)}
                  className={`py-1.5 px-2.5 rounded-lg border text-[11px] font-medium text-center transition-all ${
                    aspectRatio === p.value
                      ? 'bg-[#26262D] border-cyan-400/50 text-cyan-200 font-semibold shadow'
                      : 'bg-[#1A1A1E] border-white/[0.04] text-zinc-400 hover:text-zinc-200 hover:bg-[#202025]'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Custom Ratio Input */}
            {aspectRatio === 'custom' && (
              <div className="flex items-center gap-2 pt-1">
                <span className="text-[11px] text-zinc-400">Tỉ lệ tự nhập:</span>
                <input
                  type="text"
                  placeholder="ví dụ 21:9 hoặc 2.35:1"
                  value={customAR}
                  onChange={(e) => setCustomAR(e.target.value)}
                  className="flex-1 bg-[#1A1A1E] border border-white/10 rounded px-2.5 py-1 text-xs text-zinc-200 focus:outline-none focus:border-cyan-400"
                />
              </div>
            )}

            {/* Canvas Color when not original */}
            {aspectRatio !== 'original' && aspectRatio !== 'gốc' && (
              <div className="flex items-center justify-between pt-1">
                <span className="text-[11px] text-zinc-400">Màu nền khung (Canvas)</span>
                <div className="flex items-center gap-1.5">
                  {recentCanvasColors.map((hex) => (
                    <button
                      key={hex}
                      onClick={() => handleSelectCanvasColor(hex)}
                      style={{ backgroundColor: hex }}
                      className={`w-5 h-5 rounded border transition-transform ${
                        canvasColor.toLowerCase() === hex.toLowerCase() ? 'border-cyan-400 scale-110 shadow' : 'border-white/20 hover:scale-105'
                      }`}
                      title={hex}
                    />
                  ))}
                  <input
                    type="color"
                    value={canvasColor}
                    onChange={(e) => handleSelectCanvasColor(e.target.value)}
                    className="w-5 h-5 rounded border border-white/20 bg-transparent cursor-pointer p-0"
                    title="Chọn màu tự do"
                  />
                </div>
              </div>
            )}
          </div>

          {/* 2. Chèn Logo & Khắc phụ đề */}
          <div className="space-y-2.5">
            {/* Hardsub Toggle */}
            <div className="p-2.5 rounded-lg bg-[#1B1B1F] border border-white/[0.04]">
              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-xs font-medium text-zinc-200">
                  Khắc phụ đề vào video (Hardsub)
                </span>
                <input
                  type="checkbox"
                  checked={burnSubtitles}
                  onChange={(e) => setBurnSubtitles(e.target.checked)}
                  className="rounded bg-[#26262B] border-white/10 text-cyan-400 focus:ring-0 cursor-pointer"
                />
              </label>
              <p className="text-[10px] text-zinc-500 mt-1">
                Khắc phụ đề tiếng Việt khớp tuyệt đối từng pixel với khung xem trước.
              </p>
            </div>

            {/* Logo Overlay */}
            <div className="p-2.5 rounded-lg bg-[#1B1B1F] border border-white/[0.04] space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-zinc-200">Chèn Logo / Hình mờ</span>
                {logoConfig.path && (
                  <button
                    type="button"
                    onClick={() => setLogoConfig((prev) => ({ ...prev, path: '' }))}
                    className="text-[10px] text-red-400 hover:text-red-300"
                  >
                    Gỡ bỏ
                  </button>
                )}
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={logoConfig.path ? logoConfig.path.split('\\').pop() : ''}
                  placeholder="Chưa chọn tệp ảnh logo..."
                  className="flex-1 bg-[#1A1A1E] border border-white/10 rounded px-2 py-1 text-[11px] text-zinc-400 truncate"
                />
                <button
                  type="button"
                  onClick={handleBrowseLogo}
                  className="px-2.5 py-1 rounded bg-[#25252B] hover:bg-[#2F2F36] text-[11px] text-zinc-200 border border-white/[0.06] transition-colors"
                >
                  Chọn ảnh
                </button>
              </div>

              {logoConfig.path && (
                <div className="space-y-2 pt-1 border-t border-white/[0.04] text-[11px]">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-zinc-400 block mb-0.5">Vị trí:</span>
                      <select
                        value={logoConfig.position}
                        onChange={(e) => setLogoConfig((prev) => ({ ...prev, position: e.target.value as any }))}
                        className="w-full bg-[#1A1A1E] border border-white/10 rounded px-2 py-1 text-zinc-200"
                      >
                        <option value="top-right">Góc trên phải</option>
                        <option value="top-left">Góc trên trái</option>
                        <option value="bottom-right">Góc dưới phải</option>
                        <option value="bottom-left">Góc dưới trái</option>
                      </select>
                    </div>
                    <div>
                      <span className="text-zinc-400 block mb-0.5">Kích thước: {logoConfig.scale_pct}%</span>
                      <input
                        type="range"
                        min={5}
                        max={40}
                        value={logoConfig.scale_pct}
                        onChange={(e) => setLogoConfig((prev) => ({ ...prev, scale_pct: Number(e.target.value) }))}
                        className="w-full accent-cyan-400"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 3. Bàn hòa âm âm lượng (Full Audio Mixer) */}
          <div className="space-y-3 pt-2 border-t border-white/[0.06]">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-200">Bàn hòa âm xuất video</span>
              <span className="text-[10px] text-zinc-500">0% - 200% (+20dB)</span>
            </div>

            {/* Audio Mixer Deck */}
            <AudioMixerDeck
              viVoiceVol={voiceVol}
              bgmVol={bgmVol}
              onViVoiceVolChange={(vol) => {
                onVoiceVolChange(vol);
                if (jobId) bridge.saveProjectStyle(jobId, { voice_volume: vol, bgm_volume: bgmVol });
              }}
              onBgmVolChange={(vol) => {
                onBgmVolChange(vol);
                if (jobId) bridge.saveProjectStyle(jobId, { voice_volume: voiceVol, bgm_volume: vol });
              }}
              hasCustomBgm={Boolean(customBgmPath)}
              customBgmVol={customBgmVol}
              onCustomBgmVolChange={setCustomBgmVol}
            />

            {/* Channel 3: Nhạc nền tùy chỉnh (Custom BGM) */}
            <div className="space-y-1.5 pt-1 border-t border-white/[0.04]">
              <div className="flex items-center justify-between text-[11px] text-zinc-400">
                <span>Nhạc nền ngoài (Tùy chọn)</span>
                <span className="text-zinc-200">{customBgmVol}%</span>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={customBgmPath ? customBgmPath.split('\\').pop() : ''}
                  placeholder="Chưa chọn tệp nhạc ngoài..."
                  className="flex-1 bg-[#1A1A1E] border border-white/10 rounded px-2 py-1 text-[11px] text-zinc-400 truncate"
                />
                <button
                  type="button"
                  onClick={handleBrowseCustomBgm}
                  className="px-2 py-1 rounded bg-[#25252B] hover:bg-[#2F2F36] text-[11px] text-zinc-200 border border-white/[0.06]"
                >
                  Chọn nhạc
                </button>
              </div>
            </div>

            {/* Channel 4: Giọng gốc tiếng Trung (Orig Voice Passthrough) */}
            <div className="space-y-1.5 pt-1 border-t border-white/[0.04]">
              <div className="flex items-center justify-between text-[11px] text-zinc-400">
                <span>Giữ giọng gốc tiếng Trung</span>
                <span className="text-zinc-200">{origVoiceVol}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="200"
                value={origVoiceVol}
                onChange={(e) => setOrigVoiceVol(Number(e.target.value))}
                className="w-full accent-white cursor-pointer"
              />
            </div>
          </div>

          {/* 4. Hộp che chữ gốc / Text Box (ĐẶT Ở THỨ TỰ CUỐI CÙNG) */}
          <div className="p-2.5 rounded-lg bg-[#1B1B1F] border border-white/[0.04] space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold text-zinc-200">Hộp che chữ gốc / Text Box</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#25252B] text-zinc-400">{colorBoxes.length}</span>
              </div>
              <button
                type="button"
                onClick={handleAddBox}
                className="px-2 py-0.5 rounded bg-[#25252B] hover:bg-[#2F2F36] text-zinc-200 border border-white/[0.06] text-[11px] font-medium flex items-center gap-1 transition-colors shadow-sm"
              >
                <IconPlus size={11} />
                <span>Thêm hộp</span>
              </button>
            </div>

            {colorBoxes.length === 0 ? (
              <p className="text-[10px] text-zinc-500 leading-relaxed">
                Chưa có khối che nào. Nhấp <b>+ Thêm hộp</b> để che phụ đề tiếng Trung gốc hoặc chèn watermark tên kênh. Thao tác kéo thả trực tiếp trên khung xem trước.
              </p>
            ) : (
              <div className="space-y-2 pt-1 border-t border-white/[0.04]">
                {/* Selector + Enabled Toggle + Delete */}
                <div className="flex items-center gap-2">
                  <select
                    value={selectedBoxIndex}
                    onChange={(e) => setSelectedBoxIndex(Number(e.target.value))}
                    className="flex-1 min-w-0 bg-[#1A1A1E] border border-white/10 rounded px-2 py-1 text-xs text-zinc-200 focus:outline-none truncate"
                  >
                    {colorBoxes.map((b, idx) => (
                      <option key={b.id || idx} value={idx}>
                        Hộp #{idx + 1}{b.text ? `: ${b.text.slice(0, 12)}` : ''} ({b.w}% × {b.h}%)
                      </option>
                    ))}
                  </select>

                  {colorBoxes[selectedBoxIndex] && (
                    <label className="flex items-center gap-1 text-[11px] text-zinc-400 cursor-pointer shrink-0">
                      <input
                        type="checkbox"
                        checked={colorBoxes[selectedBoxIndex].enabled !== false}
                        onChange={(e) => handleUpdateSelectedBox({ enabled: e.target.checked })}
                        className="rounded bg-[#26262B] border-white/10 text-cyan-400 focus:ring-0"
                      />
                      <span>Bật</span>
                    </label>
                  )}

                  <button
                    type="button"
                    onClick={() => handleDeleteBox(selectedBoxIndex)}
                    className="p-1 rounded bg-[#25252B] hover:bg-red-950/60 text-zinc-400 hover:text-red-400 border border-white/[0.06] transition-colors shrink-0"
                    title="Xóa hộp này"
                  >
                    <IconTrash size={13} />
                  </button>
                </div>

                {colorBoxes[selectedBoxIndex] && (
                  <div className="space-y-2.5 text-[11px] text-zinc-400">
                    {/* Vị trí X & Y */}
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span>Vị trí X:</span>
                          <span className="text-zinc-200 font-mono">{colorBoxes[selectedBoxIndex].x}%</span>
                        </div>
                        <input
                          type="range"
                          min={0}
                          max={100}
                          step={0.5}
                          value={colorBoxes[selectedBoxIndex].x}
                          onChange={(e) => handleUpdateSelectedBox({ x: Number(e.target.value) })}
                          className="w-full accent-cyan-400"
                        />
                      </div>
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span>Vị trí Y:</span>
                          <span className="text-zinc-200 font-mono">{colorBoxes[selectedBoxIndex].y}%</span>
                        </div>
                        <input
                          type="range"
                          min={0}
                          max={100}
                          step={0.5}
                          value={colorBoxes[selectedBoxIndex].y}
                          onChange={(e) => handleUpdateSelectedBox({ y: Number(e.target.value) })}
                          className="w-full accent-cyan-400"
                        />
                      </div>
                    </div>

                    {/* Kích thước Rộng & Cao */}
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span>Chiều rộng:</span>
                          <span className="text-zinc-200 font-mono">{colorBoxes[selectedBoxIndex].w}%</span>
                        </div>
                        <input
                          type="range"
                          min={5}
                          max={100}
                          step={0.5}
                          value={colorBoxes[selectedBoxIndex].w}
                          onChange={(e) => handleUpdateSelectedBox({ w: Number(e.target.value) })}
                          className="w-full accent-cyan-400"
                        />
                      </div>
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span>Chiều cao:</span>
                          <span className="text-zinc-200 font-mono">{colorBoxes[selectedBoxIndex].h}%</span>
                        </div>
                        <input
                          type="range"
                          min={2}
                          max={50}
                          step={0.5}
                          value={colorBoxes[selectedBoxIndex].h}
                          onChange={(e) => handleUpdateSelectedBox({ h: Number(e.target.value) })}
                          className="w-full accent-cyan-400"
                        />
                      </div>
                    </div>

                    {/* Góc xoay khối (Rotation) */}
                    <div>
                      <div className="flex justify-between items-center mb-0.5">
                        <span className="text-zinc-300">Góc xoay khối:</span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-zinc-100 font-mono font-medium">{colorBoxes[selectedBoxIndex].rotation || 0}°</span>
                          {(colorBoxes[selectedBoxIndex].rotation || 0) !== 0 && (
                            <button
                              type="button"
                              onClick={() => handleUpdateSelectedBox({ rotation: 0 })}
                              className="px-1.5 py-0.2 rounded bg-[#25252B] hover:bg-[#2F2F36] text-[10px] text-cyan-300 border border-white/[0.06]"
                            >
                              Về 0°
                            </button>
                          )}
                        </div>
                      </div>
                      <input
                        type="range"
                        min={-180}
                        max={180}
                        step={1}
                        value={colorBoxes[selectedBoxIndex].rotation || 0}
                        onChange={(e) => handleUpdateSelectedBox({ rotation: Number(e.target.value) })}
                        className="w-full accent-cyan-400"
                      />
                    </div>

                    {/* Màu nền, Độ mờ & Bo góc */}
                    <div className="grid grid-cols-3 gap-2 items-center pt-1 border-t border-white/[0.04]">
                      <div>
                        <span className="block mb-0.5">Màu nền:</span>
                        <div className="flex items-center gap-1.5">
                          <input
                            type="color"
                            value={colorBoxes[selectedBoxIndex].color || '#000000'}
                            onChange={(e) => handleUpdateSelectedBox({ color: e.target.value })}
                            className="w-6 h-6 rounded border border-white/20 bg-transparent cursor-pointer p-0"
                          />
                          <span className="text-[10px] text-zinc-300 font-mono">{colorBoxes[selectedBoxIndex].color}</span>
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span>Độ mờ:</span>
                          <span className="text-zinc-200">{Math.round((colorBoxes[selectedBoxIndex].opacity ?? 0.85) * 100)}%</span>
                        </div>
                        <input
                          type="range"
                          min={10}
                          max={100}
                          value={Math.round((colorBoxes[selectedBoxIndex].opacity ?? 0.85) * 100)}
                          onChange={(e) => handleUpdateSelectedBox({ opacity: Number(e.target.value) / 100.0 })}
                          className="w-full accent-cyan-400"
                        />
                      </div>
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span>Bo góc:</span>
                          <span className="text-zinc-200">{colorBoxes[selectedBoxIndex].radius ?? 6}px</span>
                        </div>
                        <input
                          type="range"
                          min={0}
                          max={24}
                          value={colorBoxes[selectedBoxIndex].radius ?? 6}
                          onChange={(e) => handleUpdateSelectedBox({ radius: Number(e.target.value) })}
                          className="w-full accent-cyan-400"
                        />
                      </div>
                    </div>

                    {/* CHI TIẾT CHỮ (TEXT OVERLAY CONTROLS) */}
                    <div className="space-y-2 pt-1 border-t border-white/[0.04]">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-zinc-300 text-[11px]">Chữ hiển thị (Text Box):</span>
                        {colorBoxes[selectedBoxIndex].text && (
                          <button
                            type="button"
                            onClick={() => handleUpdateSelectedBox({ text: '' })}
                            className="text-[10px] text-zinc-400 hover:text-white"
                          >
                            Xóa chữ
                          </button>
                        )}
                      </div>

                      <input
                        type="text"
                        placeholder="Nhập nội dung chữ hiển thị lên hộp..."
                        value={colorBoxes[selectedBoxIndex].text || ''}
                        onChange={(e) => handleUpdateSelectedBox({ text: e.target.value })}
                        className="w-full bg-[#1A1A1E] border border-white/10 rounded px-2.5 py-1.5 text-xs text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-cyan-400"
                      />

                      {colorBoxes[selectedBoxIndex].text && (
                        <div className="space-y-2 pt-1 bg-[#141416] p-2 rounded-lg border border-white/[0.04]">
                          {/* Font family & Font size */}
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <span className="text-zinc-400 block mb-0.5">Phông chữ:</span>
                              <select
                                value={colorBoxes[selectedBoxIndex].font_name || 'Arial'}
                                onChange={(e) => handleUpdateSelectedBox({ font_name: e.target.value })}
                                className="w-full bg-[#1A1A1E] border border-white/10 rounded px-2 py-1 text-xs text-zinc-200 focus:outline-none"
                              >
                                <option value="Arial">Arial</option>
                                <option value="Times New Roman">Times New Roman</option>
                                <option value="Segoe UI">Segoe UI</option>
                                <option value="Roboto">Roboto</option>
                                <option value="Montserrat">Montserrat</option>
                                <option value="Tahoma">Tahoma</option>
                                <option value="Georgia">Georgia</option>
                                <option value="Impact">Impact</option>
                              </select>
                            </div>

                            <div>
                              <div className="flex justify-between mb-0.5">
                                <span>Cỡ chữ:</span>
                                <span className="text-zinc-200">{colorBoxes[selectedBoxIndex].font_size || 14}px</span>
                              </div>
                              <input
                                type="range"
                                min={10}
                                max={48}
                                value={colorBoxes[selectedBoxIndex].font_size || 14}
                                onChange={(e) => handleUpdateSelectedBox({ font_size: Number(e.target.value) })}
                                className="w-full accent-cyan-400"
                              />
                            </div>
                          </div>

                          {/* Alignment & Colors */}
                          <div className="grid grid-cols-3 gap-2 items-center">
                            {/* Text Align */}
                            <div>
                              <span className="text-zinc-400 block mb-0.5">Căn lề:</span>
                              <div className="flex rounded bg-[#1A1A1E] border border-white/10 overflow-hidden">
                                {(['left', 'center', 'right'] as const).map((al) => (
                                  <button
                                    key={al}
                                    type="button"
                                    onClick={() => handleUpdateSelectedBox({ text_align: al })}
                                    className={`flex-1 py-1 text-[10px] font-medium transition-colors ${
                                      (colorBoxes[selectedBoxIndex].text_align || 'center') === al
                                        ? 'bg-cyan-600 text-white'
                                        : 'text-zinc-400 hover:text-white'
                                    }`}
                                  >
                                    {al === 'left' ? 'Trái' : al === 'right' ? 'Phải' : 'Giữa'}
                                  </button>
                                ))}
                              </div>
                            </div>

                            {/* Text Color */}
                            <div>
                              <span className="text-zinc-400 block mb-0.5">Màu chữ:</span>
                              <div className="flex items-center gap-1">
                                <input
                                  type="color"
                                  value={colorBoxes[selectedBoxIndex].text_color || '#FFFFFF'}
                                  onChange={(e) => handleUpdateSelectedBox({ text_color: e.target.value })}
                                  className="w-5 h-5 rounded border border-white/20 bg-transparent cursor-pointer p-0"
                                />
                                <span className="text-[10px] text-zinc-300 font-mono">{colorBoxes[selectedBoxIndex].text_color || '#FFF'}</span>
                              </div>
                            </div>

                            {/* Text Outline Color & Width */}
                            <div>
                              <span className="text-zinc-400 block mb-0.5">Viền chữ:</span>
                              <div className="flex items-center gap-1">
                                <input
                                  type="color"
                                  value={colorBoxes[selectedBoxIndex].text_outline_color || '#000000'}
                                  onChange={(e) => handleUpdateSelectedBox({ text_outline_color: e.target.value })}
                                  className="w-5 h-5 rounded border border-white/20 bg-transparent cursor-pointer p-0"
                                />
                                <input
                                  type="range"
                                  min={0}
                                  max={6}
                                  value={colorBoxes[selectedBoxIndex].text_outline_width ?? 2}
                                  onChange={(e) => handleUpdateSelectedBox({ text_outline_width: Number(e.target.value) })}
                                  className="w-12 accent-cyan-400"
                                  title="Độ dày viền chữ"
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 4. Tên tệp & Thư mục lưu */}
          <div className="space-y-2 pt-2 border-t border-white/[0.06]">
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1">
                Tên video xuất ra
              </label>
              <input
                type="text"
                disabled={isExporting}
                value={outputTitle}
                onChange={(e) => setOutputTitle(e.target.value)}
                className="w-full bg-[#1F1F24] border border-white/[0.08] rounded-md px-3 py-1.5 text-xs text-zinc-100 focus:outline-none focus:border-cyan-400"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1">
                Thư mục lưu
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={targetDir}
                  placeholder="Thư mục out/"
                  className="flex-1 bg-[#1F1F24] border border-white/[0.08] rounded-md px-3 py-1.5 text-xs text-zinc-400 truncate"
                />
                <button
                  onClick={handleBrowseDir}
                  disabled={isExporting}
                  className="px-3 py-1.5 rounded-md bg-[#222227] hover:bg-[#2A2A30] text-zinc-200 text-xs font-medium border border-white/[0.08] flex items-center gap-1 transition-colors"
                >
                  <IconFolder size={13} />
                  <span>Chọn</span>
                </button>
              </div>
            </div>
          </div>

          {/* Progress / Success Info */}
          {(isExporting || exportSuccessPath || errorMessage) && (
            <div className="pt-2">
              <div className="flex items-center justify-between text-[11px] mb-1">
                <span className="text-zinc-400 font-medium truncate max-w-[260px]">
                  {statusMessage || (exportSuccessPath ? 'Hoàn thành' : 'Đang xử lý...')}
                </span>
                <span className="text-zinc-200 font-semibold">{progress}%</span>
              </div>
              <div className="w-full bg-[#27272A] h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-cyan-400 h-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>

              {exportSuccessPath && (
                <div className="mt-3 p-3 rounded-lg bg-emerald-950/40 border border-emerald-800/40 space-y-2">
                  <div className="text-emerald-300 text-xs font-medium flex items-center gap-1.5">
                    <IconCheck size={14} className="shrink-0 text-emerald-400" />
                    <span>Xuất video thành công!</span>
                  </div>
                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={() => bridge.openFilePath(exportSuccessPath)}
                      className="flex-1 py-1.5 rounded bg-emerald-900/60 hover:bg-emerald-800 text-emerald-200 text-xs font-medium flex items-center justify-center gap-1 transition-colors"
                    >
                      <IconPlay size={12} />
                      <span>Xem video ngay</span>
                    </button>
                    <button
                      onClick={() => bridge.openFolderPath(exportSuccessPath)}
                      className="flex-1 py-1.5 rounded bg-[#222227] hover:bg-[#2A2A30] text-zinc-300 text-xs font-medium flex items-center justify-center gap-1 transition-colors border border-white/[0.06]"
                    >
                      <IconFolder size={12} />
                      <span>Mở thư mục</span>
                    </button>
                  </div>
                </div>
              )}

              {errorMessage && (
                <div className="mt-3 p-2.5 rounded bg-red-950/40 border border-red-800/40 text-red-300 text-xs">
                  {errorMessage}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Start Export Button */}
        <div className="pt-4 border-t border-white/[0.06]">
          <button
            onClick={handleStartExport}
            disabled={isExporting}
            className="w-full py-2.5 rounded-lg bg-white hover:bg-zinc-200 text-black text-xs font-semibold flex items-center justify-center gap-2 transition-all active:scale-98 disabled:opacity-50 shadow-md"
          >
            <IconDownload size={14} />
            <span>{isExporting ? 'Đang kết xuất video...' : 'BẮT ĐẦU XUẤT VIDEO'}</span>
          </button>
        </div>
      </aside>
    </div>
  );
};