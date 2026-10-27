import React, { useState, useRef } from 'react';
import { 
  IconScissors, IconPlus, IconTrash, IconPlay, 
  IconPause, IconCheck, IconArrowUp, IconArrowDown,
  IconFolder
} from '../icons/StudioIcons';
import { bridge } from '../../api/bridge';

interface VideoItem {
  path: string;
  name: string;
  size?: number;
  duration?: number;
  resolution?: string;
}

export const ToolsView: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'merge' | 'trim'>('merge');

  // ─── MERGE STATE ───
  const [mergeList, setMergeList] = useState<VideoItem[]>([]);
  const [mergeOutputName, setMergeOutputName] = useState('merged_video.mp4');
  const [forceReencode, setForceReencode] = useState(false);
  const [isMerging, setIsMerging] = useState(false);
  const [mergeStatus, setMergeStatus] = useState<string | null>(null);
  const [mergeResultPath, setMergeResultPath] = useState<string | null>(null);

  // ─── TRIM STATE ───
  const [trimSource, setTrimSource] = useState<VideoItem | null>(null);
  const [trimStart, setTrimStart] = useState<number>(0);
  const [trimEnd, setTrimEnd] = useState<number>(10);
  const [fastCopy, setFastCopy] = useState<boolean>(true);
  const [trimOutputName, setTrimOutputName] = useState('trimmed_video.mp4');
  const [isTrimming, setIsTrimming] = useState(false);
  const [trimStatus, setTrimStatus] = useState<string | null>(null);
  const [trimResultPath, setTrimResultPath] = useState<string | null>(null);

  // Video preview ref
  const videoPreviewRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);

  // Trim timeline dragging refs
  const timelineTrackRef = useRef<HTMLDivElement | null>(null);
  const isDraggingHandleRef = useRef<'start' | 'end' | 'seek' | null>(null);
  const trimStartRef = useRef<number>(trimStart);
  trimStartRef.current = trimStart;
  const trimEndRef = useRef<number>(trimEnd);
  trimEndRef.current = trimEnd;

  // Format helpers
  const formatTime = (secs: number) => {
    const s = Math.max(0, secs);
    const m = Math.floor(s / 60);
    const remS = Math.floor(s % 60);
    const ms = Math.floor((s % 1) * 10);
    return `${m.toString().padStart(2, '0')}:${remS.toString().padStart(2, '0')}.${ms}`;
  };

  const formatSize = (bytes?: number) => {
    if (!bytes) return '';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  // ─── MERGE HANDLERS ───
  const handleAddVideos = async () => {
    try {
      const paths = await bridge.openMultipleVideosDialog();
      if (!paths || paths.length === 0) return;

      const newItems: VideoItem[] = [];
      for (const p of paths) {
        // Skip duplicate paths already in list
        if (mergeList.some((item) => item.path === p)) continue;

        const info = await bridge.probeVideoInfo(p);
        const name = p.split(/[/\\]/).pop() || p;
        if (info && info.status === 'success') {
          const w = info.video?.width;
          const h = info.video?.height;
          newItems.push({
            path: p,
            name,
            size: info.filesize,
            duration: info.duration,
            resolution: w && h ? `${w}x${h}` : undefined,
          });
        } else {
          newItems.push({ path: p, name });
        }
      }

      setMergeList((prev) => [...prev, ...newItems]);
      setMergeStatus(null);
      setMergeResultPath(null);
    } catch (err: any) {
      alert(`Lỗi chọn file: ${err.message || String(err)}`);
    }
  };

  const handleMoveUp = (index: number) => {
    if (index <= 0) return;
    setMergeList((prev) => {
      const copy = [...prev];
      const temp = copy[index - 1];
      copy[index - 1] = copy[index];
      copy[index] = temp;
      return copy;
    });
  };

  const handleMoveDown = (index: number) => {
    if (index >= mergeList.length - 1) return;
    setMergeList((prev) => {
      const copy = [...prev];
      const temp = copy[index + 1];
      copy[index + 1] = copy[index];
      copy[index] = temp;
      return copy;
    });
  };

  const handleRemoveMergeItem = (index: number) => {
    setMergeList((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleExecuteMerge = async () => {
    if (mergeList.length < 2) {
      alert('Vui lòng thêm ít nhất 2 video để ghép nối.');
      return;
    }
    setIsMerging(true);
    setMergeStatus('Đang xử lý ghép video (kiểm tra codec & nối luồng)...');
    setMergeResultPath(null);

    try {
      const res = await bridge.mergeVideos({
        videoPaths: mergeList.map((item) => item.path),
        outputName: mergeOutputName.trim() || 'merged_video.mp4',
        forceReencode,
      });

      if (res && res.status === 'success') {
        setMergeResultPath(res.output_path);
        setMergeStatus(`Ghép thành công! Đã lưu tại: ${res.filename}`);
      } else {
        setMergeStatus(`Lỗi ghép video: ${res.message || 'Không xác định'}`);
      }
    } catch (err: any) {
      setMergeStatus(`Lỗi ghép video: ${err.message || String(err)}`);
    } finally {
      setIsMerging(false);
    }
  };

  // ─── TRIM HANDLERS ───
  const handleSelectTrimVideo = async () => {
    try {
      const path = await bridge.openVideoDialog();
      if (!path) return;

      const info = await bridge.probeVideoInfo(path);
      const name = path.split(/[/\\]/).pop() || path;
      const dur = info?.duration || 10;

      setTrimSource({
        path,
        name,
        size: info?.filesize,
        duration: dur,
        resolution: info?.video?.width && info?.video?.height ? `${info.video.width}x${info.video.height}` : undefined,
      });
      setTrimStart(0);
      setTrimEnd(Math.min(dur, 60));
      setTrimOutputName(`trimmed_${name}`);
      setTrimStatus(null);
      setTrimResultPath(null);
    } catch (err: any) {
      alert(`Lỗi chọn file: ${err.message || String(err)}`);
    }
  };

  const handleSetCurrentAsStart = () => {
    if (!videoPreviewRef.current) return;
    const cur = videoPreviewRef.current.currentTime;
    setTrimStart(Number(cur.toFixed(2)));
    if (cur >= trimEnd) {
      setTrimEnd(Number((cur + 5).toFixed(2)));
    }
  };

  const handleSetCurrentAsEnd = () => {
    if (!videoPreviewRef.current) return;
    const cur = videoPreviewRef.current.currentTime;
    setTrimEnd(Number(cur.toFixed(2)));
    if (cur <= trimStart) {
      setTrimStart(Math.max(0, Number((cur - 5).toFixed(2))));
    }
  };

  const updateTimeFromPointer = (clientX: number, mode: 'start' | 'end' | 'seek') => {
    if (!timelineTrackRef.current || !trimSource) return;
    const rect = timelineTrackRef.current.getBoundingClientRect();
    if (rect.width <= 0) return;
    const totalDuration = trimSource.duration || 10;
    const fraction = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const rawTime = fraction * totalDuration;

    if (mode === 'start') {
      const curEnd = trimEndRef.current;
      const newStart = Math.min(rawTime, curEnd - 0.1);
      const val = Number(Math.max(0, newStart).toFixed(2));
      trimStartRef.current = val;
      setTrimStart(val);
      if (videoPreviewRef.current) {
        videoPreviewRef.current.currentTime = val;
      }
    } else if (mode === 'end') {
      const curStart = trimStartRef.current;
      const newEnd = Math.max(rawTime, curStart + 0.1);
      const val = Number(Math.min(totalDuration, newEnd).toFixed(2));
      trimEndRef.current = val;
      setTrimEnd(val);
      if (videoPreviewRef.current) {
        videoPreviewRef.current.currentTime = val;
      }
    } else if (mode === 'seek') {
      const val = Number(Math.max(0, Math.min(totalDuration, rawTime)).toFixed(2));
      if (videoPreviewRef.current) {
        videoPreviewRef.current.currentTime = val;
      }
    }
  };

  const handleStartDrag = (mode: 'start' | 'end' | 'seek', e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    isDraggingHandleRef.current = mode;
    updateTimeFromPointer(e.clientX, mode);

    const onMouseMove = (ev: MouseEvent) => {
      if (!isDraggingHandleRef.current) return;
      ev.preventDefault();
      updateTimeFromPointer(ev.clientX, isDraggingHandleRef.current);
    };

    const onMouseUp = () => {
      isDraggingHandleRef.current = null;
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  };

  const handleExecuteTrim = async () => {
    if (!trimSource) {
      alert('Vui lòng chọn video nguồn trước.');
      return;
    }
    if (trimEnd <= trimStart) {
      alert('Mốc kết thúc phải lớn hơn mốc bắt đầu.');
      return;
    }

    setIsTrimming(true);
    setTrimStatus('Đang cắt video theo mốc thời gian...');
    setTrimResultPath(null);

    try {
      const res = await bridge.trimVideo({
        videoPath: trimSource.path,
        startS: trimStart,
        endS: trimEnd,
        outputName: trimOutputName.trim() || `trimmed_${trimSource.name}`,
        fastCopy,
      });

      if (res && res.status === 'success') {
        setTrimResultPath(res.output_path);
        setTrimStatus(`Cắt video thành công! Đã lưu tại: ${res.filename}`);
      } else {
        setTrimStatus(`Lỗi cắt video: ${res.message || 'Không xác định'}`);
      }
    } catch (err: any) {
      setTrimStatus(`Lỗi cắt video: ${err.message || String(err)}`);
    } finally {
      setIsTrimming(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#121214] text-zinc-200 overflow-hidden select-none">
      {/* 1. Header Toolbar */}
      <div className="h-13 border-b border-white/[0.06] bg-[#161618] px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-white/10 flex items-center justify-center text-zinc-300">
            <IconScissors size={18} />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white">Công cụ xử lý video</h1>
            <p className="text-[11px] text-zinc-500">Các tiện ích cắt ghép video nhanh chóng, lossless không suy giảm chất lượng</p>
          </div>
        </div>

        {/* Sub-tab Switcher */}
        <div className="flex items-center bg-[#1F1F23] p-1 rounded-lg border border-white/[0.06]">
          <button
            onClick={() => setActiveSubTab('merge')}
            className={`px-4 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeSubTab === 'merge'
                ? 'bg-[#2A2A30] text-white shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Ghép nối video (Merge)
          </button>
          <button
            onClick={() => setActiveSubTab('trim')}
            className={`px-4 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeSubTab === 'trim'
                ? 'bg-[#2A2A30] text-white shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Cắt video (Trim)
          </button>
        </div>
      </div>

      {/* 2. Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeSubTab === 'merge' ? (
          /* ─── TAB 1: GHÉP VIDEO ─── */
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="bg-[#18181B] border border-white/[0.06] rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-white">Danh sách video cần ghép</h2>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    Thứ tự ghép sẽ chạy tuần tự từ trên xuống dưới (#1 → #2 → ...). Có thể dùng nút mũi tên để đổi thứ tự.
                  </p>
                </div>
                <button
                  onClick={handleAddVideos}
                  className="px-3 py-1.5 bg-white text-black hover:bg-zinc-200 text-xs font-semibold rounded-md shadow flex items-center gap-1.5 transition-colors"
                >
                  <IconPlus size={14} />
                  <span>Thêm video...</span>
                </button>
              </div>

              {/* Video List Table */}
              {mergeList.length === 0 ? (
                <div className="border border-dashed border-white/10 rounded-lg p-10 text-center text-zinc-500 text-xs">
                  Chưa có video nào. Bấm nút <b>"Thêm video..."</b> ở trên để chọn các video cần ghép nối.
                </div>
              ) : (
                <div className="space-y-2">
                  {mergeList.map((item, idx) => (
                    <div
                      key={item.path + idx}
                      className="flex items-center justify-between p-3 rounded-lg bg-[#202025] border border-white/[0.04] text-xs hover:border-white/10 transition-all"
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1 pr-3">
                        <span className="w-6 h-6 rounded bg-black/40 flex items-center justify-center text-zinc-400 font-bold shrink-0">
                          {idx + 1}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-zinc-200 font-medium truncate" title={item.path}>
                            {item.name}
                          </p>
                          <div className="flex items-center gap-3 text-[11px] text-zinc-500 mt-0.5">
                            {item.resolution && <span>Độ phân giải: {item.resolution}</span>}
                            {item.duration && <span>Thời lượng: {formatTime(item.duration)}</span>}
                            {item.size && <span>Dung lượng: {formatSize(item.size)}</span>}
                          </div>
                        </div>
                      </div>

                      {/* Reorder & Delete controls */}
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={() => handleMoveUp(idx)}
                          disabled={idx === 0}
                          className="p-1.5 rounded hover:bg-white/10 text-zinc-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none"
                          title="Di chuyển lên"
                        >
                          <IconArrowUp size={14} />
                        </button>
                        <button
                          onClick={() => handleMoveDown(idx)}
                          disabled={idx === mergeList.length - 1}
                          className="p-1.5 rounded hover:bg-white/10 text-zinc-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none"
                          title="Di chuyển xuống"
                        >
                          <IconArrowDown size={14} />
                        </button>
                        <button
                          onClick={() => handleRemoveMergeItem(idx)}
                          className="p-1.5 rounded hover:bg-red-500/20 text-zinc-400 hover:text-red-400 ml-1"
                          title="Xóa khỏi danh sách"
                        >
                          <IconTrash size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Merge Settings & Execution */}
            <div className="bg-[#18181B] border border-white/[0.06] rounded-xl p-5 shadow-sm space-y-4">
              <h2 className="text-sm font-semibold text-white">Tùy chọn xuất file ghép</h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="block text-zinc-400 mb-1 font-medium">Tên file kết quả</label>
                  <input
                    type="text"
                    value={mergeOutputName}
                    onChange={(e) => setMergeOutputName(e.target.value)}
                    placeholder="merged_video.mp4"
                    className="w-full bg-[#121214] border border-white/10 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-cyan-400"
                  />
                  <p className="text-[11px] text-zinc-500 mt-1">
                    File sẽ được lưu tự động trong thư mục xuất <code>out/</code> của phần mềm.
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="block text-zinc-400 font-medium">Chế độ ghép nối</label>
                  <label className="flex items-start gap-2.5 cursor-pointer text-zinc-300">
                    <input
                      type="checkbox"
                      checked={forceReencode}
                      onChange={(e) => setForceReencode(e.target.checked)}
                      className="mt-0.5 rounded bg-zinc-800 border-white/20 text-white focus:ring-0"
                    />
                    <div>
                      <span className="font-medium">Ép buộc Re-encode thống nhất</span>
                      <p className="text-[11px] text-zinc-500">
                        Mặc định DubStudio tự nhận diện: nếu các video cùng chuẩn sẽ stream-copy tức thì; bật tùy chọn này nếu các video bị lệch fps hoặc khung hình khác nhau.
                      </p>
                    </div>
                  </label>
                </div>
              </div>

              {/* Status Message */}
              {mergeStatus && (
                <div className={`p-3 rounded-lg text-xs flex items-center justify-between ${
                  mergeResultPath ? 'bg-emerald-950/40 border border-emerald-500/30 text-emerald-300' : 'bg-zinc-800/60 border border-white/10 text-zinc-300'
                }`}>
                  <span>{mergeStatus}</span>
                  {mergeResultPath && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => bridge.openFilePath(mergeResultPath)}
                        className="px-2.5 py-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 rounded font-medium text-[11px]"
                      >
                        Mở video
                      </button>
                      <button
                        onClick={() => bridge.openFolderPath(mergeResultPath)}
                        className="px-2.5 py-1 bg-white/10 hover:bg-white/15 text-zinc-200 rounded font-medium text-[11px] flex items-center gap-1"
                      >
                        <IconFolder size={12} />
                        <span>Mở thư mục</span>
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Action Button */}
              <div className="pt-2 flex justify-end">
                <button
                  onClick={handleExecuteMerge}
                  disabled={isMerging || mergeList.length < 2}
                  className="px-6 py-2.5 bg-white text-black hover:bg-zinc-200 disabled:opacity-40 disabled:pointer-events-none rounded-lg text-xs font-semibold shadow-md transition-all flex items-center gap-2"
                >
                  {isMerging ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                      <span>Đang ghép video...</span>
                    </>
                  ) : (
                    <>
                      <IconCheck size={14} />
                      <span>Bắt đầu ghép {mergeList.length > 0 ? `(${mergeList.length} video)` : ''}</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* ─── TAB 2: CẮT VIDEO ─── */
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Source video selection */}
            <div className="bg-[#18181B] border border-white/[0.06] rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-white">Video nguồn</h2>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    Chọn video để cắt bớt đoạn mở đầu, kết thúc hoặc trích xuất đoạn cao trào.
                  </p>
                </div>
                <button
                  onClick={handleSelectTrimVideo}
                  className="px-3 py-1.5 bg-white text-black hover:bg-zinc-200 text-xs font-semibold rounded-md shadow flex items-center gap-1.5 transition-colors"
                >
                  <IconFolder size={14} />
                  <span>{trimSource ? 'Đổi video khác...' : 'Chọn video...'}</span>
                </button>
              </div>

              {trimSource && (
                <div className="p-3 bg-[#202025] rounded-lg border border-white/[0.04] flex items-center justify-between text-xs">
                  <div className="truncate pr-3">
                    <p className="text-zinc-200 font-medium truncate">{trimSource.name}</p>
                    <p className="text-[11px] text-zinc-500 mt-0.5">
                      Thời lượng: {formatTime(trimSource.duration || 0)} | Dung lượng: {formatSize(trimSource.size)} {trimSource.resolution ? `| ${trimSource.resolution}` : ''}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Trimming Controls & Preview */}
            {trimSource && (
              <div className="bg-[#18181B] border border-white/[0.06] rounded-xl p-5 shadow-sm space-y-5">
                {/* Video Preview Player */}
                <div className="bg-black/60 rounded-xl overflow-hidden border border-white/10 flex flex-col items-center">
                  <video
                    ref={videoPreviewRef}
                    src={`/api/local-file?path=${encodeURIComponent(trimSource.path)}`}
                    className="max-h-72 w-auto object-contain"
                    onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                    controls
                  />
                  <div className="w-full px-4 py-2 bg-[#1A1A1E] flex items-center justify-between text-xs border-t border-white/5">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => {
                          if (!videoPreviewRef.current) return;
                          if (videoPreviewRef.current.paused) {
                            videoPreviewRef.current.play();
                          } else {
                            videoPreviewRef.current.pause();
                          }
                        }}
                        className="p-1 rounded hover:bg-white/10 text-white"
                        title={isPlaying ? 'Tạm dừng' : 'Phát'}
                      >
                        {isPlaying ? <IconPause size={14} /> : <IconPlay size={14} />}
                      </button>
                      <span className="text-zinc-400">
                        {formatTime(currentTime)} / {formatTime(trimSource.duration || 0)}
                      </span>
                    </div>
                    <span className="text-zinc-500 text-[11px]">
                      Kéo 2 mốc trên thanh timeline hoặc bấm "Lấy vị trí hiện tại"
                    </span>
                  </div>
                </div>

                {/* ─── INTERACTIVE TRIM TIMELINE SLIDER ─── */}
                <div className="space-y-1.5 pt-1">
                  <div className="flex items-center justify-between text-xs text-zinc-400">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-zinc-200">Thanh cắt mốc timeline:</span>
                      <span className="font-mono text-[11px] text-zinc-400">
                        {formatTime(trimStart)} ➔ {formatTime(trimEnd)}
                      </span>
                    </div>
                    <span className="text-zinc-500 text-[11px]">
                      Kéo 2 tay cầm hoặc click để tua video
                    </span>
                  </div>

                  {(() => {
                    const totalDur = Math.max(0.1, trimSource.duration || 10);
                    const startPct = Math.min(100, Math.max(0, (trimStart / totalDur) * 100));
                    const endPct = Math.min(100, Math.max(0, (trimEnd / totalDur) * 100));
                    const playheadPct = Math.min(100, Math.max(0, (currentTime / totalDur) * 100));

                    return (
                      <div
                        ref={timelineTrackRef}
                        onMouseDown={(e) => handleStartDrag('seek', e)}
                        className="relative h-10 bg-[#121215] border border-white/10 rounded-lg select-none cursor-pointer flex items-center"
                      >
                        {/* Background track & ranges with inner clipping */}
                        <div className="absolute inset-0 rounded-lg overflow-hidden pointer-events-none">
                          {/* Inactive left segment */}
                          <div
                            className="absolute top-0 bottom-0 left-0 bg-black/60"
                            style={{ width: `${startPct}%` }}
                          />

                          {/* Inactive right segment */}
                          <div
                            className="absolute top-0 bottom-0 right-0 bg-black/60"
                            style={{ width: `${Math.max(0, 100 - endPct)}%` }}
                          />

                          {/* Active selected range (Trim region) */}
                          <div
                            className="absolute top-1 bottom-1 bg-white/[0.12] border-y border-white/30 backdrop-blur-xs flex items-center justify-between"
                            style={{
                              left: `${startPct}%`,
                              width: `${Math.max(0, endPct - startPct)}%`,
                            }}
                          >
                            <div className="w-full h-full bg-[repeating-linear-gradient(45deg,transparent,transparent_6px,rgba(255,255,255,0.03)_6px,rgba(255,255,255,0.03)_12px)]" />
                          </div>
                        </div>

                        {/* Playhead needle */}
                        <div
                          className="absolute top-0 bottom-0 w-[1.5px] bg-white z-20 pointer-events-none shadow-[0_0_6px_rgba(255,255,255,0.8)]"
                          style={{
                            left: `${playheadPct}%`,
                          }}
                        />

                        {/* Left Handle (Trim Start) - Dedicated Hitbox & Event Isolation */}
                        <div
                          onMouseDown={(e) => {
                            e.stopPropagation();
                            handleStartDrag('start', e);
                          }}
                          className="absolute -top-1 -bottom-1 w-4 bg-zinc-200 hover:bg-white active:bg-white text-zinc-900 rounded cursor-ew-resize flex items-center justify-center z-30 shadow-xl border border-white/80 active:scale-105 group transition-all"
                          style={{
                            left: `${startPct}%`,
                            transform: 'translateX(-50%)',
                          }}
                          title={`Mốc bắt đầu: ${formatTime(trimStart)}`}
                        >
                          <div className="flex gap-0.5 pointer-events-none">
                            <div className="w-[1.5px] h-4 bg-zinc-700 group-hover:bg-zinc-900 rounded-full" />
                            <div className="w-[1.5px] h-4 bg-zinc-700 group-hover:bg-zinc-900 rounded-full" />
                          </div>
                        </div>

                        {/* Right Handle (Trim End) - Dedicated Hitbox & Event Isolation */}
                        <div
                          onMouseDown={(e) => {
                            e.stopPropagation();
                            handleStartDrag('end', e);
                          }}
                          className="absolute -top-1 -bottom-1 w-4 bg-zinc-200 hover:bg-white active:bg-white text-zinc-900 rounded cursor-ew-resize flex items-center justify-center z-30 shadow-xl border border-white/80 active:scale-105 group transition-all"
                          style={{
                            left: `${endPct}%`,
                            transform: 'translateX(-50%)',
                          }}
                          title={`Mốc kết thúc: ${formatTime(trimEnd)}`}
                        >
                          <div className="flex gap-0.5 pointer-events-none">
                            <div className="w-[1.5px] h-4 bg-zinc-700 group-hover:bg-zinc-900 rounded-full" />
                            <div className="w-[1.5px] h-4 bg-zinc-700 group-hover:bg-zinc-900 rounded-full" />
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>

                <div className="flex items-center justify-between pt-1">
                  <h2 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">Thiết lập mốc cắt video</h2>
                  <span className="text-[11px] text-zinc-500 font-mono">Đơn vị: Giây (s)</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  {/* Start Point Box (Compact & Monochromatic) */}
                  <div className="p-3 bg-[#1B1B1F] rounded-lg border border-white/[0.06] space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-zinc-200">Mốc bắt đầu (Start)</span>
                      <span className="font-mono text-[11px] text-zinc-400">{formatTime(trimStart)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max={Math.max(0, trimEnd - 0.1)}
                        value={trimStart}
                        onChange={(e) => {
                          const val = Math.max(0, Math.min(Number(e.target.value), trimEnd - 0.1));
                          setTrimStart(val);
                          if (videoPreviewRef.current) videoPreviewRef.current.currentTime = val;
                        }}
                        className="w-24 bg-[#121214] border border-white/10 rounded px-2.5 py-1 text-xs text-zinc-200 focus:outline-none focus:border-zinc-400 font-mono text-center"
                      />
                      <span className="text-zinc-500 text-[11px]">giây</span>
                      <div className="flex-1 flex justify-end">
                        <button
                          onClick={handleSetCurrentAsStart}
                          className="px-2.5 py-1 bg-white/[0.06] hover:bg-white/10 text-zinc-300 hover:text-white rounded text-[11px] font-medium border border-white/[0.06] transition-colors whitespace-nowrap"
                        >
                          Lấy vị trí hiện tại
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* End Point Box (Compact & Monochromatic) */}
                  <div className="p-3 bg-[#1B1B1F] rounded-lg border border-white/[0.06] space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-zinc-200">Mốc kết thúc (End)</span>
                      <span className="font-mono text-[11px] text-zinc-400">{formatTime(trimEnd)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        step="0.1"
                        min={trimStart + 0.1}
                        max={trimSource.duration || 1000}
                        value={trimEnd}
                        onChange={(e) => {
                          const val = Math.max(trimStart + 0.1, Number(e.target.value));
                          setTrimEnd(val);
                          if (videoPreviewRef.current) videoPreviewRef.current.currentTime = val;
                        }}
                        className="w-24 bg-[#121214] border border-white/10 rounded px-2.5 py-1 text-xs text-zinc-200 focus:outline-none focus:border-zinc-400 font-mono text-center"
                      />
                      <span className="text-zinc-500 text-[11px]">giây</span>
                      <div className="flex-1 flex justify-end">
                        <button
                          onClick={handleSetCurrentAsEnd}
                          className="px-2.5 py-1 bg-white/[0.06] hover:bg-white/10 text-zinc-300 hover:text-white rounded text-[11px] font-medium border border-white/[0.06] transition-colors whitespace-nowrap"
                        >
                          Lấy vị trí hiện tại
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Duration indicator */}
                <div className="px-3.5 py-2 bg-[#1B1B1F] rounded-lg border border-white/[0.06] flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Độ dài đoạn cắt xuất ra:</span>
                  <span className="font-mono font-medium text-zinc-100">
                    {formatTime(Math.max(0, trimEnd - trimStart))} ({Math.max(0, trimEnd - trimStart).toFixed(2)} giây)
                  </span>
                </div>

                {/* Settings & Quality options */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-2 border-t border-white/[0.04]">
                  <div>
                    <label className="block text-zinc-400 mb-1 font-medium">Tên file kết quả</label>
                    <input
                      type="text"
                      value={trimOutputName}
                      onChange={(e) => setTrimOutputName(e.target.value)}
                      placeholder="trimmed_video.mp4"
                      className="w-full bg-[#121214] border border-white/10 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-zinc-400"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="block text-zinc-400 font-medium">Phương thức cắt</label>
                    <label className="flex items-start gap-2.5 cursor-pointer text-zinc-300">
                      <input
                        type="checkbox"
                        checked={fastCopy}
                        onChange={(e) => setFastCopy(e.target.checked)}
                        className="mt-0.5 rounded bg-zinc-800 border-white/20 text-white focus:ring-0"
                      />
                      <div>
                        <span className="font-medium">Cắt nhanh không nén (Lossless Stream-Copy)</span>
                        <p className="text-[11px] text-zinc-500">
                          Tốc độ cắt chỉ trong 1 giây, giữ nguyên 100% chất lượng gốc không re-encode. Tắt nếu bạn cần cắt chính xác đến từng mili-giây ở khung hình không phải keyframe.
                        </p>
                      </div>
                    </label>
                  </div>
                </div>

                {/* Status Message */}
                {trimStatus && (
                  <div className={`p-3 rounded-lg text-xs flex items-center justify-between ${
                    trimResultPath ? 'bg-emerald-950/40 border border-emerald-500/30 text-emerald-300' : 'bg-zinc-800/60 border border-white/10 text-zinc-300'
                  }`}>
                    <span>{trimStatus}</span>
                    {trimResultPath && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => bridge.openFilePath(trimResultPath)}
                          className="px-2.5 py-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 rounded font-medium text-[11px]"
                        >
                          Mở video
                        </button>
                        <button
                          onClick={() => bridge.openFolderPath(trimResultPath)}
                          className="px-2.5 py-1 bg-white/10 hover:bg-white/15 text-zinc-200 rounded font-medium text-[11px] flex items-center gap-1"
                        >
                          <IconFolder size={12} />
                          <span>Mở thư mục</span>
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Action button */}
                <div className="pt-2 flex justify-end">
                  <button
                    onClick={handleExecuteTrim}
                    disabled={isTrimming || trimEnd <= trimStart}
                    className="px-6 py-2.5 bg-white text-black hover:bg-zinc-200 disabled:opacity-40 disabled:pointer-events-none rounded-lg text-xs font-semibold shadow-md transition-all flex items-center gap-2"
                  >
                    {isTrimming ? (
                      <>
                        <div className="w-3.5 h-3.5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                        <span>Đang cắt video...</span>
                      </>
                    ) : (
                      <>
                        <IconCheck size={14} />
                        <span>Bắt đầu cắt video</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
