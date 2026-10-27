import React, { useState, useEffect } from 'react';
import { 
  IconRefresh, IconCheck, IconClose, 
  IconDownload 
} from '../icons/StudioIcons';
import { bridge } from '../../api/bridge';

interface UpdatesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const UpdatesModal: React.FC<UpdatesModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'components' | 'app'>('components');
  const [checking, setChecking] = useState(false);
  const [updateResult, setUpdateResult] = useState<any>(null);
  const [components, setComponents] = useState<any[]>([]);

  const [downloadingPkg, setDownloadingPkg] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<{ pct: number; mb: number; totalMb: number }>({
    pct: 0,
    mb: 0,
    totalMb: 0,
  });
  const [isClosing, setIsClosing] = useState(false);

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(() => {
      setIsClosing(false);
      onClose();
    }, 160);
  };

  const loadData = async () => {
    try {
      const list = await bridge.getComponentsStatus();
      if (Array.isArray(list)) setComponents(list);
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadData();
      handleCheckUpdates();

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
          loadData();
        }
      });

      return unsub;
    }
  }, [isOpen]);

  const handleCheckUpdates = async () => {
    setChecking(true);
    try {
      const res = await bridge.checkForUpdates();
      setUpdateResult(res);
    } catch {
      setUpdateResult({ error: 'Không thể kết nối đến GitHub để kiểm tra cập nhật.' });
    } finally {
      setChecking(false);
    }
  };

  const handleDownload = async (pkgId: string) => {
    setDownloadingPkg(pkgId);
    setDownloadProgress({ pct: 0, mb: 0, totalMb: 0 });
    try {
      await bridge.downloadComponent(pkgId);
    } catch {
      setDownloadingPkg(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm select-none p-4 transition-opacity duration-160 ${
        isClosing ? 'opacity-0' : 'opacity-100'
      }`}
      onClick={handleClose}
    >
      <div 
        className={`${isClosing ? 'modal-pop-exit' : 'modal-pop'} w-full max-w-2xl bg-[#161619] border border-white/10 rounded-xl shadow-2xl flex flex-col overflow-hidden max-h-[90vh]`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-white/[0.06] flex items-center justify-between shrink-0 bg-[#1A1A1E]">
          <div className="flex items-center gap-2">
            <IconRefresh size={16} className="text-zinc-300" />
            <h3 className="text-sm font-semibold text-zinc-100">Quản lý Gói Model AI & Cập nhật</h3>
          </div>
          <button
            onClick={handleClose}
            className="w-7 h-7 rounded hover:bg-white/[0.08] text-zinc-400 hover:text-white flex items-center justify-center transition-colors"
          >
            <IconClose size={12} />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-1 px-5 pt-2 border-b border-white/[0.06] shrink-0 text-xs bg-[#131315]">
          <button
            onClick={() => setActiveTab('components')}
            className={`px-3.5 py-2 border-b-2 font-medium transition-all ${
              activeTab === 'components'
                ? 'border-white text-white font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Mô hình & Thư viện AI ({components.length})
          </button>
          <button
            onClick={() => setActiveTab('app')}
            className={`px-3.5 py-2 border-b-2 font-medium transition-all ${
              activeTab === 'app'
                ? 'border-white text-white font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Cập nhật Phần mềm (GitHub)
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-4 text-xs text-zinc-300 flex-1 leading-relaxed">
          {activeTab === 'components' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-zinc-200 text-xs">Danh sách Mô hình & Thành phần AI Cục bộ</h4>
                  <p className="text-[11px] text-zinc-500">Các gói được lưu an toàn tại thư mục dữ liệu ứng dụng.</p>
                </div>
                <button
                  onClick={loadData}
                  className="px-2.5 py-1 rounded bg-[#222227] hover:bg-[#2A2A30] text-zinc-300 text-[11px] font-medium border border-white/[0.06] flex items-center gap-1 transition-colors"
                >
                  <IconRefresh size={11} />
                  <span>Làm mới</span>
                </button>
              </div>

              {components.length === 0 ? (
                <div className="p-6 text-center text-zinc-500 text-xs">Đang kiểm tra các gói trên ổ đĩa...</div>
              ) : (
                <div className="space-y-2.5">
                  {components.map((comp) => {
                    const isDownloadingThis = downloadingPkg === comp.id;

                    return (
                      <div
                        key={comp.id}
                        className="p-3.5 rounded-lg bg-[#19191D] border border-white/[0.04] space-y-2 hover:border-white/[0.08] transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <div className="space-y-0.5">
                            <div className="font-semibold text-zinc-100 text-xs flex items-center gap-2">
                              <span>{comp.name}</span>
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-400">
                                ~{comp.size_mb} MB
                              </span>
                            </div>
                            {comp.description && (
                              <p className="text-[11px] text-zinc-400 font-light">{comp.description}</p>
                            )}
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            <span className={`text-[10px] px-2.5 py-0.5 rounded font-medium ${
                              comp.ready
                                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                            }`}>
                              {comp.ready ? '✓ Đã sẵn sàng' : 'Chưa tải'}
                            </span>

                            <button
                              onClick={() => handleDownload(comp.id)}
                              disabled={isDownloadingThis}
                              className={`px-2.5 py-1 rounded text-[11px] font-semibold flex items-center gap-1 transition-all ${
                                comp.ready
                                  ? 'bg-[#222227] hover:bg-[#2A2A30] text-zinc-300 border border-white/[0.06]'
                                  : 'bg-white hover:bg-zinc-200 text-black shadow-sm'
                              } disabled:opacity-50`}
                            >
                              <IconDownload size={11} />
                              <span>{isDownloadingThis ? 'Đang tải...' : comp.ready ? 'Tải lại' : 'Tải về'}</span>
                            </button>
                          </div>
                        </div>

                        {/* Progress bar if actively downloading */}
                        {isDownloadingThis && (
                          <div className="pt-1.5 space-y-1">
                            <div className="flex items-center justify-between text-[10px] text-zinc-400">
                              <span>Tiến độ tải về: {downloadProgress.pct}%</span>
                              <span>{downloadProgress.mb} / {downloadProgress.totalMb} MB</span>
                            </div>
                            <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                              <div
                                className="bg-cyan-400 h-full transition-all duration-200"
                                style={{ width: `${downloadProgress.pct}%` }}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {activeTab === 'app' && (
            <div className="space-y-4">
              {/* Current Version Card */}
              <div className="p-4 rounded-lg bg-[#1B1B1F] border border-white/[0.06] flex items-center justify-between">
                <div>
                  <div className="text-zinc-400 text-[11px]">Phiên bản DubStudio đang cài đặt</div>
                  <div className="text-sm font-bold text-white mt-0.5">
                    {updateResult?.current_version || '2.0.0'} (Stable)
                  </div>
                </div>

                <button
                  onClick={handleCheckUpdates}
                  disabled={checking}
                  className="px-3.5 py-1.5 rounded-md bg-[#25252A] hover:bg-[#303037] text-zinc-200 text-xs font-medium border border-white/[0.08] flex items-center gap-1.5 transition-colors disabled:opacity-50"
                >
                  <IconRefresh size={13} className={checking ? 'animate-spin' : ''} />
                  <span>{checking ? 'Đang kiểm tra...' : 'Kiểm tra ngay'}</span>
                </button>
              </div>

              {/* Result Message */}
              {updateResult && (
                <div className={`p-4 rounded-lg border text-xs space-y-2 ${
                  updateResult.has_update
                    ? 'bg-amber-500/10 border-amber-500/30 text-amber-200'
                    : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                }`}>
                  {updateResult.has_update ? (
                    <>
                      <div className="font-semibold flex items-center gap-1.5 text-amber-300">
                        <IconDownload size={14} />
                        <span>Đã phát hiện bản phát hành mới: {updateResult.latest_version}</span>
                      </div>
                      {updateResult.release_notes && (
                        <div className="p-3 bg-black/40 rounded border border-white/[0.06] text-[11px] whitespace-pre-wrap text-zinc-300 max-h-40 overflow-y-auto">
                          {updateResult.release_notes}
                        </div>
                      )}
                      <div className="pt-1">
                        <a
                          href={updateResult.download_url || 'https://github.com/sieutocdo1/dubstudio/releases'}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-block px-3 py-1.5 rounded bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-colors"
                        >
                          Mở trang tải bản cập nhật trên GitHub
                        </a>
                      </div>
                    </>
                  ) : (
                    <div className="flex items-center gap-2">
                      <IconCheck size={14} className="text-emerald-400 shrink-0" />
                      <span>Bạn đang sử dụng phiên bản DubStudio mới nhất ({updateResult.current_version || '2.0.0'}).</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 bg-[#131315] border-t border-white/[0.06] flex items-center justify-end shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors shadow-sm"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
