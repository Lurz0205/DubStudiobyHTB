import React, { useState, useRef, useEffect, useCallback } from 'react';
import { SubtitleEditor, CueItem } from './subtitles/SubtitleEditor';
import { WYSIWYGPlayer, SubtitleStyle } from './video/WYSIWYGPlayer';
import { SubtitleStylePanel } from './subtitles/SubtitleStylePanel';
import { StudioTimeline, OrigAudioRange } from './timeline/StudioTimeline';
import { EditSentenceModal } from './dialogs/EditSentenceModal';
import { ManualTranslateModal } from './modals/ManualTranslateModal';
import { 
  IconPlus, IconScissors, 
  IconChevronRight 
} from './icons/StudioIcons';
import { bridge, ProjectSummary, PipelineEvent, DEFAULT_MALE_VOICES, DEFAULT_FEMALE_VOICES } from '../api/bridge';

interface StudioWorkspaceProps {
  jobId: string;
  projectTitle: string;
  allProjects: ProjectSummary[];
  onSelectProject: (id: string, title?: string) => void;
  onOpenNewVideo: () => void;
  videoSrc?: string;
  voiceSrc?: string;
  bgmSrc?: string;
  origVoiceSrc?: string;
  cues: CueItem[];
  onCuesChange: (cues: CueItem[]) => void;
  subtitleStyle?: SubtitleStyle;
  onSubtitleStyleChange?: (style: SubtitleStyle) => void;
  aspectRatio: string;
  onAspectRatioChange: (ratio: string) => void;
  voiceVol: number;
  bgmVol: number;
  onVoiceVolChange: (vol: number) => void;
  onBgmVolChange: (vol: number) => void;
  onNavigateToExport: () => void;
  isActiveTab?: boolean;
  settingsVersion?: number;
}

export const StudioWorkspace: React.FC<StudioWorkspaceProps> = ({
  jobId,
  allProjects,
  onSelectProject,
  onOpenNewVideo,
  videoSrc,
  voiceSrc,
  bgmSrc,
  origVoiceSrc,
  cues,
  onCuesChange,
  subtitleStyle: externalSubtitleStyle,
  onSubtitleStyleChange: onExternalSubtitleStyleChange,
  aspectRatio,
  onAspectRatioChange,
  voiceVol = 100,
  bgmVol = 100,
  onVoiceVolChange: _onVoiceVolChange,
  onBgmVolChange: _onBgmVolChange,
  onNavigateToExport,
  isActiveTab = true,
  settingsVersion = 0,
}) => {
  // Playback state
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeCueId, setActiveCueId] = useState<number | null>(null);
  const [playingCueId, setPlayingCueId] = useState<number | null>(null);

  // Automatically pause playback when switching away from this tab
  useEffect(() => {
    if (!isActiveTab) {
      setIsPlaying(false);
      setPlayingCueId(null);
    }
  }, [isActiveTab]);

  // Subtitle styling matching v1.1.3 style.json 100%
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle>({
    font_name: 'Arial',
    fontSize: 26,
    primary_color: '#FFFFFF',
    outline_color: '#000000',
    outline_width: 2,
    has_box: true,
    box_color: '#000000',
    box_opacity: 0.6,
    box_radius: 6,
    box_mode: 'full_width',
    box_width_pct: 85,
    position: 'bottom',
    marginV: 35,
  });

  // Modal for editing sentence on double-click
  const [editingCue, setEditingCue] = useState<CueItem | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  // Manual Translation Modal
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [manualPrompt, setManualPrompt] = useState('');
  const [manualTotalItems, setManualTotalItems] = useState(0);

  // Original audio ranges (Track Âm gốc 🎵)
  const [origRanges, setOrigRanges] = useState<OrigAudioRange[]>([]);

  // Toolbar state (reconstructed 100% from v1.1.3)
  const [styleTone, setStyleTone] = useState('Tự nhiên, đời thường');
  const [detectGender, setDetectGender] = useState(false);
  const [singleGender, setSingleGender] = useState<'male' | 'female'>('male');
  const [voiceMale, setVoiceMale] = useState('Minh Đức');
  const [voiceFemale, setVoiceFemale] = useState('Quỳnh Anh');
  const [selectedVoice, setSelectedVoice] = useState('Minh Đức');
  const [wordsPerLine, setWordsPerLine] = useState(6);

  // Pipeline execution state
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  const [pipelineProgress, setPipelineProgress] = useState(0);
  const [pipelineMessage, setPipelineMessage] = useState('');
  const [pipelineStage, setPipelineStage] = useState('');

  const cueStopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load system default voices from App Settings
  useEffect(() => {
    bridge.getAppSettings().then((s) => {
      if (s) {
        if (s.default_male_voice) setVoiceMale(s.default_male_voice);
        if (s.default_female_voice) setVoiceFemale(s.default_female_voice);
        if (s.default_male_voice) setSelectedVoice(s.default_male_voice);
      }
    });
  }, [settingsVersion]);

  // Listen to pipeline events for this job
  useEffect(() => {
    const unsub = bridge.onPipelineEvent((ev: PipelineEvent) => {
      if (ev.job_id && ev.job_id !== jobId) return;

      if (ev.stage !== 'render') {
        setIsRunningPipeline(ev.level !== 'success' && ev.level !== 'error');
        setPipelineProgress(Math.round(ev.progress));
        setPipelineMessage(ev.message);
        setPipelineStage(ev.stage);

        if (ev.level === 'manual_input_required') {
          const evtData = (ev as any).data;
          if (evtData && evtData.prompt) {
            setManualPrompt(evtData.prompt);
            setManualTotalItems(evtData.total_items || 0);
            setIsManualModalOpen(true);
          } else {
            bridge.getManualTranslatePrompt(jobId).then((res) => {
              if (res && res.prompt) {
                setManualPrompt(res.prompt);
                setManualTotalItems(res.total_items || 0);
                setIsManualModalOpen(true);
              }
            });
          }
        }

        if (ev.level === 'success') {
          // Refresh cues upon completion
          bridge.getProjectData(jobId).then((data) => {
            if (data && data.segments) {
              const formatted = data.segments.map((s: any, idx: number) => ({
                ...s,
                id: s.id || idx + 1,
                start: s.start || 0,
                end: s.end || 0,
                text: s.vi_text || s.text || '',
                orig: s.orig || s.zh || s.zh_text || '',
              }));
              onCuesChange(formatted);
            }
            if (data && typeof data.duration === 'number' && data.duration > 0) {
              setDuration((prev) => (prev > 0 ? prev : data.duration));
            }
          });
        }
      }
    });
    return unsub;
  }, [jobId, onCuesChange]);

  useEffect(() => {
    if (externalSubtitleStyle) {
      setSubtitleStyle(externalSubtitleStyle);
    }
  }, [externalSubtitleStyle]);

  // Load project config, subtitle style, and cues whenever jobId or active state changes
  useEffect(() => {
    if (!jobId || !isActiveTab) return;
    bridge.getProjectData(jobId).then((data) => {
      if (data && data.config) {
        if (data.config.words_per_line) setWordsPerLine(data.config.words_per_line);
        if (data.config.translation_tone) setStyleTone(data.config.translation_tone);
        if (typeof data.config.detect_gender === 'boolean') setDetectGender(data.config.detect_gender);
        if (data.config.single_voice_gender) setSingleGender(data.config.single_voice_gender);
        const vMale = data.config.voice_male || data.config.default_male_voice || 'Minh Đức';
        const vFemale = data.config.voice_female || data.config.default_female_voice || 'Quỳnh Anh';
        setVoiceMale(vMale);
        setVoiceFemale(vFemale);
        if (data.config.single_voice) {
          setSelectedVoice(data.config.single_voice);
        } else if (data.config.single_voice_gender === 'female') {
          setSelectedVoice(vFemale);
        } else {
          setSelectedVoice(vMale);
        }
      }
      if (data && data.style) {
        const mergedStyle: SubtitleStyle = {
          ...subtitleStyle,
          ...data.style,
          fontSize: data.style.font_size || data.style.fontSize || subtitleStyle.fontSize,
          marginV: data.style.margin_v || data.style.marginV || subtitleStyle.marginV,
        };
        setSubtitleStyle(mergedStyle);
        onExternalSubtitleStyleChange?.(mergedStyle);

        if (data.style.keep_original_ranges && Array.isArray(data.style.keep_original_ranges)) {
          const loadedRanges: OrigAudioRange[] = data.style.keep_original_ranges.map((r: any, idx: number) => ({
            id: idx + 1,
            start: Number(r[0] || 0),
            end: Number(r[1] || 0),
          }));
          setOrigRanges(loadedRanges);
        } else {
          setOrigRanges([]);
        }
      }

      // Synchronize cues to timeline whenever entering studio tab or changing project
      if (data && data.segments && Array.isArray(data.segments) && data.segments.length > 0) {
        const formatted: CueItem[] = data.segments.map((s: any, idx: number) => ({
          ...s,
          id: s.id || idx + 1,
          start: s.start || 0,
          end: s.end || 0,
          text: s.vi_text || s.text || '',
          orig: s.orig || s.zh || s.zh_text || '',
        }));
        onCuesChange(formatted);
      }

      if (data && typeof data.duration === 'number' && data.duration > 0) {
        setDuration((prev) => (prev > 0 ? prev : data.duration));
      }
    });
  }, [jobId, isActiveTab]);

  const handleOrigRangesChange = (ranges: OrigAudioRange[]) => {
    setOrigRanges(ranges);
    if (jobId) {
      bridge.saveProjectStyle(jobId, {
        keep_original_ranges: ranges.map((r) => [r.start, r.end]),
      });
    }
  };

  const handleSubtitleStyleChange = (updates: Partial<SubtitleStyle>) => {
    setSubtitleStyle((prev) => {
      const next = { ...prev, ...updates };
      if (jobId) {
        bridge.saveProjectStyle(jobId, next);
      }
      onExternalSubtitleStyleChange?.(next);
      return next;
    });
  };

  const handleTimeUpdate = useCallback((t: number) => {
    setCurrentTime(t);
  }, []);

  // Determine active cue from current video playback time
  useEffect(() => {
    const current = cues.find((c) => currentTime >= c.start && currentTime <= c.end);
    if (current && current.id !== activeCueId) {
      setActiveCueId(current.id);
    }
  }, [currentTime, cues, activeCueId]);

  // Determine current playback cue strictly by timestamp
  const activeCue = cues.find((c) => currentTime >= c.start && currentTime <= c.end);

  const activeSubtitle = (() => {
    if (!activeCue) return '';
    if (activeCue.mute_sub || (activeCue as any).muted_sub) return '';
    // Chỉ hiển thị phụ đề nếu currentTime thực sự nằm trong phạm vi thời lượng của câu (cả khi phát lẫn khi tạm dừng)
    if (currentTime < activeCue.start || currentTime > activeCue.end) {
      return '';
    }
    const raw = (activeCue.text || '').trim();
    if (!raw) return '';

    // 1. Explicit sub-cues with timestamps - only use if text matches activeCue.text!
    if (activeCue.cues && Array.isArray(activeCue.cues) && activeCue.cues.length > 0) {
      const joinedSubText = activeCue.cues.map((sc: any) => sc.text || '').join(' ').replace(/\s+/g, ' ').trim();
      const normRaw = raw.replace(/\s+/g, ' ').trim();
      if (joinedSubText === normRaw || joinedSubText.replace(/[.,!?;:…—\-]/g, '') === normRaw.replace(/[.,!?;:…—\-]/g, '')) {
        const match = activeCue.cues.find((sc: any) => currentTime >= sc.start && currentTime <= sc.end);
        if (match && match.text) return match.text.trim();
      }
    }

    // 2. Sequential Sub-segment Timing based on _effective_weight matching cue_split.py 1:1
    if (raw.includes('\n')) {
      const lines = raw.split('\n').map((l) => l.trim()).filter(Boolean);
      if (lines.length > 1) {
        const totalDur = Math.max(0.1, activeCue.end - activeCue.start);
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

        let currT = activeCue.start;
        for (let i = 0; i < lines.length; i++) {
          const ratio = weights[i] / totalW;
          const lineDur = (i === lines.length - 1) ? (activeCue.end - currT) : (totalDur * ratio);
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

  // Synchronize audio elements with video playback
  const handlePlayPause = useCallback(() => {
    if (cueStopTimerRef.current) {
      clearTimeout(cueStopTimerRef.current);
      cueStopTimerRef.current = null;
    }
    setPlayingCueId(null);
    setIsPlaying((prev) => !prev);
  }, []);

  // Global Spacebar shortcut to Toggle Play/Pause when not editing inputs
  useEffect(() => {
    if (!isActiveTab) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' || e.key === ' ') {
        const target = e.target as HTMLElement | null;
        if (target) {
          const tag = target.tagName.toLowerCase();
          if (tag === 'input' || tag === 'textarea' || target.isContentEditable) {
            return;
          }
        }
        e.preventDefault();
        handlePlayPause();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isActiveTab, handlePlayPause]);

  const handleSeek = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  // Update cue text or timestamp
  const handleUpdateCue = (cueId: number, updates: Partial<CueItem>) => {
    const updated = cues.map((c) => {
      if (c.id === cueId) {
        const item = { ...c, ...updates };
        const textChanged = updates.text !== undefined && updates.text !== c.text;
        const voiceChanged = updates.voice !== undefined && updates.voice !== c.voice;
        const speedChanged = updates.speed !== undefined && updates.speed !== c.speed;
        const startChanged = updates.start !== undefined && Math.abs(updates.start - c.start) > 0.01;
        const endChanged = updates.end !== undefined && Math.abs(updates.end - c.end) > 0.01;
        const timeChanged = startChanged || endChanged;

        const newStart = updates.start !== undefined ? Number(updates.start) : Number(c.start);
        const newEnd = updates.end !== undefined ? Number(updates.end) : Number(c.end);
        const oldStart = Number(c.start);
        const oldEnd = Number(c.end);
        const oldDur = Math.max(0.05, oldEnd - oldStart);
        const newDur = Math.max(0.05, newEnd - newStart);

        if (timeChanged) {
          // Proportionally scale sub-cues / sub-slices so timeline and preview display correctly immediately
          if (item.cues && Array.isArray(item.cues) && item.cues.length > 0) {
            item.cues = item.cues.map((sc: any) => {
              const relSt = Math.max(0, Math.min(1, ((sc.start ?? oldStart) - oldStart) / oldDur));
              const relEn = Math.max(0, Math.min(1, ((sc.end ?? oldEnd) - oldStart) / oldDur));
              return {
                ...sc,
                start: Math.round((newStart + relSt * newDur) * 1000) / 1000,
                end: Math.round((newStart + relEn * newDur) * 1000) / 1000,
              };
            });
          }
          if ((item as any).sub_slices && Array.isArray((item as any).sub_slices) && (item as any).sub_slices.length > 0) {
            (item as any).sub_slices = (item as any).sub_slices.map((sc: any) => {
              const relSt = Math.max(0, Math.min(1, ((sc.start ?? oldStart) - oldStart) / oldDur));
              const relEn = Math.max(0, Math.min(1, ((sc.end ?? oldEnd) - oldStart) / oldDur));
              return {
                ...sc,
                start: Math.round((newStart + relSt * newDur) * 1000) / 1000,
                end: Math.round((newStart + relEn * newDur) * 1000) / 1000,
              };
            });
          }
        }

        if (textChanged) {
          (item as any).vi_text = updates.text;
          (item as any).tts_text = updates.text;
          (item as any).cues = undefined; // Invalidate outdated sub-slices so preview immediately uses new text!
          (item as any).sub_slices = undefined;
        }
        if (voiceChanged) {
          (item as any).user_edited_voice = Boolean(updates.voice);
        }
        if (textChanged || voiceChanged || speedChanged) {
          (item as any).tts_hash = undefined;
          item.has_tts = false;
        }
        return item;
      }
      return c;
    });
    onCuesChange(updated);
    if (jobId) {
      bridge.saveProjectSegments(jobId, updated);
    }
  };

  // Batch update all cues (e.g. Find & Replace All) in a single atomic save
  const handleBatchUpdateCues = (newCues: CueItem[]) => {
    const synced = newCues.map((c) => {
      const orig = cues.find((old) => old.id === c.id);
      if (orig && c.text !== orig.text) {
        return {
          ...c,
          vi_text: c.text,
          tts_text: c.text,
          cues: undefined,
          sub_slices: undefined,
          tts_hash: undefined,
          has_tts: false,
        };
      }
      return c;
    });
    onCuesChange(synced);
    if (jobId) {
      bridge.saveProjectSegments(jobId, synced);
    }
  };

  // Add new cue
  const handleAddCue = (afterCueId?: number) => {
    let newStart = 0;
    let newEnd = 3.0;

    if (afterCueId !== undefined) {
      const target = cues.find((c) => c.id === afterCueId);
      if (target) {
        newStart = target.end + 0.1;
        newEnd = newStart + 2.5;
      }
    } else if (cues.length > 0) {
      const last = cues[cues.length - 1];
      newStart = last.end + 0.1;
      newEnd = newStart + 2.5;
    }

    const newCue: CueItem = {
      id: cues.length > 0 ? Math.max(...cues.map((c) => c.id)) + 1 : 1,
      start: parseFloat(newStart.toFixed(2)),
      end: parseFloat(newEnd.toFixed(2)),
      text: 'Nội dung phụ đề mới',
      orig: '',
    };

    const updated = [...cues, newCue].sort((a, b) => a.start - b.start);
    onCuesChange(updated);
    setActiveCueId(newCue.id);
    if (jobId) {
      bridge.saveProjectSegments(jobId, updated);
    }
  };

  // Delete cue
  const handleDeleteCue = (cueId: number) => {
    const updated = cues.filter((c) => c.id !== cueId);
    onCuesChange(updated);
    if (activeCueId === cueId) {
      setActiveCueId(updated.length > 0 ? updated[0].id : null);
    }
    if (jobId) {
      bridge.saveProjectSegments(jobId, updated);
    }
  };

  // Play a specific cue (sentence)
  const handlePlayCue = (cue: CueItem) => {
    if (playingCueId === cue.id) {
      setPlayingCueId(null);
      setIsPlaying(false);
      if (cueStopTimerRef.current) clearTimeout(cueStopTimerRef.current);
      return;
    }

    setPlayingCueId(cue.id);
    setActiveCueId(cue.id);
    handleSeek(cue.start);
    setIsPlaying(true);

    if (cueStopTimerRef.current) clearTimeout(cueStopTimerRef.current);
    const durationMs = Math.max(200, (cue.end - cue.start) * 1000);
    cueStopTimerRef.current = setTimeout(() => {
      setIsPlaying(false);
      setPlayingCueId(null);
    }, durationMs);
  };

  // Auto split cues strictly using native Python DP cue_split.py engine
  const handleAutoSplit = async () => {
    if (!jobId) return;
    try {
      const res = await bridge.autoSplitCues(jobId, wordsPerLine);
      if (res && res.status === 'success' && res.segments) {
        const formatted: CueItem[] = res.segments.map((s: any, idx: number) => ({
          ...s,
          id: s.id || idx + 1,
          start: s.start || 0,
          end: s.end || 0,
          text: s.text || s.vi_text || '',
          orig: s.orig || s.zh || s.src_text || '',
          voice: s.voice || (detectGender ? (s.gender === 'female' ? voiceFemale : voiceMale) : selectedVoice),
          speed: s.speed || 1.0,
          cues: s.cues,
          has_tts: Boolean(s.tts_file || s.has_tts || (s.tts_dur && s.tts_dur > 0)),
        }));
        onCuesChange(formatted);
      }
    } catch (e) {
      console.error('Failed to auto split cues with cue_split.py', e);
    }
  };

  // Run Step 1: Subtitles Pipeline (Ingest -> Separate -> ASR -> Translate)
  const handleRunSubtitles = async () => {
    if (!jobId) return;
    setIsRunningPipeline(true);
    setPipelineProgress(5);
    setPipelineMessage('Bắt đầu nhận dạng Whisper và dịch thuật LLM...');
    await bridge.runPipeline(jobId, {
      subtitles_only: true,
      style: styleTone,
      detect_gender: detectGender,
      single_voice_gender: singleGender,
      single_voice: selectedVoice,
      voice_male: voiceMale,
      voice_female: voiceFemale,
      words_per_line: wordsPerLine,
    });
  };

  // Run Step 2: Dub Pipeline (TTS -> Fit -> Mix)
  const handleRunDub = async () => {
    if (!jobId) return;
    setIsRunningPipeline(true);
    setPipelineProgress(5);
    setPipelineMessage('Bắt đầu tạo giọng đọc tiếng Việt và khớp timeline...');
    try {
      await bridge.saveProjectSegments(jobId, cues);
    } catch (e) {
      console.warn('Pre-save cues before dub failed:', e);
    }
    await bridge.runPipeline(jobId, {
      dub_only: true,
      style: styleTone,
      detect_gender: detectGender,
      single_voice_gender: singleGender,
      single_voice: selectedVoice,
      voice_male: voiceMale,
      voice_female: voiceFemale,
      words_per_line: wordsPerLine,
    });
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#121214] select-none">

      {/* ─── TOOLBAR (2 ROWS) — Khôi phục 100% chức năng từ v1.1.3 ─── */}
      <header className="bg-[#161619] border-b border-white/[0.06] px-4 py-2.5 space-y-2 shrink-0">
        {/* Row 1: Tác vụ | Văn phong | Giọng */}
        <div className="flex items-center gap-3 text-xs">
          {/* Job Selector */}
          <div className="flex items-center gap-2">
            <span className="text-zinc-400 font-medium shrink-0">Tác vụ:</span>
            <div className="relative inline-flex items-center">
              <select
                value={jobId}
                onChange={(e) => onSelectProject(e.target.value)}
                className="appearance-none bg-[#1A1A1E] hover:bg-[#222226] border border-white/[0.08] hover:border-white/20 text-zinc-100 rounded-md pl-2.5 pr-7 py-1 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-zinc-400 min-w-[140px] max-w-[220px] truncate transition-all cursor-pointer shadow-sm"
              >
                {allProjects.map((p) => (
                  <option key={p.id} value={p.id} className="bg-[#1A1A1E] text-zinc-100">
                    {p.title}
                  </option>
                ))}
              </select>
              <span className="pointer-events-none absolute right-2 text-zinc-500 text-[9px]">▼</span>
            </div>
            <button
              onClick={onOpenNewVideo}
              className="px-2.5 py-1 rounded bg-[#222227] hover:bg-[#2A2A30] text-zinc-300 hover:text-white text-xs font-medium border border-white/[0.06] flex items-center gap-1 transition-colors"
              title="Thêm tệp video mới"
            >
              <IconPlus size={12} />
              <span>Thêm</span>
            </button>
          </div>

          <div className="h-4 w-[1px] bg-white/[0.08]" />

          {/* Tone / Văn phong */}
          <div className="flex items-center gap-2">
            <span className="text-zinc-400 font-medium shrink-0">Văn phong:</span>
            <div className="relative inline-flex items-center">
              <select
                value={styleTone}
                onChange={(e) => {
                  const t = e.target.value;
                  setStyleTone(t);
                  if (jobId) bridge.saveProjectConfig(jobId, { translation_tone: t });
                }}
                className="appearance-none bg-[#1A1A1E] hover:bg-[#222226] border border-white/[0.08] hover:border-white/20 text-zinc-100 rounded-md pl-2.5 pr-7 py-1 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-zinc-400 transition-all cursor-pointer shadow-sm"
              >
                <option value="Tự nhiên, đời thường" className="bg-[#1A1A1E]">Tự nhiên, đời thường</option>
                <option value="Hài hước, hóm hỉnh" className="bg-[#1A1A1E]">Hài hước, hóm hỉnh</option>
                <option value="Trang trọng, tài liệu" className="bg-[#1A1A1E]">Trang trọng, tài liệu</option>
                <option value="Kiếm hiệp, cổ trang" className="bg-[#1A1A1E]">Kiếm hiệp, cổ trang</option>
                <option value="Trẻ trung, hiện đại (Gen Z)" className="bg-[#1A1A1E]">Trẻ trung, hiện đại (Gen Z)</option>
              </select>
              <span className="pointer-events-none absolute right-2 text-zinc-500 text-[9px]">▼</span>
            </div>
          </div>

          <div className="h-4 w-[1px] bg-white/[0.08]" />

          {/* Gender Mode Toggle */}
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 cursor-pointer text-zinc-300">
              <input
                type="checkbox"
                checked={detectGender}
                onChange={(e) => {
                  const g = e.target.checked;
                  setDetectGender(g);
                  if (jobId) bridge.saveProjectConfig(jobId, { detect_gender: g });
                }}
                className="rounded bg-[#1F1F24] border-white/10 text-white focus:ring-0 cursor-pointer"
              />
              <span>Chia Nam/Nữ</span>
            </label>

            {!detectGender ? (
              <div className="flex items-center gap-1.5">
                <span className="text-zinc-500">Giọng:</span>
                <div className="relative inline-flex items-center">
                  <select
                    value={selectedVoice}
                    onChange={(e) => {
                      const v = e.target.value;
                      setSelectedVoice(v);
                      const isFem = DEFAULT_FEMALE_VOICES.includes(v);
                      const g = isFem ? 'female' : 'male';
                      setSingleGender(g);
                      if (jobId) {
                        bridge.saveProjectConfig(jobId, {
                          single_voice: v,
                          single_voice_gender: g,
                        });
                      }
                    }}
                    className="appearance-none bg-[#1A1A1E] hover:bg-[#222226] border border-white/[0.08] hover:border-white/20 text-zinc-100 rounded-md pl-2 pr-6 py-1 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-zinc-400 transition-all cursor-pointer shadow-sm max-w-[130px] truncate"
                  >
                    <optgroup label="Giọng Nam" className="bg-[#1A1A1E]">
                      {DEFAULT_MALE_VOICES.map((v) => (
                        <option key={v} value={v} className="bg-[#1A1A1E]">{v}</option>
                      ))}
                    </optgroup>
                    <optgroup label="Giọng Nữ" className="bg-[#1A1A1E]">
                      {DEFAULT_FEMALE_VOICES.map((v) => (
                        <option key={v} value={v} className="bg-[#1A1A1E]">{v}</option>
                      ))}
                    </optgroup>
                  </select>
                  <span className="pointer-events-none absolute right-1.5 text-zinc-500 text-[9px]">▼</span>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1">
                  <span className="text-zinc-500">Nam:</span>
                  <div className="relative inline-flex items-center">
                    <select
                      value={voiceMale}
                      onChange={(e) => {
                        const v = e.target.value;
                        setVoiceMale(v);
                        if (jobId) bridge.saveProjectConfig(jobId, { voice_male: v, default_male_voice: v });
                      }}
                      className="appearance-none bg-[#1A1A1E] hover:bg-[#222226] border border-white/[0.08] hover:border-white/20 text-zinc-100 rounded-md pl-2 pr-6 py-1 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-zinc-400 transition-all cursor-pointer shadow-sm max-w-[110px] truncate"
                    >
                      {DEFAULT_MALE_VOICES.map((v) => (
                        <option key={v} value={v} className="bg-[#1A1A1E]">{v}</option>
                      ))}
                    </select>
                    <span className="pointer-events-none absolute right-1.5 text-zinc-500 text-[9px]">▼</span>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-zinc-500">Nữ:</span>
                  <div className="relative inline-flex items-center">
                    <select
                      value={voiceFemale}
                      onChange={(e) => {
                        const v = e.target.value;
                        setVoiceFemale(v);
                        if (jobId) bridge.saveProjectConfig(jobId, { voice_female: v, default_female_voice: v });
                      }}
                      className="appearance-none bg-[#1A1A1E] hover:bg-[#222226] border border-white/[0.08] hover:border-white/20 text-zinc-100 rounded-md pl-2 pr-6 py-1 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-zinc-400 transition-all cursor-pointer shadow-sm max-w-[110px] truncate"
                    >
                      {DEFAULT_FEMALE_VOICES.map((v) => (
                        <option key={v} value={v} className="bg-[#1A1A1E]">{v}</option>
                      ))}
                    </select>
                    <span className="pointer-events-none absolute right-1.5 text-zinc-500 text-[9px]">▼</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Row 2: Từ/dòng + Tách tự động | Pipeline Bước 1, Bước 2, Bước 3 */}
        <div className="flex items-center justify-between gap-4 pt-1 border-t border-white/[0.04] text-xs">
          {/* Left: Words per line & Auto split */}
          <div className="flex items-center gap-2">
            <span className="text-zinc-400 font-medium">Từ/dòng:</span>
            <input
              type="number"
              min={3}
              max={25}
              value={wordsPerLine}
              onChange={(e) => setWordsPerLine(Math.max(3, Math.min(25, Number(e.target.value))))}
              className="w-14 bg-[#1F1F24] border border-white/[0.08] text-center text-zinc-100 rounded py-1 text-xs focus:outline-none"
            />
            <button
              onClick={handleAutoSplit}
              className="px-2.5 py-1 rounded bg-[#222227] hover:bg-[#2A2A30] text-zinc-300 hover:text-white text-xs font-medium border border-white/[0.06] flex items-center gap-1.5 transition-colors"
              title="Tự động ngắt nhịp toàn bộ câu theo số từ chỉ định"
            >
              <IconScissors size={12} />
              <span>Tách tự động</span>
            </button>
          </div>

          {/* Right: 3 Core Workflow Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleRunSubtitles}
              disabled={isRunningPipeline}
              className="px-3.5 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold flex items-center justify-center transition-all active:scale-98 disabled:opacity-50 shadow-sm"
              title="Bước 1: Nhận dạng Whisper & Dịch tiếng Trung sang tiếng Việt"
            >
              <span>1. Tạo phụ đề</span>
            </button>

            <button
              onClick={handleRunDub}
              disabled={isRunningPipeline}
              className="px-3.5 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold flex items-center justify-center transition-all active:scale-98 disabled:opacity-50 shadow-sm"
              title="Bước 2: Tạo giọng đọc thuyết minh tiếng Việt và khớp timeline"
            >
              <span>2. Tạo lồng tiếng</span>
            </button>

            <button
              onClick={onNavigateToExport}
              className="px-3.5 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold flex items-center gap-1.5 transition-all active:scale-98 shadow-sm"
              title="Bước 3: Chuyển sang chỉnh sửa video và xuất file hoàn thiện"
            >
              <span>3. Chỉnh sửa & Xuất</span>
              <IconChevronRight size={13} />
            </button>
          </div>
        </div>

        {/* Real-time Pipeline Progress Bar */}
        {isRunningPipeline && (
          <div className="pt-2">
            <div className="flex items-center justify-between text-[11px] mb-1">
              <span className="text-zinc-300 font-medium flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>{pipelineMessage || `Đang xử lý ${pipelineStage}...`}</span>
              </span>
              <span className="text-zinc-300 font-semibold">{pipelineProgress}%</span>
            </div>
            <div className="w-full bg-[#27272A] h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-white h-full transition-all duration-300"
                style={{ width: `${pipelineProgress}%` }}
              />
            </div>
          </div>
        )}
      </header>

      {/* ─── MAIN WORKSPACE (SPLIT LAYOUT) ─── */}
      <div className="flex-1 p-3 flex gap-3 overflow-hidden">
        {/* Left: Subtitle Editor Column */}
        <SubtitleEditor
          cues={cues}
          activeCueId={activeCueId}
          playingCueId={playingCueId}
          onSelectCue={(id) => {
            setActiveCueId(id);
            const c = cues.find((item) => item.id === id);
            if (c) handleSeek(c.start);
          }}
          onUpdateCue={handleUpdateCue}
          onBatchUpdateCues={handleBatchUpdateCues}
          onAddCue={handleAddCue}
          onDeleteCue={handleDeleteCue}
          onPlayCue={handlePlayCue}
          onDoubleClickCue={(cue) => {
            setEditingCue(cue);
            setIsEditModalOpen(true);
          }}
        />

        {/* Center: WYSIWYG Video & Canvas Player */}
        <section className="flex-1 bg-[#161619] border border-white/[0.06] rounded-lg flex flex-col overflow-hidden min-h-0">
          <WYSIWYGPlayer
            videoSrc={videoSrc}
            activeSubtitle={activeSubtitle}
            cues={cues}
            subtitleStyle={subtitleStyle}
            onSubtitleStyleChange={handleSubtitleStyleChange}
            aspectRatio={aspectRatio}
            onAspectRatioChange={onAspectRatioChange}
            voiceSrc={voiceSrc}
            bgmSrc={bgmSrc}
            origVoiceSrc={origVoiceSrc}
            voiceVol={voiceVol}
            bgmVol={bgmVol}
            origRanges={origRanges}
            currentTime={currentTime}
            duration={duration || 1}
            isPlaying={isPlaying}
            onPlayPauseToggle={handlePlayPause}
            onSeek={handleSeek}
            onTimeUpdate={handleTimeUpdate}
            onDurationChange={(d) => setDuration(d)}
          />
        </section>

        {/* Right: Subtitle Styling Deck (100% Dedicated to Subtitles) */}
        <aside className="w-80 bg-[#161619] border border-white/[0.06] rounded-lg p-3.5 flex flex-col justify-between shrink-0 overflow-y-auto">
          <div className="space-y-4">
            <div className="pb-2 border-b border-white/[0.06] flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-200">Kiểu dáng phụ đề</span>
            </div>

            <SubtitleStylePanel
              style={subtitleStyle}
              onChange={handleSubtitleStyleChange}
            />
          </div>

          {/* Reset Action */}
          <div className="pt-3 border-t border-white/[0.06]">
            <button
              onClick={() => {
                const defaultSty: SubtitleStyle = {
                  font_name: 'Arial',
                  fontSize: 26,
                  font_size: 26,
                  primary_color: '#FFFFFF',
                  outline_color: '#000000',
                  outline_width: 2,
                  has_box: true,
                  box_color: '#000000',
                  box_opacity: 0.6,
                  box_radius: 6,
                  box_mode: 'full_width',
                  box_width_pct: 85,
                  pos_y_pct: 86.0,
                  position: 'bottom',
                  marginV: 35,
                  margin_v: 35,
                };
                setSubtitleStyle(defaultSty);
                if (jobId) bridge.saveProjectStyle(jobId, defaultSty);
              }}
              className="w-full py-2 rounded bg-[#222226] hover:bg-[#2A2A30] text-zinc-300 text-xs font-medium transition-colors border border-white/[0.04]"
            >
              Khôi phục mặc định kiểu chữ
            </button>
          </div>
        </aside>
      </div>

      {/* ─── BOTTOM: Full Interactive Timeline Component ─── */}
      <div className="px-3 pb-3 shrink-0">
        <StudioTimeline
          cues={cues}
          duration={duration || 1}
          currentTime={currentTime}
          isPlaying={isPlaying}
          activeCueId={activeCueId}
          origRanges={origRanges}
          onOrigRangesChange={handleOrigRangesChange}
          onSeek={handleSeek}
          onSelectCue={(id) => {
            setActiveCueId(id);
            const c = cues.find((item) => item.id === id);
            if (c) handleSeek(c.start);
          }}
          onUpdateCueTimes={(id, st, en) => {
            handleUpdateCue(id, { start: st, end: en });
          }}
          onDoubleClickCue={(cue) => {
            setEditingCue(cue);
            setIsEditModalOpen(true);
          }}
          onUpdateCue={handleUpdateCue}
          onDeleteCue={handleDeleteCue}
          onPlayCue={handlePlayCue}
        />
      </div>

      {/* ─── EDIT SENTENCE MODAL (DOUBLE CLICK) ─── */}
      <EditSentenceModal
        isOpen={isEditModalOpen}
        cue={editingCue}
        jobId={jobId}
        onClose={() => setIsEditModalOpen(false)}
        onSave={(updated) => {
          if (editingCue) {
            handleUpdateCue(editingCue.id, updated);
          }
        }}
        onPlaySnippet={(st, en) => {
          handleSeek(st);
          setIsPlaying(true);
          if (cueStopTimerRef.current) clearTimeout(cueStopTimerRef.current);
          cueStopTimerRef.current = setTimeout(() => {
            setIsPlaying(false);
          }, Math.max(0.5, en - st) * 1000);
        }}
      />

      {/* ─── MANUAL TRANSLATE MODAL ─── */}
      <ManualTranslateModal
        isOpen={isManualModalOpen}
        jobId={jobId}
        promptText={manualPrompt}
        totalItems={manualTotalItems}
        onClose={() => setIsManualModalOpen(false)}
        onSubmitSuccess={() => {
          setIsManualModalOpen(false);
        }}
      />
    </div>
  );
};
