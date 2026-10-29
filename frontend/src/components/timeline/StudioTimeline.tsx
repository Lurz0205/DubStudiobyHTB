import React, { useRef, useState, useEffect } from 'react';
import { CueItem } from '../subtitles/SubtitleEditor';
import { IconPlay, IconTrash, IconPlus, IconCheck } from '../icons/StudioIcons';
import { FloatingContextMenu } from '../common/FloatingContextMenu';

export interface OrigAudioRange {
  id: number;
  start: number;
  end: number;
}

interface StudioTimelineProps {
  cues: CueItem[];
  duration: number;
  currentTime: number;
  activeCueId: number | null;
  isPlaying?: boolean;
  origRanges?: OrigAudioRange[];
  onSeek: (time: number) => void;
  onSelectCue: (id: number) => void;
  onUpdateCueTimes: (id: number, start: number, end: number) => void;
  onDoubleClickCue: (cue: CueItem) => void;
  onUpdateCue?: (id: number, updates: Partial<CueItem>) => void;
  onDeleteCue?: (id: number) => void;
  onPlayCue?: (cue: CueItem) => void;
  onOrigRangesChange?: (ranges: OrigAudioRange[]) => void;
}

export const StudioTimeline: React.FC<StudioTimelineProps> = ({
  cues,
  duration,
  currentTime,
  activeCueId,
  isPlaying,
  origRanges = [],
  onSeek,
  onSelectCue,
  onUpdateCueTimes,
  onDoubleClickCue,
  onUpdateCue,
  onDeleteCue,
  onPlayCue,
  onOrigRangesChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState<number>(1.0); // 1.0 = fit, up to 8.0x

  const [dragAction, setDragAction] = useState<{
    type: 'seek' | 'move_cue' | 'resize_start' | 'resize_end' | 'pan_scroll' | 'move_orig' | 'resize_orig_start' | 'resize_orig_end';
    cueId?: number;
    origRangeId?: number;
    startX: number;
    origStart?: number;
    origEnd?: number;
    scrollLeftStart?: number;
  } | null>(null);

  // Context Menu state
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    cue?: CueItem;
    origRange?: OrigAudioRange;
  } | null>(null);

  const safeDuration = Math.max(1, duration);

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    const ms = Math.floor((secs % 1) * 10);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms}`;
  };

  const formatRulerTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // Close context menu on global click
  useEffect(() => {
    const handleClick = () => setContextMenu(null);
    window.addEventListener('click', handleClick);
    return () => window.removeEventListener('click', handleClick);
  }, []);

  // Pixels per second based on container width and zoom level
  const [containerWidth, setContainerWidth] = useState(800);
  useEffect(() => {
    const updateW = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.clientWidth || 800);
      }
    };
    updateW();
    window.addEventListener('resize', updateW);
    return () => window.removeEventListener('resize', updateW);
  }, []);

  const totalTrackWidth = Math.max(containerWidth, containerWidth * zoom);
  const pxPerSec = totalTrackWidth / safeDuration;

  // Generate ruler tick marks: major mark every 5s with number, minor ticks every 1s when zoomed
  const tickInterval = zoom >= 2 ? 1 : 5; // seconds
  const ticks: number[] = [];
  for (let t = 0; t <= safeDuration; t += tickInterval) {
    ticks.push(t);
  }

  // Auto-scroll timeline to follow playhead during playback if zoomed in
  useEffect(() => {
    if (!isPlaying || !scrollContainerRef.current || zoom <= 1.0) return;
    const el = scrollContainerRef.current;
    const playheadPx = currentTime * pxPerSec;
    if (playheadPx > el.scrollLeft + el.clientWidth - 40) {
      el.scrollLeft = playheadPx - 80;
    } else if (playheadPx < el.scrollLeft) {
      el.scrollLeft = Math.max(0, playheadPx - 40);
    }
  }, [isPlaying, currentTime, pxPerSec, zoom]);

  // Handle window mouse moves for dragging playhead, cue blocks, pan scroll, or orig ranges
  useEffect(() => {
    if (!dragAction) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!scrollContainerRef.current) return;

      if (dragAction.type === 'pan_scroll') {
        const dx = e.clientX - dragAction.startX;
        scrollContainerRef.current.scrollLeft = (dragAction.scrollLeftStart || 0) - dx;
        return;
      }

      const rect = scrollContainerRef.current.getBoundingClientRect();
      const xInContainer = e.clientX - rect.left + scrollContainerRef.current.scrollLeft;
      const timeAtCursor = Math.max(0, Math.min(safeDuration, xInContainer / pxPerSec));

      if (dragAction.type === 'seek') {
        onSeek(timeAtCursor);
      } else if (dragAction.type === 'move_cue' && dragAction.cueId !== undefined) {
        const dxSec = (e.clientX - dragAction.startX) / pxPerSec;
        const dur = (dragAction.origEnd || 0) - (dragAction.origStart || 0);
        let newStart = Math.max(0, (dragAction.origStart || 0) + dxSec);
        let newEnd = newStart + dur;
        if (newEnd > safeDuration) {
          newEnd = safeDuration;
          newStart = Math.max(0, newEnd - dur);
        }
        onUpdateCueTimes(dragAction.cueId, Math.round(newStart * 100) / 100, Math.round(newEnd * 100) / 100);
      } else if (dragAction.type === 'resize_start' && dragAction.cueId !== undefined) {
        const dxSec = (e.clientX - dragAction.startX) / pxPerSec;
        let newStart = (dragAction.origStart || 0) + dxSec;
        const origEnd = dragAction.origEnd || 1;
        newStart = Math.max(0, Math.min(origEnd - 0.2, newStart));
        onUpdateCueTimes(dragAction.cueId, Math.round(newStart * 100) / 100, Math.round(origEnd * 100) / 100);
      } else if (dragAction.type === 'resize_end' && dragAction.cueId !== undefined) {
        const dxSec = (e.clientX - dragAction.startX) / pxPerSec;
        let newEnd = (dragAction.origEnd || 0) + dxSec;
        const origStart = dragAction.origStart || 0;
        newEnd = Math.min(safeDuration, Math.max(origStart + 0.2, newEnd));
        onUpdateCueTimes(dragAction.cueId, Math.round(origStart * 100) / 100, Math.round(newEnd * 100) / 100);
      } else if (dragAction.type === 'move_orig' && dragAction.origRangeId !== undefined) {
        const dxSec = (e.clientX - dragAction.startX) / pxPerSec;
        const dur = (dragAction.origEnd || 0) - (dragAction.origStart || 0);
        let newStart = Math.max(0, (dragAction.origStart || 0) + dxSec);
        let newEnd = newStart + dur;
        if (newEnd > safeDuration) {
          newEnd = safeDuration;
          newStart = Math.max(0, newEnd - dur);
        }
        const updated = origRanges.map((r) =>
          r.id === dragAction.origRangeId
            ? { ...r, start: Math.round(newStart * 100) / 100, end: Math.round(newEnd * 100) / 100 }
            : r
        );
        onOrigRangesChange?.(updated);
      } else if (dragAction.type === 'resize_orig_start' && dragAction.origRangeId !== undefined) {
        const dxSec = (e.clientX - dragAction.startX) / pxPerSec;
        let newStart = (dragAction.origStart || 0) + dxSec;
        const origEnd = dragAction.origEnd || 1;
        newStart = Math.max(0, Math.min(origEnd - 0.2, newStart));
        const updated = origRanges.map((r) =>
          r.id === dragAction.origRangeId
            ? { ...r, start: Math.round(newStart * 100) / 100 }
            : r
        );
        onOrigRangesChange?.(updated);
      } else if (dragAction.type === 'resize_orig_end' && dragAction.origRangeId !== undefined) {
        const dxSec = (e.clientX - dragAction.startX) / pxPerSec;
        let newEnd = (dragAction.origEnd || 0) + dxSec;
        const origStart = dragAction.origStart || 0;
        newEnd = Math.min(safeDuration, Math.max(origStart + 0.2, newEnd));
        const updated = origRanges.map((r) =>
          r.id === dragAction.origRangeId
            ? { ...r, end: Math.round(newEnd * 100) / 100 }
            : r
        );
        onOrigRangesChange?.(updated);
      }
    };

    const handleMouseUp = () => {
      setDragAction(null);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragAction, safeDuration, pxPerSec, onSeek, onUpdateCueTimes, origRanges, onOrigRangesChange]);

  const handleRulerMouseDown = (e: React.MouseEvent) => {
    if (!scrollContainerRef.current) return;
    const rect = scrollContainerRef.current.getBoundingClientRect();

    // Ngăn chặn hoàn toàn việc tua video (seek) khi người dùng nhấp hoặc kéo thanh cuộn ngang ở đáy
    const scrollbarHeight = scrollContainerRef.current.offsetHeight - scrollContainerRef.current.clientHeight;
    if (
      (scrollbarHeight > 0 && e.clientY >= rect.top + scrollContainerRef.current.clientHeight) ||
      e.clientY >= rect.bottom - 15
    ) {
      return;
    }

    if (e.button === 2) {
      // Right click drag on empty space: pan scroll timeline
      e.preventDefault();
      setDragAction({
        type: 'pan_scroll',
        startX: e.clientX,
        scrollLeftStart: scrollContainerRef.current.scrollLeft,
      });
      return;
    }
    if (e.button !== 0) return;
    const xInContainer = e.clientX - rect.left + scrollContainerRef.current.scrollLeft;
    const timeAtCursor = Math.max(0, Math.min(safeDuration, xInContainer / pxPerSec));
    onSeek(timeAtCursor);
    setDragAction({ type: 'seek', startX: e.clientX });
  };

  const handleAddOrigRange = () => {
    const newStart = Math.round(currentTime * 100) / 100;
    const newEnd = Math.min(safeDuration, Math.round((currentTime + 3.0) * 100) / 100);
    const newId = Date.now();
    const updated = [...origRanges, { id: newId, start: newStart, end: newEnd }];
    onOrigRangesChange?.(updated);
  };

  const handleDeleteOrigRange = (id: number) => {
    const updated = origRanges.filter((r) => r.id !== id);
    onOrigRangesChange?.(updated);
  };

  return (
    <div 
      ref={containerRef}
      className="w-full bg-[#161619] border border-white/[0.06] rounded-xl flex flex-col overflow-hidden select-none shrink-0"
    >
      {/* 1. Header Toolbar with Zoom Controls & Giữ âm gốc */}
      <div className="px-3.5 py-1.5 border-b border-white/[0.06] flex items-center justify-between shrink-0 bg-[#1A1A1E]">
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-semibold text-zinc-300">
            TIMELINE ĐA KÊNH
          </span>
          <span className="text-[10px] text-zinc-500">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>

          {/* Nút Giữ âm gốc (màu xám) */}
          <button
            onClick={handleAddOrigRange}
            className="px-2.5 py-0.5 rounded bg-[#2A2A30] hover:bg-[#35353D] border border-white/10 text-zinc-200 text-[11px] font-medium flex items-center gap-1 transition-colors"
            title="Khoanh vùng giữ 100% âm thanh gốc của video (nhạc nền, tiếng gốc không bị cắt)"
          >
            <IconPlus size={11} />
            <span>Vùng âm gốc</span>
          </button>
        </div>

        {/* Zoom controls & Nav */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => onSeek(0)}
            className="px-2 py-0.5 rounded bg-[#25252B] hover:bg-[#2F2F36] text-[11px] text-zinc-300 font-medium transition-colors"
            title="Về đầu video"
          >
            Về đầu
          </button>
          <button
            onClick={() => setZoom(1.0)}
            className="px-2 py-0.5 rounded bg-[#25252B] hover:bg-[#2F2F36] text-[11px] text-zinc-300 font-medium transition-colors"
            title="Vừa khít màn hình"
          >
            Vừa khung
          </button>
          <div className="flex items-center gap-1 bg-[#222227] px-2 py-0.5 rounded border border-white/[0.04]">
            <button
              onClick={() => setZoom((prev) => Math.max(1.0, prev - 0.5))}
              className="text-zinc-400 hover:text-white text-xs px-1 font-bold"
              title="Thu nhỏ timeline"
            >
              -
            </button>
            <input
              type="range"
              min="1.0"
              max="6.0"
              step="0.2"
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
              className="w-16 accent-white cursor-pointer h-1"
            />
            <button
              onClick={() => setZoom((prev) => Math.min(6.0, prev + 0.5))}
              className="text-zinc-400 hover:text-white text-xs px-1 font-bold"
              title="Phóng to timeline"
            >
              +
            </button>
            <span className="text-[10px] text-zinc-400 w-7 text-right">
              {zoom.toFixed(1)}x
            </span>
          </div>
        </div>
      </div>

      {/* 2. Scrollable Timeline Ruler & Tracks */}
      <div 
        ref={scrollContainerRef}
        onMouseDown={handleRulerMouseDown}
        onContextMenu={(e) => e.preventDefault()}
        className="w-full overflow-x-auto overflow-y-hidden relative bg-[#111114]"
        style={{ height: '142px' }}
      >
        <div 
          style={{ width: `${totalTrackWidth}px`, height: '100%' }}
          className="relative flex flex-col"
        >
          {/* Time Ruler (Click/Drag to Seek, Right-click to Pan) */}
          <div className="w-full h-6 bg-[#18181C] border-b border-white/[0.06] relative cursor-pointer flex items-center">
            {ticks.map((t) => {
              const x = t * pxPerSec;
              const isMajor = Math.round(t) % 5 === 0;
              return (
                <div
                  key={t}
                  style={{ left: `${x}px` }}
                  className="absolute top-0 bottom-0 flex flex-col justify-between pointer-events-none"
                >
                  {isMajor ? (
                    <span className="text-[9px] text-zinc-400 pl-1 leading-none font-medium">
                      {formatRulerTime(t)}
                    </span>
                  ) : (
                    <span className="h-3" />
                  )}
                  <div className={`w-[1px] ${isMajor ? 'h-2.5 bg-zinc-500' : 'h-1.5 bg-zinc-700/60'}`} />
                </div>
              );
            })}
          </div>

          {/* Track 1: Subtitle Cues Blocks */}
          <div className="w-full h-10 relative border-b border-white/[0.04] bg-[#141417] flex items-center">
            <span className="absolute left-2 text-[9px] font-bold text-zinc-600 uppercase pointer-events-none z-0">
              Phụ đề (Cues)
            </span>
            {cues.map((c) => {
              const left = c.start * pxPerSec;
              const width = Math.max(16, (c.end - c.start) * pxPerSec);
              const isSelected = c.id === activeCueId;

              return (
                <div
                  key={c.id}
                  style={{
                    left: `${left}px`,
                    width: `${width}px`,
                  }}
                  onDoubleClick={(e) => {
                    e.stopPropagation();
                    onDoubleClickCue(c);
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectCue(c.id);
                    onSeek(c.start);
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setContextMenu({
                      x: e.clientX,
                      y: e.clientY,
                      cue: c,
                    });
                  }}
                  className={`absolute h-7 rounded border text-[11px] flex items-center px-2 z-10 transition-all ${
                    isSelected
                      ? 'bg-cyan-950/70 border-cyan-400 text-cyan-200 shadow-md ring-1 ring-cyan-400/50'
                      : (c.mute_sub ?? c.muted_sub)
                      ? 'bg-[#1C1C22]/50 border-white/[0.04] text-zinc-500 line-through'
                      : 'bg-[#25252C] border-white/10 text-zinc-300 hover:border-white/30 hover:bg-[#2C2C35]'
                  }`}
                  title={`#${c.id}: ${c.vi_text || c.text} (${c.start.toFixed(2)}s -> ${c.end.toFixed(2)}s) - Chuột trái để kéo, Chuột phải mở menu`}
                >
                  {/* Left Resize Handle (Left click only) */}
                  <div
                    onMouseDown={(e) => {
                      if (e.button !== 0) return;
                      e.stopPropagation();
                      setDragAction({
                        type: 'resize_start',
                        cueId: c.id,
                        startX: e.clientX,
                        origStart: c.start,
                        origEnd: c.end,
                      });
                    }}
                    className="absolute left-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-white/40 rounded-l"
                    title="Kéo chỉnh thời gian bắt đầu"
                  />

                  {/* Middle Drag & Label (Left click only) */}
                  <div 
                    onMouseDown={(e) => {
                      if (e.button !== 0) return;
                      e.stopPropagation();
                      setDragAction({
                        type: 'move_cue',
                        cueId: c.id,
                        startX: e.clientX,
                        origStart: c.start,
                        origEnd: c.end,
                      });
                    }}
                    className="flex-1 truncate cursor-grab active:cursor-grabbing font-medium select-none"
                  >
                    <span className="text-[10px] opacity-70 mr-1">#{c.id}</span>
                    <span>{c.vi_text || c.text}</span>
                  </div>

                  {/* Right Resize Handle (Left click only) */}
                  <div
                    onMouseDown={(e) => {
                      if (e.button !== 0) return;
                      e.stopPropagation();
                      setDragAction({
                        type: 'resize_end',
                        cueId: c.id,
                        startX: e.clientX,
                        origStart: c.start,
                        origEnd: c.end,
                      });
                    }}
                    className="absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-white/40 rounded-r"
                    title="Kéo chỉnh thời gian kết thúc"
                  />
                </div>
              );
            })}
          </div>

          {/* Track 2: Dubbing Voice Audio (TTS) - REAL audio files only */}
          <div className="w-full h-8 relative border-b border-white/[0.04] bg-[#111114] flex items-center">
            <span className="absolute left-2 text-[9px] font-bold text-zinc-600 uppercase pointer-events-none z-0">
              Lồng tiếng (TTS)
            </span>
            {cues.map((c) => {
              // Only render if real TTS audio has actually been generated
              const hasRealAudio = Boolean(c.tts_file || c.has_tts || (c.tts_dur && c.tts_dur > 0));
              if (!hasRealAudio) return null;

              const left = (c.voice_start !== undefined ? c.voice_start : c.start) * pxPerSec;
              const dur = (c.voice_dur && c.voice_dur > 0)
                ? c.voice_dur
                : (c.end > c.start ? (c.end - c.start) : (c.tts_dur || 0));
              const width = Math.max(14, dur * pxPerSec);

              return (
                <div
                  key={`audio-${c.id}`}
                  style={{
                    left: `${left}px`,
                    width: `${width}px`,
                  }}
                  className={`absolute h-5 rounded border text-[9px] flex items-center px-1.5 pointer-events-none overflow-hidden ${
                    (c.mute_tts ?? c.muted_tts)
                      ? 'bg-zinc-800/40 border-zinc-700/30 text-zinc-500 opacity-50'
                      : 'bg-emerald-950/60 border-emerald-500/30 text-emerald-300'
                  }`}
                >
                  <span className="truncate">♪ #{c.id} {c.voice ? `(${c.voice})` : ''}</span>
                </div>
              );
            })}
          </div>

          {/* Track 3: Âm gốc 🎵 (Keep Original Audio Ranges) */}
          <div className="w-full h-8 relative bg-[#131317] flex items-center">
            <span className="absolute left-2 text-[9px] font-bold text-zinc-600 uppercase pointer-events-none z-0">
              Âm gốc 🎵
            </span>
            {origRanges.map((r) => {
              const left = r.start * pxPerSec;
              const width = Math.max(16, (r.end - r.start) * pxPerSec);

              return (
                <div
                  key={r.id}
                  style={{
                    left: `${left}px`,
                    width: `${width}px`,
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setContextMenu({
                      x: e.clientX,
                      y: e.clientY,
                      origRange: r,
                    });
                  }}
                  className="absolute h-5.5 rounded bg-purple-950/70 border border-purple-500/40 text-purple-200 text-[10px] flex items-center px-1.5 z-10 group shadow-sm"
                  title={`🎵 Giữ âm gốc: ${r.start.toFixed(1)}s → ${r.end.toFixed(1)}s (Kéo mép để co giãn, Chuột phải để xóa)`}
                >
                  {/* Left resize handle */}
                  <div
                    onMouseDown={(e) => {
                      if (e.button !== 0) return;
                      e.stopPropagation();
                      setDragAction({
                        type: 'resize_orig_start',
                        origRangeId: r.id,
                        startX: e.clientX,
                        origStart: r.start,
                        origEnd: r.end,
                      });
                    }}
                    className="absolute left-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-purple-300/40 rounded-l"
                  />

                  {/* Body drag */}
                  <div
                    onMouseDown={(e) => {
                      if (e.button !== 0) return;
                      e.stopPropagation();
                      setDragAction({
                        type: 'move_orig',
                        origRangeId: r.id,
                        startX: e.clientX,
                        origStart: r.start,
                        origEnd: r.end,
                      });
                    }}
                    className="flex-1 truncate cursor-grab active:cursor-grabbing font-medium select-none"
                  >
                    <span className="text-[9px]">🎵 {r.start.toFixed(1)}s - {r.end.toFixed(1)}s</span>
                  </div>

                  {/* Right resize handle */}
                  <div
                    onMouseDown={(e) => {
                      if (e.button !== 0) return;
                      e.stopPropagation();
                      setDragAction({
                        type: 'resize_orig_end',
                        origRangeId: r.id,
                        startX: e.clientX,
                        origStart: r.start,
                        origEnd: r.end,
                      });
                    }}
                    className="absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-purple-300/40 rounded-r"
                  />
                </div>
              );
            })}
          </div>

          {/* Playhead Vertical Line & Sleek Modern Badge */}
          <div
            style={{
              left: `${currentTime * pxPerSec}px`,
              willChange: 'left',
            }}
            className="absolute top-0 bottom-0 w-[1.5px] bg-gradient-to-b from-cyan-300 via-cyan-400 to-cyan-500 z-30 pointer-events-none shadow-[0_0_8px_rgba(34,211,238,0.7),0_0_1.5px_rgba(255,255,255,0.9)]"
          >
            {/* Modern High-Precision Marker Badge (DaVinci/Premiere needle pointer) */}
            <div className="-ml-[5.25px] -mt-[1px] select-none pointer-events-none drop-shadow-[0_0_6px_rgba(34,211,238,0.85)]">
              <svg
                width="12"
                height="15"
                viewBox="0 0 12 15"
                fill="none"
                className="filter"
              >
                <path
                  d="M0 2C0 0.895431 0.895431 0 2 0H10C11.1046 0 12 0.895431 12 2V9C12 9.42968 11.8623 9.84752 11.6074 10.1925L6.60742 14.6925C6.26207 15.0033 5.73793 15.0033 5.39258 14.6925L0.392578 10.1925C0.137684 9.84752 0 9.42968 0 9V2Z"
                  fill="#22D3EE"
                />
                <line x1="6" y1="2.5" x2="6" y2="9.5" stroke="#083344" strokeWidth="1.2" strokeLinecap="round" opacity="0.6" />
              </svg>
            </div>

            {/* Luminous bottom anchor dot */}
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-300 -ml-[2.25px] shadow-[0_0_6px_rgba(34,211,238,0.9)] absolute bottom-0 pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Floating Context Menu rendered via createPortal on document.body */}
      {contextMenu && (
        <FloatingContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          triggerKey={contextMenu.cue?.id ?? contextMenu.origRange?.id}
          onClose={() => setContextMenu(null)}
        >
          {contextMenu.cue && (
            <>
              <div className="px-3 py-1 text-[10px] text-zinc-500 border-b border-white/[0.04] truncate">
                Câu #{contextMenu.cue.id}: {(contextMenu.cue.vi_text || contextMenu.cue.text).slice(0, 24)}...
              </div>

              {onPlayCue && (
                <button
                  onClick={() => {
                    if (contextMenu.cue) onPlayCue(contextMenu.cue);
                    setContextMenu(null);
                  }}
                  className="w-full px-3 py-1.5 text-left hover:bg-white/[0.08] flex items-center gap-2"
                >
                  <IconPlay size={12} className="text-zinc-400" />
                  <span>Nghe thử câu này</span>
                </button>
              )}

              {onUpdateCue && (
                <>
                  <button
                    onClick={() => {
                      if (contextMenu.cue) {
                        const nextVal = !(contextMenu.cue.mute_sub ?? contextMenu.cue.muted_sub);
                        onUpdateCue(contextMenu.cue.id, { mute_sub: nextVal, muted_sub: nextVal });
                      }
                      setContextMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left hover:bg-white/[0.08] flex items-center gap-2"
                  >
                    <IconCheck size={12} className={(contextMenu.cue.mute_sub ?? contextMenu.cue.muted_sub) ? 'text-zinc-500' : 'text-emerald-400'} />
                    <span>{(contextMenu.cue.mute_sub ?? contextMenu.cue.muted_sub) ? 'Bật lại phụ đề' : 'Tắt phụ đề câu này'}</span>
                  </button>

                  <button
                    onClick={() => {
                      if (contextMenu.cue) {
                        const nextVal = !(contextMenu.cue.mute_tts ?? contextMenu.cue.muted_tts);
                        onUpdateCue(contextMenu.cue.id, { mute_tts: nextVal, muted_tts: nextVal });
                      }
                      setContextMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left hover:bg-white/[0.08] flex items-center gap-2"
                  >
                    <IconCheck size={12} className={(contextMenu.cue.mute_tts ?? contextMenu.cue.muted_tts) ? 'text-zinc-500' : 'text-cyan-400'} />
                    <span>{(contextMenu.cue.mute_tts ?? contextMenu.cue.muted_tts) ? 'Bật lại giọng đọc TTS' : 'Tắt giọng đọc TTS câu này'}</span>
                  </button>
                </>
              )}

              <button
                onClick={() => {
                  if (contextMenu.cue) onDoubleClickCue(contextMenu.cue);
                  setContextMenu(null);
                }}
                className="w-full px-3 py-1.5 text-left hover:bg-white/[0.08] flex items-center gap-2"
              >
                <span>Chỉnh sửa chi tiết...</span>
              </button>

              {onDeleteCue && (
                <>
                  <div className="h-[1px] bg-white/[0.06] my-1" />
                  <button
                    onClick={() => {
                      if (contextMenu.cue) onDeleteCue(contextMenu.cue.id);
                      setContextMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left hover:bg-red-950/60 text-red-400 flex items-center gap-2"
                  >
                    <IconTrash size={12} />
                    <span>Xóa câu thoại này</span>
                  </button>
                </>
              )}
            </>
          )}

          {contextMenu.origRange && (
            <>
              <div className="px-3 py-1 text-[10px] text-purple-300 border-b border-white/[0.04]">
                🎵 Vùng giữ âm gốc ({contextMenu.origRange.start.toFixed(1)}s → {contextMenu.origRange.end.toFixed(1)}s)
              </div>
              <button
                onClick={() => {
                  if (contextMenu.origRange) handleDeleteOrigRange(contextMenu.origRange.id);
                  setContextMenu(null);
                }}
                className="w-full px-3 py-1.5 text-left hover:bg-red-950/60 text-red-400 flex items-center gap-2"
              >
                <IconTrash size={12} />
                <span>Xóa vùng giữ âm gốc này</span>
              </button>
            </>
          )}
        </FloatingContextMenu>
      )}
    </div>
  );
};