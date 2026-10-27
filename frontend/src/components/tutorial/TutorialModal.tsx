import React, { useState, useEffect } from 'react';
import { 
  IconInfo, IconClose, IconCheck, 
  IconDownload 
} from '../icons/StudioIcons';
import { bridge } from '../../api/bridge';

interface TutorialModalProps {
  isOpen: boolean;
  onClose: () => void;
  isFirstRun?: boolean;
}

export const TutorialModal: React.FC<TutorialModalProps> = ({ 
  isOpen, 
  onClose,
  isFirstRun = false,
}) => {
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [selectedAsr, setSelectedAsr] = useState<'sensevoice-small' | 'whisper_large_v3'>('sensevoice-small');
  const [selectedProvider, setSelectedProvider] = useState<'gemini_web' | 'manual'>('gemini_web');
  const [dontShowAgain, setDontShowAgain] = useState<boolean>(true);

  // Components status for Speech-to-text models
  const [components, setComponents] = useState<any[]>([]);
  const [downloadingPkg, setDownloadingPkg] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<{ pct: number; mb: number; totalMb: number }>({ pct: 0, mb: 0, totalMb: 0 });
  const [isClosing, setIsClosing] = useState(false);

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(() => {
      setIsClosing(false);
      onClose();
    }, 160);
  };

  useEffect(() => {
    if (!isOpen) return;
    setCurrentStep(0);

    // Load components status
    bridge.getComponentsStatus().then((pkgs) => {
      if (pkgs) setComponents(pkgs);
    });

    // Listen to download progress
    const unsub = bridge.onPipelineEvent((ev: any) => {
      if (ev.type === 'component_download_progress') {
        setDownloadingPkg(ev.pkg_id);
        setDownloadProgress({
          pct: ev.percent || 0,
          mb: ev.downloaded_mb || 0,
          totalMb: ev.total_mb || 0,
        });
      } else if (ev.type === 'component_download_done') {
        setDownloadingPkg(null);
        bridge.getComponentsStatus().then((pkgs) => {
          if (pkgs) setComponents(pkgs);
        });
      }
    });

    return unsub;
  }, [isOpen]);

  if (!isOpen) return null;

  const handleDownloadModel = async (pkgId: string) => {
    setDownloadingPkg(pkgId);
    setDownloadProgress({ pct: 0, mb: 0, totalMb: 0 });
    await bridge.downloadComponent(pkgId);
  };

  const handleFinish = async () => {
    try {
      await bridge.saveAppSettings({
        whisper_model: selectedAsr,
        translation_provider: selectedProvider,
      });
      if (dontShowAgain) {
        await bridge.markFirstRunDone(true);
      }
    } catch (err) {
      console.error('Failed to save first-run settings', err);
    } finally {
      handleClose();
    }
  };

  const sensevoicePkg = components.find((c) => c.id === 'sensevoice_small');
  const whisperPkg = components.find((c) => c.id === 'whisper_large_v3');

  const stepsList = [
    '1. Giới thiệu',
    '2. Chọn Model Speech-to-Text',
    '3. Chọn Cách dịch',
  ];

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm select-none p-4 transition-opacity duration-160 ${
        isClosing ? 'opacity-0' : 'opacity-100'
      }`}
      onClick={handleClose}
    >
      <div 
        className={`${isClosing ? 'modal-pop-exit' : 'modal-pop'} w-full max-w-2xl bg-[#161619] border border-white/10 rounded-xl shadow-2xl flex flex-col overflow-hidden max-h-[92vh]`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-white/[0.06] flex items-center justify-between shrink-0 bg-[#1A1A1E]">
          <div className="flex items-center gap-2">
            <IconInfo size={16} className="text-zinc-300" />
            <div>
              <h3 className="text-sm font-semibold text-zinc-100">
                {isFirstRun ? 'Chào mừng bạn đến với DubStudio — Thiết lập ban đầu' : 'Hướng dẫn Sử dụng DubStudio'}
              </h3>
              <p className="text-[10px] text-zinc-500">
                Bước {currentStep + 1} / {stepsList.length}: {stepsList[currentStep]}
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="w-7 h-7 rounded hover:bg-white/[0.08] text-zinc-400 hover:text-white flex items-center justify-center transition-colors"
          >
            <IconClose size={12} />
          </button>
        </div>

        {/* Step Tabs Navigation */}
        <div className="flex items-center gap-1 px-5 pt-2 border-b border-white/[0.06] shrink-0 text-xs bg-[#131315]">
          {stepsList.map((label, idx) => (
            <button
              key={label}
              onClick={() => setCurrentStep(idx)}
              className={`px-3 py-2 border-b-2 font-medium transition-all ${
                currentStep === idx
                  ? 'border-white text-white font-semibold'
                  : 'border-transparent text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-4 text-xs text-zinc-300 flex-1 leading-relaxed">
          {/* STEP 0: Overview */}
          {currentStep === 0 && (
            <div className="space-y-3.5">
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-zinc-100">
                  Quy trình lồng tiếng tự động 1-Click
                </h4>
                <p className="text-zinc-400 text-xs leading-relaxed">
                  DubStudio được thiết kế chuyên biệt để tự động hóa trọn gói quá trình dịch thuật và thuyết minh video tiếng Trung sang tiếng Việt với chất lượng giọng đọc tự nhiên và thời gian đồng bộ chuẩn xác:
                </p>
              </div>

              <div className="space-y-2">
                <div className="p-3 rounded-lg bg-[#1B1B1F] border border-white/[0.04] space-y-1">
                  <div className="font-semibold text-zinc-100 flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-white text-black font-bold flex items-center justify-center text-[10px]">1</span>
                    <span>Nhận diện giọng nói (Speech-to-Text / ASR)</span>
                  </div>
                  <p className="text-zinc-400 pl-7 text-[11px]">
                    Tự động bóc băng, nghe và phân đoạn từng câu nói tiếng Trung bằng mô hình AI chuyên dụng chạy trực tiếp trên máy.
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-[#1B1B1F] border border-white/[0.04] space-y-1">
                  <div className="font-semibold text-zinc-100 flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-white text-black font-bold flex items-center justify-center text-[10px]">2</span>
                    <span>Dịch thuật ngữ cảnh (Gemini Web hoặc Tự dịch ngoài)</span>
                  </div>
                  <p className="text-zinc-400 pl-7 text-[11px]">
                    Chuyển ngữ sang câu văn thuần Việt đời thường, tự nhiên, chuẩn văn phong và khớp tốc độ nói của nhân vật.
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-[#1B1B1F] border border-white/[0.04] space-y-1">
                  <div className="font-semibold text-zinc-100 flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-white text-black font-bold flex items-center justify-center text-[10px]">3</span>
                    <span>Tạo giọng thuyết minh AI (VieNeu-TTS v3 Offline)</span>
                  </div>
                  <p className="text-zinc-400 pl-7 text-[11px]">
                    Bộ 25 giọng đọc Nam/Nữ truyền cảm, ấm áp, tổng hợp 100% offline trên máy tính mà không phụ thuộc Internet.
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-[#1B1B1F] border border-white/[0.04] space-y-1">
                  <div className="font-semibold text-zinc-100 flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-white text-black font-bold flex items-center justify-center text-[10px]">4</span>
                    <span>Hòa âm 4 kênh & Xuất video (WYSIWYG 100%)</span>
                  </div>
                  <p className="text-zinc-400 pl-7 text-[11px]">
                    Cân bằng âm lượng giọng đọc, nhạc nền BGM, tăng cường âm thanh +20dB và khắc phụ đề chuẩn xác pixel-perfect.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* STEP 1: Choose Speech to Text Model */}
          {currentStep === 1 && (
            <div className="space-y-4">
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-zinc-100">
                  Lựa chọn Mô hình Nhận dạng Giọng nói (Speech-to-Text)
                </h4>
                <p className="text-zinc-400 text-xs">
                  Mô hình nhận dạng quyết định độ chính xác khi bóc tách câu thoại từ video gốc. Hãy chọn mô hình phù hợp với cấu hình máy tính của bạn:
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {/* Model 1: SenseVoice-Small */}
                <div
                  onClick={() => setSelectedAsr('sensevoice-small')}
                  className={`p-3.5 rounded-lg border transition-all cursor-pointer flex flex-col justify-between ${
                    selectedAsr === 'sensevoice-small'
                      ? 'bg-[#1C1C20] border-white/20 ring-1 ring-white/10'
                      : 'bg-[#161619] border-white/[0.04] hover:bg-[#1A1A1E]'
                  }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-zinc-100 text-xs">SenseVoice-Small</span>
                      <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-medium">
                        Khuyên dùng
                      </span>
                    </div>

                    <p className="text-[11px] text-zinc-400 leading-relaxed">
                      <b>Dung lượng:</b> ~943 MB<br />
                      <b>Tốc độ:</b> Siêu nhanh, chiếm rất ít VRAM và RAM.<br />
                      <b>Đặc điểm:</b> Nhận dạng tiếng Trung tự nhiên, phân đoạn chuẩn và chạy mượt mà ngay cả trên laptop văn phòng.
                    </p>
                  </div>

                  <div className="pt-3 mt-2 border-t border-white/[0.06] flex items-center justify-between">
                    <span className="text-[10px] text-zinc-500">
                      {sensevoicePkg?.ready ? '✓ Đã sẵn sàng' : 'Chưa tải về'}
                    </span>
                    {!sensevoicePkg?.ready && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadModel('sensevoice_small');
                        }}
                        disabled={downloadingPkg === 'sensevoice_small'}
                        className="px-2.5 py-1 rounded bg-white text-black font-semibold text-[11px] flex items-center gap-1 hover:bg-zinc-200 transition-colors disabled:opacity-50"
                      >
                        <IconDownload size={11} />
                        <span>{downloadingPkg === 'sensevoice_small' ? 'Đang tải...' : 'Tải về'}</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Model 2: faster-whisper large-v3 */}
                <div
                  onClick={() => setSelectedAsr('whisper_large_v3')}
                  className={`p-3.5 rounded-lg border transition-all cursor-pointer flex flex-col justify-between ${
                    selectedAsr === 'whisper_large_v3'
                      ? 'bg-[#1C1C20] border-white/20 ring-1 ring-white/10'
                      : 'bg-[#161619] border-white/[0.04] hover:bg-[#1A1A1E]'
                  }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-zinc-100 text-xs">faster-whisper large-v3</span>
                      <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[10px] font-medium">
                        Chuẩn xác cao
                      </span>
                    </div>

                    <p className="text-[11px] text-zinc-400 leading-relaxed">
                      <b>Dung lượng:</b> ~3.09 GB<br />
                      <b>Tốc độ:</b> Yêu cầu GPU rời NVIDIA RTX hoặc CPU mạnh.<br />
                      <b>Đặc điểm:</b> Bóc băng chuẩn từng chi tiết nhỏ đối với video có nhiều tạp âm hoặc giọng địa phương khó nghe.
                    </p>
                  </div>

                  <div className="pt-3 mt-2 border-t border-white/[0.06] flex items-center justify-between">
                    <span className="text-[10px] text-zinc-500">
                      {whisperPkg?.ready ? '✓ Đã sẵn sàng' : 'Chưa tải về'}
                    </span>
                    {!whisperPkg?.ready && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadModel('whisper_large_v3');
                        }}
                        disabled={downloadingPkg === 'whisper_large_v3'}
                        className="px-2.5 py-1 rounded bg-[#2A2A30] text-zinc-200 font-semibold text-[11px] flex items-center gap-1 hover:bg-[#35353C] transition-colors disabled:opacity-50"
                      >
                        <IconDownload size={11} />
                        <span>{downloadingPkg === 'whisper_large_v3' ? 'Đang tải...' : 'Tải về'}</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Download Progress Bar if downloading */}
              {downloadingPkg && (
                <div className="p-3 rounded-lg bg-[#141416] border border-white/[0.06] space-y-1.5">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-zinc-300 font-medium">
                      Đang tải {downloadingPkg === 'sensevoice_small' ? 'SenseVoice-Small' : 'faster-whisper large-v3'}...
                    </span>
                    <span className="text-cyan-400">
                      {downloadProgress.mb} / {downloadProgress.totalMb} MB ({downloadProgress.pct}%)
                    </span>
                  </div>
                  <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                    <div 
                      className="bg-cyan-400 h-full transition-all duration-300"
                      style={{ width: `${downloadProgress.pct}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 2: Choose Translation Provider */}
          {currentStep === 2 && (
            <div className="space-y-4">
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-zinc-100">
                  Lựa chọn Phương thức Dịch thuật AI (Không cần API Key)
                </h4>
                <p className="text-zinc-400 text-xs">
                  DubStudio hỗ trợ hai phương thức dịch hoàn toàn miễn phí, bạn có thể chuyển đổi bất cứ lúc nào trong mục Cài đặt:
                </p>
              </div>

              <div className="space-y-3">
                {/* Option A: Gemini Web */}
                <div
                  onClick={() => setSelectedProvider('gemini_web')}
                  className={`p-3.5 rounded-lg border transition-all cursor-pointer space-y-2 ${
                    selectedProvider === 'gemini_web'
                      ? 'bg-[#1C1C20] border-white/20 ring-1 ring-white/10'
                      : 'bg-[#161619] border-white/[0.04] hover:bg-[#1A1A1E]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <input
                        type="radio"
                        checked={selectedProvider === 'gemini_web'}
                        onChange={() => setSelectedProvider('gemini_web')}
                        className="accent-white cursor-pointer"
                      />
                      <span className="font-semibold text-zinc-100 text-xs">
                        Gemini Web Tự động (Trình duyệt độc lập trong nền)
                      </span>
                    </div>
                    <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-medium">
                      Tiện lợi nhất
                    </span>
                  </div>

                  <p className="text-[11px] text-zinc-400 pl-5 leading-relaxed">
                    • Ứng dụng tự động điều khiển một cửa sổ trình duyệt Edge/Chrome nhỏ gọn trong nền để gửi prompt và nhận kết quả dịch tự động.<br />
                    • Miễn phí 100%, không giới hạn lượt dùng và <b>không cần nhập bất kỳ mã API Key nào</b>.
                  </p>
                </div>

                {/* Option B: Manual External AI */}
                <div
                  onClick={() => setSelectedProvider('manual')}
                  className={`p-3.5 rounded-lg border transition-all cursor-pointer space-y-2 ${
                    selectedProvider === 'manual'
                      ? 'bg-[#1C1C20] border-white/20 ring-1 ring-white/10'
                      : 'bg-[#161619] border-white/[0.04] hover:bg-[#1A1A1E]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <input
                        type="radio"
                        checked={selectedProvider === 'manual'}
                        onChange={() => setSelectedProvider('manual')}
                        className="accent-white cursor-pointer"
                      />
                      <span className="font-semibold text-zinc-100 text-xs">
                        Tự dịch thủ công (ChatGPT / Claude / Gemini ngoài)
                      </span>
                    </div>
                  </div>

                  <p className="text-[11px] text-zinc-400 pl-5 leading-relaxed">
                    • Khi bấm <b>Tạo phụ đề</b>, ứng dụng hiển thị hộp thoại chứa sẵn Prompt tiếng Trung và các nút 1-click để mở nhanh ChatGPT / Claude / Gemini Web ngoài.<br />
                    • Bạn chỉ cần copy prompt sang AI dịch, sau đó dán kết quả trở lại ứng dụng để tiếp tục tạo giọng đọc thuyết minh.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Navigation */}
        <div className="px-5 py-3.5 border-t border-white/[0.06] bg-[#141416] flex items-center justify-between shrink-0">
          <div>
            {isFirstRun && (
              <label className="flex items-center gap-2 cursor-pointer text-[11px] text-zinc-400 hover:text-zinc-300">
                <input
                  type="checkbox"
                  checked={dontShowAgain}
                  onChange={(e) => setDontShowAgain(e.target.checked)}
                  className="rounded bg-[#222227] border-white/10 accent-white cursor-pointer"
                />
                <span>Không tự động hiện lại khi mở ứng dụng</span>
              </label>
            )}
          </div>

          <div className="flex items-center gap-2">
            {currentStep > 0 && (
              <button
                type="button"
                onClick={() => setCurrentStep((prev) => prev - 1)}
                className="px-3 py-1.5 rounded-md bg-[#222227] hover:bg-[#2A2A30] text-zinc-300 text-xs font-medium border border-white/[0.06] transition-colors"
              >
                Quay lại
              </button>
            )}

            {currentStep < stepsList.length - 1 ? (
              <button
                type="button"
                onClick={() => setCurrentStep((prev) => prev + 1)}
                className="px-4 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors shadow-sm"
              >
                Tiếp tục
              </button>
            ) : (
              <button
                type="button"
                onClick={handleFinish}
                className="px-4 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
              >
                <IconCheck size={12} />
                <span>{isFirstRun ? 'Hoàn tất & Bắt đầu sử dụng' : 'Đã hiểu'}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
