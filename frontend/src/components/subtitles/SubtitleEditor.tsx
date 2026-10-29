import React, { useState, useMemo, useEffect, useRef } from 'react';
import { 
  IconPlay, IconPause, IconPlus, IconTrash, 
  IconSearch, IconCheck, IconClose 
} from '../icons/StudioIcons';
import { FloatingContextMenu } from '../common/FloatingContextMenu';

export interface CueItem {
  id: number;
  start: number;
  end: number;
  text: string;
  vi_text?: string;
  orig?: string;
  source_text?: string;
  speaker?: string;
  speed?: number;
  voice?: string;
  cues?: Array<{ start: number; end: number; text: string; locked?: boolean }>;
  muted_sub?: boolean;
  muted_tts?: boolean;
  mute_sub?: boolean;
  mute_tts?: boolean;
  tts_file?: string;
  tts_dur?: number;
  voice_start?: number;
  voice_dur?: number;
  fit?: any;
  fit_rate?: number;
  has_tts?: boolean;
  gender?: string;
  user_edited_voice?: boolean;
}

interface SubtitleEditorProps {
  cues: CueItem[];
  activeCueId: number | null;
  playingCueId?: number | null;
  onSelectCue: (cueId: number) => void;
  onUpdateCue: (cueId: number, updates: Partial<CueItem>) => void;
  onBatchUpdateCues?: (updatedCues: CueItem[]) => void;
  onAddCue: (afterCueId?: number) => void;
  onDeleteCue: (cueId: number) => void;
  onPlayCue: (cue: CueItem) => void;
  onDoubleClickCue?: (cue: CueItem) => void;
}

export const formatTimestamp = (sec: number): string => {
  if (isNaN(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  const ms = Math.floor((sec % 1) * 10);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms}`;
};

export const SubtitleEditor: React.FC<SubtitleEditorProps> = ({
  cues,
  activeCueId,
  playingCueId,
  onSelectCue,
  onUpdateCue,
  onBatchUpdateCues,
  onAddCue,
  onDeleteCue,
  onPlayCue,
  onDoubleClickCue,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isFindReplaceOpen, setIsFindReplaceOpen] = useState(false);
  const [findText, setFindText] = useState('');
  const [replaceText, setReplaceText] = useState('');

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    cue: CueItem;
  } | null>(null);

  const activeCardRef = useRef<HTMLDivElement | null>(null);

  // Smooth auto-scroll to active card
  useEffect(() => {
    if (activeCueId !== null && activeCardRef.current) {
      activeCardRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      });
    }
  }, [activeCueId]);

  useEffect(() => {
    const handleClick = () => setContextMenu(null);
    window.addEventListener('click', handleClick);
    return () => window.removeEventListener('click', handleClick);
  }, []);

  // Filter cues based on simple search query
  const filteredCues = useMemo(() => {
    if (!searchQuery.trim()) return cues;
    const q = searchQuery.toLowerCase();
    return cues.filter(
      (c) =>
        c.text.toLowerCase().includes(q) ||
        (c.orig && c.orig.toLowerCase().includes(q)) ||
        (c.source_text && c.source_text.toLowerCase().includes(q))
    );
  }, [cues, searchQuery]);

  // Find & Replace match count
  const matchingCueIndices = useMemo(() => {
    if (!findText.trim()) return [];
    const q = findText.toLowerCase();
    const matched: number[] = [];
    cues.forEach((c, idx) => {
      if (c.text.toLowerCase().includes(q)) {
        matched.push(idx);
      }
    });
    return matched;
  }, [cues, findText]);

  // Find Next
  const handleFindNext = () => {
    if (matchingCueIndices.length === 0) return;
    const currentIdx = cues.findIndex((c) => c.id === activeCueId);
    const next = matchingCueIndices.find((idx) => idx > currentIdx);
    const targetIdx = next !== undefined ? next : matchingCueIndices[0];
    onSelectCue(cues[targetIdx].id);
  };

  // Replace Current
  const handleReplaceCurrent = () => {
    if (!findText.trim() || activeCueId === null) return;
    const target = cues.find((c) => c.id === activeCueId);
    if (!target) return;
    const re = new RegExp(findText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
    if (re.test(target.text)) {
      const newText = target.text.replace(re, replaceText);
      onUpdateCue(target.id, {
        text: newText,
        vi_text: newText,
        tts_text: newText,
        tts_hash: undefined,
        has_tts: false,
      } as any);
    }
  };

  // Replace All
  const handleReplaceAll = () => {
    if (!findText.trim()) return;
    const re = new RegExp(findText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    const updated = cues.map((c) => {
      if (re.test(c.text)) {
        const newText = c.text.replace(re, replaceText);
        return {
          ...c,
          text: newText,
          vi_text: newText,
          tts_text: newText,
          tts_hash: undefined,
          has_tts: false,
        };
      }
      return c;
    });
    if (onBatchUpdateCues) {
      onBatchUpdateCues(updated);
    } else {
      updated.forEach((c) =>
        onUpdateCue(c.id, {
          text: c.text,
          vi_text: c.text,
          tts_text: c.text,
          tts_hash: undefined,
          has_tts: false,
        } as any)
      );
    }
  };

  // Delete All Occurrences
  const handleDeleteAllFound = () => {
    if (!findText.trim()) return;
    const re = new RegExp(findText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    const updated = cues.map((c) => {
      if (re.test(c.text)) {
        const newText = c.text.replace(re, '').trim();
        return {
          ...c,
          text: newText,
          vi_text: newText,
          tts_text: newText,
          tts_hash: undefined,
          has_tts: false,
        };
      }
      return c;
    });
    if (onBatchUpdateCues) {
      onBatchUpdateCues(updated);
    } else {
      updated.forEach((c) =>
        onUpdateCue(c.id, {
          text: c.text,
          vi_text: c.text,
          tts_text: c.text,
          tts_hash: undefined,
          has_tts: false,
        } as any)
      );
    }
  };

  return (
    <aside className="w-84 bg-[#161619] border border-white/[0.06] rounded-lg flex flex-col shrink-0 overflow-hidden select-none">
      {/* 1. Header with Title & Cue Count */}
      <div className="px-3.5 py-2 border-b border-white/[0.06] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-zinc-200">Danh sách Phụ đề</span>
          <span className="text-[11px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
            {cues.length}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setIsFindReplaceOpen((prev) => !prev)}
            className={`px-2 py-1 rounded text-[11px] font-medium flex items-center gap-1 transition-colors border ${
              isFindReplaceOpen
                ? 'bg-cyan-950/80 border-cyan-400 text-cyan-200'
                : 'bg-[#222226] hover:bg-[#2A2A30] text-zinc-300 hover:text-white border-white/[0.06]'
            }`}
            title="Mở thanh Tìm kiếm & Thay thế (Find & Replace)"
          >
            <span>Tìm/Thay thế</span>
          </button>
          <button
            onClick={() => onAddCue(activeCueId ?? undefined)}
            className="px-2 py-1 rounded bg-[#222226] hover:bg-[#2A2A30] text-zinc-300 hover:text-white text-[11px] font-medium flex items-center gap-1 transition-colors border border-white/[0.06]"
            title="Thêm câu phụ đề mới"
          >
            <IconPlus size={12} />
            <span>Thêm</span>
          </button>
        </div>
      </div>

      {/* 2. Find & Replace Expandable Bar */}
      {isFindReplaceOpen && (
        <div className="p-2.5 bg-[#1B1B20] border-b border-white/[0.08] space-y-2 shrink-0 animate-fade-in text-xs">
          <div className="flex items-center justify-between pb-1 border-b border-white/[0.04]">
            <span className="text-[11px] font-semibold text-zinc-300">Tìm kiếm & Thay thế</span>
            <button
              onClick={() => setIsFindReplaceOpen(false)}
              className="text-zinc-500 hover:text-white p-0.5"
              title="Đóng (Esc)"
            >
              <IconClose size={11} />
            </button>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-zinc-400 w-12 font-medium">Tìm:</span>
            <input
              type="text"
              placeholder="Nhập từ cần tìm..."
              value={findText}
              onChange={(e) => setFindText(e.target.value)}
              spellCheck={false}
              autoCorrect="off"
              autoCapitalize="off"
              className="flex-1 bg-[#141416] border border-white/10 rounded px-2 py-1 text-zinc-200 text-xs focus:outline-none focus:border-cyan-400"
            />
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-zinc-400 w-12 font-medium">Thay thế:</span>
            <input
              type="text"
              placeholder="Thay thế bằng..."
              value={replaceText}
              onChange={(e) => setReplaceText(e.target.value)}
              spellCheck={false}
              autoCorrect="off"
              autoCapitalize="off"
              className="flex-1 bg-[#141416] border border-white/10 rounded px-2 py-1 text-zinc-200 text-xs focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="flex items-center justify-between pt-1">
            <span className="text-[10px] font-mono text-cyan-300">
              {findText ? `(${matchingCueIndices.length} câu khớp)` : ''}
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleFindNext}
                disabled={matchingCueIndices.length === 0}
                className="px-2 py-0.5 rounded bg-[#27272E] hover:bg-[#32323B] text-zinc-300 text-[10px] font-medium disabled:opacity-40"
              >
                Tìm tiếp
              </button>
              <button
                type="button"
                onClick={handleReplaceCurrent}
                disabled={!findText || activeCueId === null}
                className="px-2 py-0.5 rounded bg-[#27272E] hover:bg-[#32323B] text-zinc-300 text-[10px] font-medium disabled:opacity-40"
              >
                Thay thế
              </button>
              <button
                type="button"
                onClick={handleReplaceAll}
                disabled={matchingCueIndices.length === 0}
                className="px-2.5 py-0.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-[10px] font-semibold disabled:opacity-40 shadow-sm"
              >
                Tất cả
              </button>
              <button
                type="button"
                onClick={handleDeleteAllFound}
                disabled={matchingCueIndices.length === 0}
                className="px-2 py-0.5 rounded bg-red-950/60 hover:bg-red-900 border border-red-800/40 text-red-300 text-[10px] disabled:opacity-40"
                title="Xóa từ này khỏi tất cả câu"
              >
                Xóa từ
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3. Search Filter Input */}
      {!isFindReplaceOpen && (
        <div className="p-2 border-b border-white/[0.06] shrink-0">
          <div className="relative flex items-center">
            <IconSearch size={13} className="absolute left-2.5 text-zinc-500 pointer-events-none" />
            <input
              type="text"
              placeholder="Lọc nhanh câu thoại..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#1F1F23] border border-white/[0.06] rounded pl-7 pr-2.5 py-1 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-white/20 transition-colors"
            />
          </div>
        </div>
      )}

      {/* 4. Cue Cards List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 focus:outline-none">
        {filteredCues.length === 0 ? (
          <div className="h-full flex items-center justify-center p-4 text-center text-xs text-zinc-500">
            {cues.length === 0 ? 'Chưa có phụ đề trong dự án' : 'Không tìm thấy kết quả phù hợp'}
          </div>
        ) : (
          filteredCues.map((cue) => {
            const isSelected = activeCueId === cue.id;
            const isPlayingThis = playingCueId === cue.id;
            const originalText = cue.orig || cue.source_text || '';

            return (
              <div
                key={cue.id}
                ref={isSelected ? activeCardRef : null}
                onClick={() => onSelectCue(cue.id)}
                onDoubleClick={() => onDoubleClickCue?.(cue)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setContextMenu({
                    x: e.clientX,
                    y: e.clientY,
                    cue,
                  });
                }}
                className={`interactive-card p-2.5 rounded-md border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-[#222226] border-white/20 shadow-md ring-1 ring-cyan-500/30'
                    : (cue.mute_sub ?? cue.muted_sub)
                    ? 'bg-[#18181B]/40 border-white/[0.02] opacity-60'
                    : 'bg-[#1A1A1E]/60 border-white/[0.04] hover:bg-[#1E1E22] hover:border-white/[0.08]'
                }`}
                title="Nhấp đúp vào vùng trống/tiêu đề để mở chi tiết | Chuột phải mở menu"
              >
                {/* Meta row: Index, Timestamps, Audio preview, Delete */}
                <div className="flex items-center justify-between text-[11px] text-zinc-400 mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-zinc-400">#{cue.id}</span>
                    <span className="text-zinc-500">
                      {formatTimestamp(cue.start)} — {formatTimestamp(cue.end)}
                    </span>
                    <span className="text-[10px] text-zinc-600">
                      ({(cue.end - cue.start).toFixed(1)}s)
                    </span>
                    {(cue.mute_sub ?? cue.muted_sub) && (
                      <span className="text-[9px] px-1 rounded bg-zinc-800 text-zinc-400">Tắt sub</span>
                    )}
                    {(cue.mute_tts ?? cue.muted_tts) && (
                      <span className="text-[9px] px-1 rounded bg-zinc-800 text-zinc-400">Tắt TTS</span>
                    )}
                  </div>

                  <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => onPlayCue(cue)}
                      className={`p-1 rounded hover:bg-white/10 transition-colors ${
                        isPlayingThis ? 'text-white' : 'text-zinc-400 hover:text-zinc-200'
                      }`}
                      title={isPlayingThis ? 'Dừng phát' : 'Nghe thử câu này'}
                    >
                      {isPlayingThis ? <IconPause size={12} /> : <IconPlay size={12} />}
                    </button>
                    <button
                      onClick={() => onDeleteCue(cue.id)}
                      className="p-1 rounded hover:bg-white/10 text-zinc-500 hover:text-zinc-300 transition-colors"
                      title="Xóa câu"
                    >
                      <IconTrash size={12} />
                    </button>
                  </div>
                </div>

                {/* Target Subtitle Text (Vietnamese) - onDoubleClick stops propagation so text selection works! */}
                <div className="mt-1" onClick={(e) => e.stopPropagation()}>
                  <textarea
                    rows={2}
                    value={cue.text}
                    onFocus={() => onSelectCue(cue.id)}
                    onDoubleClick={(e) => e.stopPropagation()}
                    spellCheck={false}
                    autoCorrect="off"
                    autoCapitalize="off"
                    data-gramm="false"
                    data-gramm_editor="false"
                    data-enable-grammarly="false"
                    onChange={(e) =>
                      onUpdateCue(cue.id, {
                        text: e.target.value,
                        vi_text: e.target.value,
                        tts_text: e.target.value,
                        tts_hash: undefined,
                        has_tts: false,
                      } as any)
                    }
                    className={`w-full bg-[#18181B] border border-white/[0.06] focus:border-white/20 rounded p-1.5 text-xs text-zinc-100 placeholder-zinc-500 resize-none leading-relaxed focus:outline-none transition-colors ${
                      (cue.mute_sub ?? cue.muted_sub) ? 'line-through opacity-60' : ''
                    }`}
                    placeholder="Nhập nội dung phụ đề tiếng Việt..."
                  />
                </div>

                {/* Source Original Text (Chinese) */}
                {originalText && (
                  <div className="text-[11px] text-zinc-500 mt-1 font-light leading-relaxed truncate select-text">
                    {originalText}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Floating Context Menu rendered via createPortal on document.body */}
      {contextMenu && (
        <FloatingContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          triggerKey={contextMenu.cue.id}
          onClose={() => setContextMenu(null)}
        >
          <div className="px-3 py-1 text-[10px] text-zinc-500 border-b border-white/[0.04] truncate">
            Câu #{contextMenu.cue.id}: {(contextMenu.cue.vi_text || contextMenu.cue.text).slice(0, 24)}...
          </div>

          <button
            onClick={() => {
              onPlayCue(contextMenu.cue);
              setContextMenu(null);
            }}
            className="w-full px-3 py-1.5 text-left hover:bg-white/[0.08] flex items-center gap-2"
          >
            <IconPlay size={12} className="text-zinc-400" />
            <span>Nghe thử câu này</span>
          </button>

          <button
            onClick={() => {
              const nextVal = !(contextMenu.cue.mute_sub ?? contextMenu.cue.muted_sub);
              onUpdateCue(contextMenu.cue.id, { mute_sub: nextVal, muted_sub: nextVal });
              setContextMenu(null);
            }}
            className="w-full px-3 py-1.5 text-left hover:bg-white/[0.08] flex items-center gap-2"
          >
            <IconCheck size={12} className={(contextMenu.cue.mute_sub ?? contextMenu.cue.muted_sub) ? 'text-zinc-500' : 'text-emerald-400'} />
            <span>{(contextMenu.cue.mute_sub ?? contextMenu.cue.muted_sub) ? 'Bật lại phụ đề' : 'Tắt phụ đề câu này'}</span>
          </button>

          <button
            onClick={() => {
              const nextVal = !(contextMenu.cue.mute_tts ?? contextMenu.cue.muted_tts);
              onUpdateCue(contextMenu.cue.id, { mute_tts: nextVal, muted_tts: nextVal });
              setContextMenu(null);
            }}
            className="w-full px-3 py-1.5 text-left hover:bg-white/[0.08] flex items-center gap-2"
          >
            <IconCheck size={12} className={(contextMenu.cue.mute_tts ?? contextMenu.cue.muted_tts) ? 'text-zinc-500' : 'text-cyan-400'} />
            <span>{(contextMenu.cue.mute_tts ?? contextMenu.cue.muted_tts) ? 'Bật lại giọng đọc TTS' : 'Tắt giọng đọc TTS câu này'}</span>
          </button>

          <button
            onClick={() => {
              onDoubleClickCue?.(contextMenu.cue);
              setContextMenu(null);
            }}
            className="w-full px-3 py-1.5 text-left hover:bg-white/[0.08] flex items-center gap-2"
          >
            <span>Chỉnh sửa chi tiết...</span>
          </button>

          <div className="h-[1px] bg-white/[0.06] my-1" />

          <button
            onClick={() => {
              onDeleteCue(contextMenu.cue.id);
              setContextMenu(null);
            }}
            className="w-full px-3 py-1.5 text-left hover:bg-red-950/60 text-red-400 flex items-center gap-2"
          >
            <IconTrash size={12} />
            <span>Xóa câu thoại này</span>
          </button>
        </FloatingContextMenu>
      )}
    </aside>
  );
};
