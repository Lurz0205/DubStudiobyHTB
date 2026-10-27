import React, { useState, useEffect } from 'react';
import { CueItem } from '../subtitles/SubtitleEditor';
import { bridge, DEFAULT_MALE_VOICES, DEFAULT_FEMALE_VOICES } from '../../api/bridge';
import { 
  IconCheck, IconPlay, IconScissors 
} from '../icons/StudioIcons';

interface EditSentenceModalProps {
  isOpen: boolean;
  cue: CueItem | null;
  jobId: string;
  onClose: () => void;
  onSave: (updated: Partial<CueItem>) => void;
  onPlaySnippet?: (start: number, end: number) => void;
}

export const EditSentenceModal: React.FC<EditSentenceModalProps> = ({
  isOpen,
  cue,
  jobId,
  onClose,
  onSave,
  onPlaySnippet,
}) => {
  if (!isOpen || !cue) return null;

  const [start, setStart] = useState<number>(cue.start);
  const [end, setEnd] = useState<number>(cue.end);
  const [speed, setSpeed] = useState<number>(cue.speed || 1.0);
  const [voice, setVoice] = useState<string>(cue.voice || '');
  const [viText, setViText] = useState<string>(cue.text || '');
  const zhText = cue.orig || cue.source_text || '';

  const [copiedZh, setCopiedZh] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [synthSuccess, setSynthSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isClosing, setIsClosing] = useState(false);

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(() => {
      setIsClosing(false);
      onClose();
    }, 160);
  };

  useEffect(() => {
    if (!cue) return;
    setIsClosing(false);
    setStart(cue.start);
    setEnd(cue.end);
    setSpeed(cue.speed || 1.0);
    setVoice(cue.voice || '');
    setViText(cue.text || '');
    setCopiedZh(false);
    setSynthSuccess(false);
    setErrorMessage(null);
  }, [cue]);

  const duration = Math.max(0, end - start);

  const handleCopyZh = async () => {
    if (!zhText) return;
    try {
      await navigator.clipboard.writeText(zhText);
      setCopiedZh(true);
      setTimeout(() => setCopiedZh(false), 2000);
    } catch {
      // Fallback
      setCopiedZh(true);
      setTimeout(() => setCopiedZh(false), 2000);
    }
  };

  const handleAutoBreak = () => {
    // Break into natural lines of ~6 words per line
    const words = viText.trim().split(/\s+/);
    if (words.length <= 6) return;
    const lines: string[] = [];
    for (let i = 0; i < words.length; i += 6) {
      lines.push(words.slice(i, i + 6).join(' '));
    }
    setViText(lines.join('\n'));
  };

  const handleSynthesizeTTS = async () => {
    if (!jobId || !cue) return;
    setIsSynthesizing(true);
    setErrorMessage(null);
    setSynthSuccess(false);

    try {
      const res = await bridge.synthesizeSingleSegment(jobId, cue.id, {
        text: viText,
        speed: speed,
        voice: voice || undefined,
      });

      if (res && res.status === 'success') {
        setSynthSuccess(true);
        setTimeout(() => setSynthSuccess(false), 3000);
        if (res.audio_url) {
          const audio = new Audio(res.audio_url);
          audio.play().catch(() => {});
        }
      } else {
        setErrorMessage(res?.message || 'Không thể tạo giọng đọc');
      }
    } catch (err: any) {
      setErrorMessage(err?.message || 'Lỗi kết nối khi tạo TTS');
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handleSave = () => {
    onSave({
      start: Number(start),
      end: Number(end),
      speed: Number(speed),
      voice: voice || undefined,
      user_edited_voice: Boolean(voice),
      text: viText.trim(),
    });
    handleClose();
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 select-none transition-opacity duration-160 ${
        isClosing ? 'opacity-0' : 'opacity-100'
      }`}
      onClick={handleClose}
    >
      <div 
        className={`${isClosing ? 'modal-pop-exit' : 'modal-pop'} w-full max-w-xl bg-[#1A1A1E] border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-white/[0.08] flex items-center justify-between bg-[#222227]">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-cyan-300">
              Chỉnh sửa câu thoại #{cue.id}
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-black/40 text-zinc-400">
              Độ dài: {duration.toFixed(2)}s
            </span>
          </div>
          <button
            onClick={handleClose}
            className="w-6 h-6 rounded flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Body Form */}
        <div className="p-5 space-y-4 text-xs overflow-y-auto max-h-[75vh]">
          {/* 1. Time Range & Speed & Voice Row */}
          <div className="grid grid-cols-4 gap-2.5 p-3 rounded-xl bg-[#141416] border border-white/[0.04]">
            <div>
              <label className="block text-[10px] font-medium text-zinc-400 mb-1">
                Bắt đầu (s)
              </label>
              <input
                type="number"
                step="0.05"
                min="0"
                value={start}
                onChange={(e) => setStart(Number(e.target.value))}
                className="w-full bg-[#202025] border border-white/10 rounded px-2 py-1 text-zinc-200 font-mono focus:outline-none focus:border-cyan-400"
              />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-zinc-400 mb-1">
                Kết thúc (s)
              </label>
              <input
                type="number"
                step="0.05"
                min="0"
                value={end}
                onChange={(e) => setEnd(Number(e.target.value))}
                className="w-full bg-[#202025] border border-white/10 rounded px-2 py-1 text-zinc-200 font-mono focus:outline-none focus:border-cyan-400"
              />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-zinc-400 mb-1">
                Tốc độ ({speed}x)
              </label>
              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.05"
                value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
                className="w-full accent-cyan-400 cursor-pointer mt-1"
              />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-zinc-400 mb-1">
                Giọng đọc câu này
              </label>
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="w-full bg-[#202025] border border-white/10 rounded px-1.5 py-1 text-zinc-200 text-[11px] focus:outline-none focus:border-cyan-400 truncate"
              >
                <option value="">(Mặc định)</option>
                <optgroup label="Giọng Nam">
                  {DEFAULT_MALE_VOICES.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </optgroup>
                <optgroup label="Giọng Nữ">
                  {DEFAULT_FEMALE_VOICES.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </optgroup>
              </select>
            </div>
          </div>

          {/* 2. Chinese Source (Readonly + Quick Copy) */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-zinc-400">
                Nguồn tiếng Trung (Gốc)
              </span>
              <button
                type="button"
                onClick={handleCopyZh}
                className="px-2.5 py-1 rounded bg-[#25252B] hover:bg-[#2F2F36] text-zinc-200 text-[11px] font-medium flex items-center gap-1.5 transition-colors border border-white/[0.06]"
              >
                {copiedZh ? (
                  <>
                    <IconCheck size={12} className="text-emerald-400" />
                    <span className="text-emerald-300">Đã sao chép!</span>
                  </>
                ) : (
                  <span>Sao chép</span>
                )}
              </button>
            </div>
            <div className="p-3 rounded-lg bg-[#141416] border border-white/[0.04] text-zinc-300 font-medium select-text leading-relaxed">
              {zhText || <span className="text-zinc-600 italic">Không có văn bản tiếng Trung</span>}
            </div>
          </div>

          {/* 3. Vietnamese Translation (Editable) */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-zinc-300">
                Bản dịch tiếng Việt (Nhấn Enter để tách dòng nhịp câu)
              </span>
              <button
                type="button"
                onClick={handleAutoBreak}
                className="px-2 py-0.5 rounded bg-[#25252B] hover:bg-[#2F2F36] text-zinc-300 text-[11px] flex items-center gap-1 border border-white/[0.04]"
                title="Tự động ngắt câu thành các dòng ~6 từ"
              >
                <IconScissors size={12} />
                <span>Tự động ngắt dòng</span>
              </button>
            </div>
            <textarea
              rows={4}
              value={viText}
              onChange={(e) => setViText(e.target.value)}
              spellCheck={false}
              autoCorrect="off"
              autoCapitalize="off"
              data-gramm="false"
              data-gramm_editor="false"
              data-enable-grammarly="false"
              className="w-full bg-[#141416] border border-white/10 rounded-lg p-3 text-zinc-100 font-medium leading-relaxed focus:outline-none focus:border-cyan-400 resize-none"
              placeholder="Nhập nội dung phụ đề tiếng Việt..."
            />
          </div>

          {/* Messages */}
          {synthSuccess && (
            <div className="p-2 rounded bg-emerald-950/60 border border-emerald-800/40 text-emerald-300 text-xs flex items-center gap-2">
              <IconCheck size={13} />
              <span>Đã tái tạo giọng đọc TTS và cập nhật bè âm thanh thành công!</span>
            </div>
          )}
          {errorMessage && (
            <div className="p-2 rounded bg-red-950/60 border border-red-800/40 text-red-300 text-xs">
              {errorMessage}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-3 border-t border-white/[0.08] bg-[#1F1F24] flex items-center justify-between">
          <div className="flex items-center gap-2">
            {onPlaySnippet && (
              <button
                type="button"
                onClick={() => onPlaySnippet(start, end)}
                className="px-3 py-1.5 rounded-lg bg-[#292930] hover:bg-[#34343D] text-zinc-200 text-xs font-medium flex items-center gap-1.5 transition-colors border border-white/[0.06]"
              >
                <IconPlay size={12} />
                <span>Nghe thử câu này</span>
              </button>
            )}

            <button
              type="button"
              disabled={isSynthesizing}
              onClick={handleSynthesizeTTS}
              className="px-3 py-1.5 rounded-lg bg-[#292930] hover:bg-[#34343D] text-cyan-300 text-xs font-medium flex items-center gap-1.5 transition-colors border border-cyan-500/20 disabled:opacity-50"
            >
              <span>{isSynthesizing ? 'Đang tạo TTS...' : 'Tạo lại giọng đọc'}</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleClose}
              className="px-3.5 py-1.5 rounded-lg bg-[#26262C] hover:bg-[#303038] text-zinc-300 text-xs font-medium transition-colors border border-white/[0.06]"
            >
              Hủy
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="px-4 py-1.5 rounded-lg bg-white hover:bg-zinc-200 text-zinc-950 text-xs font-semibold shadow-md transition-all active:scale-95"
            >
              Lưu thay đổi
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};