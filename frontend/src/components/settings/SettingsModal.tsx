import React, { useState, useEffect, useRef } from 'react';
import { 
  IconClose, IconFolder, IconCheck, 
  IconSettings, IconPlay, IconPause
} from '../icons/StudioIcons';
import { bridge } from '../../api/bridge';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [translationProvider, setTranslationProvider] = useState<'gemini_web' | 'manual'>('gemini_web');
  const [translationTone, setTranslationTone] = useState('Tự nhiên, đời thường');
  const [defaultMaleVoice, setDefaultMaleVoice] = useState('Minh Đức');
  const [defaultFemaleVoice, setDefaultFemaleVoice] = useState('Quỳnh Anh');
  const [whisperModel, setWhisperModel] = useState('sensevoice-small');
  const [separationModel, setSeparationModel] = useState('Kim_Vocal_2.onnx');
  const [outDir, setOutDir] = useState('');

  const [maleVoices, setMaleVoices] = useState<string[]>([]);
  const [femaleVoices, setFemaleVoices] = useState<string[]>([]);

  const [browserStatus, setBrowserStatus] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [isClosing, setIsClosing] = useState(false);

  // GPU Hardware Status
  const [gpuInfo, setGpuInfo] = useState<any>(null);

  const [playingVoice, setPlayingVoice] = useState<string | null>(null);
  const audioPreviewRef = useRef<HTMLAudioElement | null>(null);

  const handlePreviewVoice = async (voice: string) => {
    if (playingVoice === voice) {
      if (audioPreviewRef.current) {
        audioPreviewRef.current.pause();
        audioPreviewRef.current = null;
      }
      setPlayingVoice(null);
      return;
    }

    if (audioPreviewRef.current) {
      audioPreviewRef.current.pause();
      audioPreviewRef.current = null;
    }

    setPlayingVoice(voice);
    try {
      const res = await bridge.previewVoice(voice);
      if (res && res.status === 'success' && res.audio_url) {
        const audio = new Audio(res.audio_url);
        audioPreviewRef.current = audio;
        audio.onended = () => {
          setPlayingVoice(null);
          audioPreviewRef.current = null;
        };
        audio.onerror = () => {
          setPlayingVoice(null);
          audioPreviewRef.current = null;
        };
        await audio.play();
      } else {
        setPlayingVoice(null);
        alert(res?.message || 'Không thể tạo bản nghe thử');
      }
    } catch {
      setPlayingVoice(null);
    }
  };

  const handleClose = () => {
    if (audioPreviewRef.current) {
      audioPreviewRef.current.pause();
      audioPreviewRef.current = null;
    }
    setPlayingVoice(null);
    setIsClosing(true);
    setTimeout(() => {
      setIsClosing(false);
      onClose();
    }, 160);
  };

  useEffect(() => {
    return () => {
      if (audioPreviewRef.current) {
        audioPreviewRef.current.pause();
        audioPreviewRef.current = null;
      }
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    setIsClosing(false);
    setSaveStatus('idle');
    setBrowserStatus(null);

    bridge.getGpuInfo().then((info) => {
      if (info) setGpuInfo(info);
    }).catch(() => {});

    bridge.getAppSettings().then((s) => {
      if (s) {
        if (s.translation_provider) setTranslationProvider(s.translation_provider);
        if (s.translation_tone) setTranslationTone(s.translation_tone);
        if (s.default_male_voice) setDefaultMaleVoice(s.default_male_voice);
        if (s.default_female_voice) setDefaultFemaleVoice(s.default_female_voice);
        if (s.whisper_model) setWhisperModel(s.whisper_model);
        if (s.separation_model) setSeparationModel(s.separation_model);
        if (s.out_dir) setOutDir(s.out_dir);

        if (s.male_voices && s.male_voices.length > 0) setMaleVoices(s.male_voices);
        if (s.female_voices && s.female_voices.length > 0) setFemaleVoices(s.female_voices);
      }
    });
  }, [isOpen]);

  if (!isOpen) return null;

  const handleLaunchBrowser = async () => {
    setBrowserStatus('Đang mở trình duyệt...');
    try {
      const res = await bridge.launchGeminiBrowser();
      setBrowserStatus(res?.message || 'Đã mở trình duyệt Gemini Web');
      setTimeout(() => setBrowserStatus(null), 5000);
    } catch {
      setBrowserStatus('Không thể mở trình duyệt');
      setTimeout(() => setBrowserStatus(null), 4000);
    }
  };

  const handleBrowseOutDir = async () => {
    const dir = await bridge.openFolderDialog(outDir);
    if (dir) setOutDir(dir);
  };

  const handleSave = async () => {
    setSaveStatus('saving');
    try {
      await bridge.saveAppSettings({
        translation_provider: translationProvider,
        translation_tone: translationTone,
        default_male_voice: defaultMaleVoice,
        default_female_voice: defaultFemaleVoice,
        whisper_model: whisperModel,
        separation_model: separationModel,
        out_dir: outDir,
      });
      setSaveStatus('saved');
    } catch {
      setSaveStatus('saved');
    } finally {
      setTimeout(() => {
        handleClose();
      }, 300);
    }
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm select-none p-4 transition-opacity duration-160 ${
        isClosing ? 'opacity-0' : 'opacity-100'
      }`}
      onClick={handleClose}
    >
      <div 
        className={`${isClosing ? 'modal-pop-exit' : 'modal-pop'} w-full max-w-xl bg-[#161619] border border-white/10 rounded-xl shadow-2xl flex flex-col overflow-hidden max-h-[90vh]`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-white/[0.06] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <IconSettings size={16} className="text-zinc-300" />
            <h3 className="text-sm font-semibold text-zinc-100">Cài đặt Hệ thống</h3>
          </div>
          <button
            onClick={handleClose}
            className="w-7 h-7 rounded hover:bg-white/[0.08] text-zinc-400 hover:text-white flex items-center justify-center transition-colors"
          >
            <IconClose size={12} />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-5 text-xs text-zinc-300 flex-1">
          {/* Notification banner on save */}
          {saveStatus === 'saved' && (
            <div className="p-2.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
              <IconCheck size={14} />
              <span>Đã lưu cài đặt hệ thống thành công!</span>
            </div>
          )}

          {/* 1. Phương thức Dịch thuật */}
          <div className="space-y-2.5 pb-4 border-b border-white/[0.06]">
            <label className="block text-xs font-semibold text-zinc-200">
              Phương thức Dịch thuật AI (Không cần API Key)
            </label>

            <div className="grid grid-cols-2 gap-2 bg-[#1A1A1E] p-1 rounded-lg border border-white/[0.06]">
              <button
                type="button"
                onClick={() => setTranslationProvider('gemini_web')}
                className={`py-2 px-3 rounded-md text-xs font-medium transition-all text-left flex flex-col gap-0.5 ${
                  translationProvider === 'gemini_web'
                    ? 'bg-[#25252A] text-white shadow-sm border border-white/10'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <span className="font-semibold text-zinc-100">Gemini Web (Tự động)</span>
                <span className="text-[10px] text-zinc-400">Trình duyệt ngầm, miễn phí 100%</span>
              </button>

              <button
                type="button"
                onClick={() => setTranslationProvider('manual')}
                className={`py-2 px-3 rounded-md text-xs font-medium transition-all text-left flex flex-col gap-0.5 ${
                  translationProvider === 'manual'
                    ? 'bg-[#25252A] text-white shadow-sm border border-white/10'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <span className="font-semibold text-zinc-100">Tự dịch thủ công</span>
                <span className="text-[10px] text-zinc-400">Copy prompt sang ChatGPT / Claude</span>
              </button>
            </div>

            {/* Provider Details Box */}
            {translationProvider === 'gemini_web' ? (
              <div className="p-3 rounded-lg bg-[#141416] border border-white/[0.04] space-y-2">
                <p className="text-[11px] text-zinc-400 leading-relaxed">
                  Ứng dụng tự động điều khiển một cửa sổ trình duyệt Edge/Chrome nhỏ gọn trong nền để dịch thuật tự động qua Gemini Web. Hoàn toàn miễn phí, không giới hạn số lượng câu và không bao giờ yêu cầu nhập mã API Key.
                </p>
                <div className="flex items-center gap-2 pt-1">
                  <button
                    type="button"
                    onClick={handleLaunchBrowser}
                    className="px-3 py-1.5 rounded bg-[#222227] hover:bg-[#2A2A30] text-zinc-200 text-xs font-medium border border-white/[0.08] transition-colors"
                  >
                    Mở trình duyệt Gemini Web
                  </button>
                  {browserStatus && (
                    <span className="text-[11px] text-cyan-300">
                      {browserStatus}
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-3 rounded-lg bg-[#141416] border border-white/[0.04]">
                <p className="text-[11px] text-zinc-400 leading-relaxed">
                  Khi bạn bấm <b>Tạo phụ đề</b> ở Studio, sau khi nhận dạng tiếng Trung xong, ứng dụng sẽ cung cấp prompt để bạn sao chép sang ChatGPT / Claude / Gemini ngoài dịch, rồi dán kết quả trả lại vào app. Phù hợp cho mọi tài khoản AI cá nhân.
                </p>
              </div>
            )}
          </div>

          {/* 2. Giọng thuyết minh mặc định (VieNeu-TTS v3) */}
          <div className="space-y-3 pb-4 border-b border-white/[0.06]">
            <label className="block text-xs font-semibold text-zinc-200">
              Giọng thuyết minh AI mặc định (VieNeu-TTS v3)
            </label>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Giọng Nam */}
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Giọng Nam mặc định:
                </label>
                <div className="flex items-center gap-2">
                  <select
                    value={defaultMaleVoice}
                    onChange={(e) => setDefaultMaleVoice(e.target.value)}
                    className="flex-1 min-w-0 bg-[#1F1F24] border border-white/[0.08] rounded-md px-2.5 py-1.5 text-xs text-zinc-100 focus:outline-none cursor-pointer truncate"
                  >
                    {(maleVoices.length > 0 ? maleVoices : ['Minh Đức', 'Hải Đăng', 'Quốc Tuấn', 'Quang Sơn', 'Thiện Minh', 'Minh Triết', 'Đức Trí', 'Thái Sơn', 'Xuân Vĩnh', 'Thanh Bình', 'Phạm Tuyên', 'Thiền Tâm Đức', 'Adam', 'Adam bựa']).map((v) => (
                      <option key={v} value={v}>
                        {v} (Nam)
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => handlePreviewVoice(defaultMaleVoice)}
                    className="px-2.5 py-1.5 rounded-md bg-[#2A2A30] hover:bg-[#35353D] border border-white/10 text-xs font-medium text-zinc-200 flex items-center gap-1 shrink-0 transition-colors"
                    title="Nghe thử giọng này"
                  >
                    {playingVoice === defaultMaleVoice ? <IconPause size={13} /> : <IconPlay size={13} />}
                    <span>{playingVoice === defaultMaleVoice ? 'Dừng' : 'Nghe thử'}</span>
                  </button>
                </div>
              </div>

              {/* Giọng Nữ */}
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Giọng Nữ mặc định:
                </label>
                <div className="flex items-center gap-2">
                  <select
                    value={defaultFemaleVoice}
                    onChange={(e) => setDefaultFemaleVoice(e.target.value)}
                    className="flex-1 min-w-0 bg-[#1F1F24] border border-white/[0.08] rounded-md px-2.5 py-1.5 text-xs text-zinc-100 focus:outline-none cursor-pointer truncate"
                  >
                    {(femaleVoices.length > 0 ? femaleVoices : ['Quỳnh Anh', 'Mai Anh', 'Trúc Ly', 'Thùy Dung', 'Ngọc Huyền', 'Ngọc Trân', 'Ngọc Linh', 'Đoan Trang', 'Thục Đoan', 'Mỹ Duyên', 'Kim Thanh']).map((v) => (
                      <option key={v} value={v}>
                        {v} (Nữ)
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => handlePreviewVoice(defaultFemaleVoice)}
                    className="px-2.5 py-1.5 rounded-md bg-[#2A2A30] hover:bg-[#35353D] border border-white/10 text-xs font-medium text-zinc-200 flex items-center gap-1 shrink-0 transition-colors"
                    title="Nghe thử giọng này"
                  >
                    {playingVoice === defaultFemaleVoice ? <IconPause size={13} /> : <IconPlay size={13} />}
                    <span>{playingVoice === defaultFemaleVoice ? 'Dừng' : 'Nghe thử'}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* 3. Mô hình Nhận dạng & Tách nhạc */}
          <div className="space-y-3 pb-4 border-b border-white/[0.06]">
            <label className="block text-xs font-semibold text-zinc-200">
              Mô hình Xử lý Âm thanh & Nhận dạng (ASR / UVR)
            </label>

            <div className="grid grid-cols-2 gap-3">
              {/* Mô hình ASR */}
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Nhận dạng tiếng Trung (ASR):
                </label>
                <select
                  value={whisperModel}
                  onChange={(e) => setWhisperModel(e.target.value)}
                  className="w-full bg-[#1F1F24] border border-white/[0.08] rounded-md px-2.5 py-1.5 text-xs text-zinc-100 focus:outline-none cursor-pointer"
                >
                  <option value="sensevoice-small">SenseVoice-Small (~900 MB - Nhanh, nhẹ)</option>
                  <option value="whisper_large_v3">faster-whisper large-v3 (~3.09 GB - Chuẩn xác)</option>
                </select>
              </div>

              {/* Mô hình Tách nhạc */}
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Tách giọng & BGM (UVR):
                </label>
                <select
                  value={separationModel}
                  onChange={(e) => setSeparationModel(e.target.value)}
                  className="w-full bg-[#1F1F24] border border-white/[0.08] rounded-md px-2.5 py-1.5 text-xs text-zinc-100 focus:outline-none cursor-pointer"
                >
                  <option value="Kim_Vocal_2.onnx">Kim Vocal 2 ONNX (~66 MB - Khuyên dùng)</option>
                  <option value="bs_roformer">BS-RoFormer EP 317 (~225 MB - Cao cấp)</option>
                </select>
              </div>
            </div>
          </div>

          {/* 4. Thư mục xuất video */}
          <div className="pb-4 border-b border-white/[0.06]">
            <label className="block text-[11px] font-medium text-zinc-300 mb-1">
              Thư mục lưu video thành phẩm
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={outDir}
                onChange={(e) => setOutDir(e.target.value)}
                placeholder="Mặc định: out/"
                className="flex-1 bg-[#1F1F24] border border-white/[0.08] rounded-md px-3 py-1.5 text-xs text-zinc-100 focus:outline-none"
              />
              <button
                type="button"
                onClick={handleBrowseOutDir}
                className="px-3 py-1.5 rounded-md bg-[#222227] hover:bg-[#2A2A30] text-zinc-200 text-xs font-medium border border-white/[0.08] flex items-center gap-1.5 transition-colors"
              >
                <IconFolder size={13} />
                <span>Chọn</span>
              </button>
            </div>
          </div>

          {/* 5. Trạng thái Phần cứng xử lý (GPU / CPU) */}
          <div className="space-y-2.5">
            <label className="block text-xs font-semibold text-zinc-200">
              Trạng thái Phần cứng & Tăng tốc (GPU / CPU)
            </label>

            <div className="p-3 rounded-lg bg-[#141416] border border-white/[0.04] space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${gpuInfo?.is_cuda_ready ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                  <span className="font-medium text-zinc-200 text-xs">
                    {gpuInfo?.card_name || 'Đang kiểm tra phần cứng...'}
                  </span>
                </div>
                <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                  gpuInfo?.is_cuda_ready
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                }`}>
                  {gpuInfo?.is_cuda_ready ? 'CUDA Sẵn sàng' : 'Chế độ CPU'}
                </span>
              </div>

              {gpuInfo && (
                <div className="grid grid-cols-2 gap-2 text-[11px] text-zinc-400 pt-2 border-t border-white/[0.04]">
                  <div>
                    <span className="text-zinc-500">Bộ nhớ VRAM:</span>{' '}
                    <span className="text-zinc-300 font-mono">{gpuInfo.vram_gb ? `${gpuInfo.vram_gb} GB` : 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Phiên bản Driver:</span>{' '}
                    <span className="text-zinc-300 font-mono">{gpuInfo.driver_version || 'N/A'}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-3 border-t border-white/[0.06] bg-[#141416] flex items-center justify-between shrink-0">
          <span className="text-[11px] text-zinc-500">
            Cấu hình được lưu trực tiếp vào bộ nhớ ứng dụng.
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={handleClose}
              className="px-3 py-1.5 rounded-md text-zinc-400 hover:text-white text-xs font-medium transition-colors"
            >
              Đóng
            </button>
            <button
              onClick={handleSave}
              disabled={saveStatus === 'saving'}
              className="px-4 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm disabled:opacity-50"
            >
              {saveStatus === 'saving' ? (
                <span>Đang lưu...</span>
              ) : (
                <>
                  <IconCheck size={12} />
                  <span>Lưu thay đổi</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
