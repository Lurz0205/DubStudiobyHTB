import React, { useState } from 'react';
import { IconClose, IconCheck } from '../icons/StudioIcons';
import { bridge } from '../../api/bridge';

interface ManualTranslateModalProps {
  isOpen: boolean;
  jobId: string;
  promptText: string;
  totalItems?: number;
  onClose: () => void;
  onSubmitSuccess?: () => void;
}

export const ManualTranslateModal: React.FC<ManualTranslateModalProps> = ({
  isOpen,
  jobId,
  promptText,
  totalItems = 0,
  onClose,
  onSubmitSuccess,
}) => {
  const [copied, setCopied] = useState(false);
  const [translatedText, setTranslatedText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleCopyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(promptText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Fallback
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const handleOpenAi = (url: string) => {
    window.open(url, '_blank');
  };

  const handleSubmit = async () => {
    if (!translatedText.trim()) {
      setErrorMsg('Vui lòng dán nội dung kết quả dịch trước khi tiếp tục.');
      return;
    }
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await bridge.submitManualTranslation(jobId, translatedText.trim(), false);
      if (res && res.status === 'success') {
        onSubmitSuccess?.();
        onClose();
      } else {
        setErrorMsg(res?.message || 'Không thể gửi kết quả dịch.');
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Lỗi khi gửi kết quả dịch.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = async () => {
    try {
      await bridge.submitManualTranslation(jobId, '', true);
    } catch {
      // ignore
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 select-none animate-fadeIn">
      <div className="w-full max-w-2xl bg-[#161619] border border-white/10 rounded-xl shadow-2xl flex flex-col overflow-hidden max-h-[92vh]">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-white/[0.06] flex items-center justify-between shrink-0 bg-[#1A1A1E]">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <h3 className="text-sm font-semibold text-zinc-100">
              Dịch thủ công qua AI (ChatGPT / Claude / Gemini)
            </h3>
          </div>
          <button
            onClick={handleCancel}
            className="w-7 h-7 rounded hover:bg-white/[0.08] text-zinc-400 hover:text-white flex items-center justify-center transition-colors"
          >
            <IconClose size={14} />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 overflow-y-auto text-xs text-zinc-300">
          {/* Quick AI Links */}
          <div className="flex items-center justify-between p-3 rounded-lg bg-[#141416] border border-white/[0.04]">
            <span className="text-zinc-400">Mở nhanh công cụ AI:</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleOpenAi('https://chatgpt.com')}
                className="px-2.5 py-1 rounded bg-[#222226] hover:bg-[#2C2C32] text-zinc-200 border border-white/[0.06] transition-colors"
              >
                ChatGPT
              </button>
              <button
                onClick={() => handleOpenAi('https://claude.ai')}
                className="px-2.5 py-1 rounded bg-[#222226] hover:bg-[#2C2C32] text-zinc-200 border border-white/[0.06] transition-colors"
              >
                Claude
              </button>
              <button
                onClick={() => handleOpenAi('https://gemini.google.com')}
                className="px-2.5 py-1 rounded bg-[#222226] hover:bg-[#2C2C32] text-zinc-200 border border-white/[0.06] transition-colors"
              >
                Gemini Web
              </button>
            </div>
          </div>

          {/* Step 1: Copy Prompt */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="font-semibold text-zinc-200 flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-[11px] font-bold">1</span>
                <span>Sao chép Prompt tiếng Trung {totalItems > 0 ? `(${totalItems} câu)` : ''}</span>
              </label>
              <button
                onClick={handleCopyPrompt}
                className="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-medium flex items-center gap-1.5 transition-colors shadow-sm"
              >
                {copied ? <IconCheck size={12} className="text-white" /> : null}
                <span>{copied ? 'Đã sao chép vào Clipboard!' : 'Sao chép Prompt'}</span>
              </button>
            </div>
            <textarea
              readOnly
              value={promptText}
              rows={5}
              className="w-full bg-[#141416] border border-white/[0.08] rounded-lg p-2.5 text-zinc-400 font-mono text-[11px] select-all resize-none focus:outline-none"
            />
          </div>

          {/* Step 2: Paste Result */}
          <div className="space-y-1.5">
            <label className="font-semibold text-zinc-200 flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-[11px] font-bold">2</span>
              <span>Dán kết quả dịch tiếng Việt vào đây</span>
            </label>
            <textarea
              value={translatedText}
              onChange={(e) => setTranslatedText(e.target.value)}
              placeholder="Dán toàn bộ câu trả lời từ AI vào đây (định dạng [1] Câu dịch 1, [2] Câu dịch 2...)"
              rows={8}
              className="w-full bg-[#141416] border border-white/10 rounded-lg p-3 text-zinc-100 placeholder-zinc-500 text-xs focus:outline-none focus:border-cyan-400 resize-none font-sans leading-relaxed"
            />
          </div>

          {errorMsg && (
            <div className="p-2.5 rounded bg-red-950/40 border border-red-500/30 text-red-400 text-xs">
              {errorMsg}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-white/[0.06] flex items-center justify-end gap-2.5 bg-[#1A1A1E] shrink-0">
          <button
            onClick={handleCancel}
            disabled={isSubmitting}
            className="px-4 py-1.5 rounded-lg border border-white/10 text-zinc-300 hover:bg-white/[0.08] transition-colors text-xs font-medium"
          >
            Hủy bỏ
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || !translatedText.trim()}
            className="px-4 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-medium transition-colors text-xs flex items-center gap-2 shadow-sm"
          >
            {isSubmitting ? 'Đang xử lý kết quả...' : 'Xác nhận & Tiếp tục'}
          </button>
        </div>
      </div>
    </div>
  );
};
