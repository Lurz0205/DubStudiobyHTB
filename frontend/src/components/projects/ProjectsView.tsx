import React, { useState, useEffect } from 'react';
import { 
  IconFolder, IconFilm, IconPlus, IconRefresh, 
  IconTrash, IconEdit, IconCheck, IconChevronRight 
} from '../icons/StudioIcons';
import { bridge, ProjectSummary } from '../../api/bridge';

interface ProjectsViewProps {
  projects: ProjectSummary[];
  currentJobId: string;
  isLoading: boolean;
  onRefresh: () => void;
  onOpenVideoDialog: () => void;
  onSelectProject: (jobId: string, title?: string) => void;
  onDeleteProject?: (jobId: string) => void;
  onNavigateToTab: (tab: 'studio' | 'editor') => void;
}

export const ProjectsView: React.FC<ProjectsViewProps> = ({
  projects,
  currentJobId,
  isLoading,
  onRefresh,
  onOpenVideoDialog,
  onSelectProject,
  onDeleteProject,
  onNavigateToTab,
}) => {
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState<{ id: string; title: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isClosingDelete, setIsClosingDelete] = useState(false);

  useEffect(() => {
    onRefresh();
  }, []);

  const handleStartRename = (p: ProjectSummary) => {
    setRenamingId(p.id);
    setNewTitle(p.title);
  };

  const handleSaveRename = async (jobId: string) => {
    if (newTitle.trim()) {
      await bridge.renameProject(jobId, newTitle.trim());
      setRenamingId(null);
      onRefresh();
    }
  };

  const requestDelete = (jobId: string, title: string) => {
    setDeleteConfirm({ id: jobId, title });
    setIsClosingDelete(false);
  };

  const cancelDelete = () => {
    setIsClosingDelete(true);
    setTimeout(() => {
      setDeleteConfirm(null);
      setIsClosingDelete(false);
    }, 160);
  };

  const executeDelete = async () => {
    if (!deleteConfirm) return;
    setIsDeleting(true);
    try {
      await bridge.deleteProject(deleteConfirm.id);
      if (onDeleteProject) {
        onDeleteProject(deleteConfirm.id);
      } else {
        onRefresh();
      }
    } finally {
      setIsDeleting(false);
      setDeleteConfirm(null);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-6 overflow-hidden max-w-5xl mx-auto w-full select-none">
      {/* 1. Header Toolbar */}
      <div className="flex items-center justify-between pb-4 border-b border-white/[0.06] mb-5">
        <div>
          <h2 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
            <IconFolder size={18} className="text-zinc-300" />
            <span>Quản lý Dự án Lồng tiếng</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400">
              {projects.length}
            </span>
          </h2>
          <p className="text-xs text-zinc-500 mt-1">
            Mỗi tệp video là một dự án độc lập, lưu trữ toàn bộ phụ đề, âm thanh và video đã xử lý.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={onRefresh}
            className="p-2 rounded-md bg-[#1F1F23] hover:bg-[#2A2A30] text-zinc-400 hover:text-white transition-colors border border-white/[0.06]"
            title="Làm mới danh sách dự án"
          >
            <IconRefresh size={14} className={isLoading ? 'animate-spin' : ''} />
          </button>

          <button
            onClick={onOpenVideoDialog}
            className="px-4 py-2 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold flex items-center gap-2 transition-all active:scale-98 shadow-sm"
          >
            <IconPlus size={14} />
            <span>Thêm tệp video mới</span>
          </button>
        </div>
      </div>

      {/* 2. Projects List */}
      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
        {projects.length === 0 ? (
          <div className="h-72 flex flex-col items-center justify-center text-center p-8 border border-dashed border-white/[0.08] rounded-xl bg-[#161619]/50">
            <div className="w-12 h-12 rounded-xl bg-[#1F1F24] flex items-center justify-center text-zinc-500 mb-3">
              <IconFilm size={24} />
            </div>
            <h3 className="text-sm font-semibold text-zinc-200 mb-1">Chưa có dự án nào</h3>
            <p className="text-xs text-zinc-500 max-w-sm mb-4 leading-relaxed">
              Chọn video tiếng Trung bất kỳ từ máy tính để bắt đầu quy trình lồng tiếng và tạo phụ đề tiếng Việt tự động.
            </p>
            <button
              onClick={onOpenVideoDialog}
              className="px-4 py-2 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold flex items-center gap-1.5 transition-colors"
            >
              <IconPlus size={14} />
              <span>Mở video ngay</span>
            </button>
          </div>
        ) : (
          projects.map((p) => {
            const isCurrent = p.id === currentJobId;
            const dateStr = p.modified_time
              ? new Date(p.modified_time * 1000).toLocaleString('vi-VN')
              : 'Gần đây';

            return (
              <div
                key={p.id}
                className={`p-4 rounded-xl border transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                  isCurrent
                    ? 'bg-[#1E1E23] border-white/20 shadow-md'
                    : 'bg-[#161619] border-white/[0.06] hover:bg-[#1A1A1E] hover:border-white/10'
                }`}
              >
                {/* Left: Thumbnail & Details */}
                <div className="flex items-start gap-3.5 flex-1 min-w-0">
                  <div className="w-11 h-11 rounded-lg bg-[#222227] flex items-center justify-center text-zinc-300 shrink-0 border border-white/[0.04]">
                    <IconFilm size={20} />
                  </div>

                  <div className="flex-1 min-w-0">
                    {renamingId === p.id ? (
                      <div className="flex items-center gap-2 mb-1">
                        <input
                          type="text"
                          value={newTitle}
                          onChange={(e) => setNewTitle(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleSaveRename(p.id)}
                          className="bg-[#26262B] border border-white/20 rounded px-2.5 py-1 text-xs text-white focus:outline-none"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveRename(p.id)}
                          className="px-2 py-1 rounded bg-white text-black text-xs font-semibold"
                        >
                          Lưu
                        </button>
                        <button
                          onClick={() => setRenamingId(null)}
                          className="px-2 py-1 rounded bg-zinc-800 text-zinc-400 text-xs"
                        >
                          Hủy
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span 
                          onClick={() => {
                            onSelectProject(p.id, p.title);
                            onNavigateToTab('studio');
                          }}
                          className="text-xs font-semibold text-zinc-100 hover:text-white cursor-pointer truncate"
                        >
                          {p.title}
                        </span>
                        {isCurrent && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-white shrink-0">
                            Đang mở
                          </span>
                        )}
                      </div>
                    )}

                    <div className="flex items-center gap-3 text-[11px] text-zinc-500 mt-1">
                      <span>{dateStr}</span>
                      <span>&bull;</span>
                      <span className="truncate max-w-[200px]">ID: {p.id}</span>
                    </div>

                    {/* Step Badges (Quy trình 4 bước) */}
                    <div className="flex items-center gap-1.5 mt-2.5 text-[10px]">
                      <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 flex items-center gap-1">
                        <IconCheck size={10} className="text-emerald-400" /> Video gốc
                      </span>

                      <span className={`px-2 py-0.5 rounded flex items-center gap-1 ${
                        p.has_subtitles 
                          ? 'bg-zinc-800 text-zinc-300' 
                          : 'bg-zinc-900 text-zinc-600'
                      }`}>
                        {p.has_subtitles && <IconCheck size={10} className="text-emerald-400" />}
                        Phụ đề
                      </span>

                      <span className={`px-2 py-0.5 rounded flex items-center gap-1 ${
                        p.has_dub 
                          ? 'bg-zinc-800 text-zinc-300' 
                          : 'bg-zinc-900 text-zinc-600'
                      }`}>
                        {p.has_dub && <IconCheck size={10} className="text-emerald-400" />}
                        Lồng tiếng
                      </span>

                      <span className={`px-2 py-0.5 rounded flex items-center gap-1 ${
                        p.has_export 
                          ? 'bg-zinc-800 text-emerald-400 border border-emerald-800/40' 
                          : 'bg-zinc-900 text-zinc-600'
                      }`}>
                        {p.has_export && <IconCheck size={10} className="text-emerald-400" />}
                        Đã xuất
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleStartRename(p)}
                    className="p-2 rounded-md hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 transition-colors"
                    title="Đổi tên dự án"
                  >
                    <IconEdit size={14} />
                  </button>

                  <button
                    onClick={() => requestDelete(p.id, p.title)}
                    className="p-2 rounded-md hover:bg-red-500/10 text-zinc-500 hover:text-red-400 transition-colors"
                    title="Xóa dự án"
                  >
                    <IconTrash size={14} />
                  </button>

                  <button
                    onClick={() => {
                      onSelectProject(p.id, p.title);
                      onNavigateToTab('studio');
                    }}
                    className="px-3 py-1.5 rounded-md bg-[#222227] hover:bg-[#2A2A30] text-zinc-200 text-xs font-medium border border-white/[0.08] flex items-center gap-1.5 transition-colors"
                  >
                    <span>Lồng tiếng</span>
                    <IconChevronRight size={12} />
                  </button>

                  <button
                    onClick={() => {
                      onSelectProject(p.id, p.title);
                      onNavigateToTab('editor');
                    }}
                    className="px-3 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold flex items-center gap-1.5 transition-colors"
                  >
                    <span>Xuất video</span>
                    <IconChevronRight size={12} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
      {/* Modern Dark-Themed Delete Confirmation Modal */}
      {deleteConfirm && (
        <div
          className={`fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm select-none p-4 transition-opacity duration-160 ${
            isClosingDelete ? 'opacity-0' : 'opacity-100'
          }`}
          onClick={cancelDelete}
        >
          <div
            className={`w-full max-w-md bg-[#161619] border border-white/10 rounded-xl shadow-2xl p-5 space-y-4 ${
              isClosingDelete ? 'modal-pop-exit' : 'modal-pop'
            }`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-lg bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400 shrink-0">
                <IconTrash size={18} />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-zinc-100">Xác nhận xóa dự án</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  Bạn có chắc muốn xóa dự án <strong className="text-zinc-200 font-medium">"{deleteConfirm.title}"</strong>? Toàn bộ file thuyết minh, nhạc nền và phụ đề sẽ bị xóa vĩnh viễn khỏi máy tính.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-white/[0.06]">
              <button
                onClick={cancelDelete}
                disabled={isDeleting}
                className="px-3.5 py-1.5 rounded-lg bg-[#222226] hover:bg-[#2A2A30] text-zinc-300 hover:text-white text-xs font-medium transition-colors"
              >
                Hủy bỏ
              </button>
              <button
                onClick={executeDelete}
                disabled={isDeleting}
                className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all active:scale-98 shadow-sm disabled:opacity-50"
              >
                <IconTrash size={13} />
                <span>{isDeleting ? 'Đang xóa...' : 'Xóa vĩnh viễn'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
