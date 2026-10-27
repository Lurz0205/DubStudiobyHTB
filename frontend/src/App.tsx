import React, { useState, useEffect, useCallback } from 'react';
import { TitleBar } from './components/TitleBar';
import { Sidebar, NavTab } from './components/Sidebar';
import { ProjectsView } from './components/projects/ProjectsView';
import { StudioWorkspace } from './components/StudioWorkspace';
import { MergeExportView } from './components/export/MergeExportView';
import { ToolsView } from './components/tools/ToolsView';
import { SubtitleStyle } from './components/video/WYSIWYGPlayer';
import { UpdatesModal } from './components/updates/UpdatesModal';
import { TutorialModal } from './components/tutorial/TutorialModal';
import { SettingsModal } from './components/settings/SettingsModal';
import { CueItem } from './components/subtitles/SubtitleEditor';
import { IconCheck } from './components/icons/StudioIcons';
import { bridge, ProjectSummary, PipelineEvent, ensureBridgeReady } from './api/bridge';

const DEFAULT_CUES: CueItem[] = [
  { id: 1, start: 0.5, end: 3.2, text: 'Chào mừng bạn đến với bản nâng cấp DubStudio 2.0.', orig: '欢迎来到DubStudio全新升级版本。' },
  { id: 2, start: 3.4, end: 6.8, text: 'Toàn bộ giao diện đã được thiết kế lại tối giản, phẳng và tinh tế.', orig: '整个界面采用专业极简风格重构。' },
  { id: 3, start: 7.1, end: 10.5, text: 'Âm lượng thuyết minh to rõ, êm tai và được giới hạn đỉnh an toàn.', orig: '声音放大清晰悦耳，无杂音。' },
  { id: 4, start: 10.9, end: 14.2, text: 'Khung hình và phụ đề khớp tuyệt đối từng pixel khi xuất video.', orig: '字幕在预览和导出时像素级完美匹配。' },
];

export const App: React.FC = () => {
  // Navigation tabs: strictly top (projects -> studio -> editor), bottom (updates -> tutorial -> settings)
  const [activeTab, setActiveTab] = useState<NavTab>('projects');

  // Active Project State
  const [jobId, setJobId] = useState<string>('');
  const [projectTitle, setProjectTitle] = useState<string>('DubStudio');
  const [videoSrc, setVideoSrc] = useState<string | undefined>(undefined);
  const [voiceSrc, setVoiceSrc] = useState<string | undefined>(undefined);
  const [bgmSrc, setBgmSrc] = useState<string | undefined>(undefined);
  const [cues, setCues] = useState<CueItem[]>(DEFAULT_CUES);
  const [aspectRatio, setAspectRatio] = useState<string>('original');
  const [voiceVol, setVoiceVol] = useState<number>(100);
  const [bgmVol, setBgmVol] = useState<number>(100);

  // Subtitle styling matching v1.1.3 style.json 100%
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle>({
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
    position: 'bottom',
    marginV: 35,
    margin_v: 35,
  });

  // Projects list
  const [projectsList, setProjectsList] = useState<ProjectSummary[]>([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);

  // Bottom Modals
  const [isUpdatesOpen, setIsUpdatesOpen] = useState(false);
  const [isTutorialOpen, setIsTutorialOpen] = useState(false);
  const [isFirstRunUser, setIsFirstRunUser] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsVersion, setSettingsVersion] = useState(0);

  // Check first run & background update check on mount
  useEffect(() => {
    bridge.isFirstRun().then((first) => {
      if (first) {
        setIsFirstRunUser(true);
        setIsTutorialOpen(true);
      }
    }).catch(() => {});

    // Silent background check for updates
    bridge.checkAppUpdate().then((info) => {
      if (info && info.has_update) {
        setToastMessage(`Đã có bản cập nhật mới (v${info.latest_version}). Bấm "Kiểm tra cập nhật" để xem.`);
      }
    }).catch(() => {});
  }, []);

  // Toast notification
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Fetch project list
  const refreshProjects = useCallback(async () => {
    setIsLoadingProjects(true);
    try {
      await ensureBridgeReady();
      const list = await bridge.getProjects();
      setProjectsList(list);

      // If no active project and list has items, load first item
      if (!jobId && list.length > 0) {
        loadProject(list[0].id, list[0].title);
      }
    } catch {
      // Standalone dev fallback
    } finally {
      setIsLoadingProjects(false);
    }
  }, [jobId]);

  useEffect(() => {
    refreshProjects();

    const onBridgeReady = () => {
      refreshProjects();
    };
    window.addEventListener('pywebviewready', onBridgeReady);
    return () => {
      window.removeEventListener('pywebviewready', onBridgeReady);
    };
  }, [refreshProjects]);

  // Real-time events
  useEffect(() => {
    const unsub = bridge.onPipelineEvent((ev: PipelineEvent) => {
      setToastMessage(`${ev.message} (${Math.round(ev.progress)}%)`);
      setTimeout(() => setToastMessage(null), 4000);
      if (ev.level === 'success' || ev.stage === 'done') {
        if (ev.job_id) {
          loadProject(ev.job_id);
        } else if (jobId) {
          loadProject(jobId);
        }
      }
    });
    return unsub;
  }, [jobId]);

  // Load a project by ID
  const loadProject = async (pId: string, title?: string) => {
    try {
      const data = await bridge.getProjectData(pId);
      if (data && !data.error) {
        setJobId(pId);
        if (title || data.title) setProjectTitle(title || data.title);

        if (data.segments && data.segments.length > 0) {
          setCues(
            data.segments.map((s: any, idx: number) => ({
              ...s,
              id: s.id || idx + 1,
              start: s.start || 0,
              end: s.end || 0,
              text: s.vi_text || s.text || '',
              orig: s.orig || s.zh || s.zh_text || '',
            }))
          );
        } else {
          setCues([]);
        }

        // Always prioritize input.mp4 for editing so the player contains the real original audio!
        if (data.media_base_url && data.has_input_video) {
          setVideoSrc(`${data.media_base_url}/input.mp4`);
        } else if (data.preview_video_url) {
          setVideoSrc(data.preview_video_url);
        } else {
          setVideoSrc(undefined);
        }

        if (data.media_base_url) {
          const vUrl = data.voice_url || (data.has_raw_voice ? `${data.media_base_url}/voice_track.wav?t=${Date.now()}` : undefined);
          const bUrl = data.bgm_url || (data.has_bgm ? `${data.media_base_url}/audio/bgm.wav?t=${Date.now()}` : undefined);
          setVoiceSrc(vUrl);
          setBgmSrc(bUrl);
        }

        if (data.style) {
          if (typeof data.style.voice_volume === 'number') {
            const vVal = data.style.voice_volume;
            setVoiceVol(vVal <= 2.0 && vVal > 0 ? Math.round(vVal * 100) : vVal);
          }
          if (typeof data.style.bgm_volume === 'number') {
            const bVal = data.style.bgm_volume;
            setBgmVol(bVal <= 2.0 && bVal > 0 ? Math.round(bVal * 100) : bVal);
          }
          setSubtitleStyle((prev) => ({
            ...prev,
            ...data.style,
            fontSize: data.style.font_size || data.style.fontSize || prev.fontSize,
            marginV: data.style.margin_v || data.style.marginV || prev.marginV,
          }));
        }
      }
    } catch (e) {
      console.error('Failed to load project', e);
    }
  };

  // Pending video for Project Naming Modal
  const [pendingVideoPath, setPendingVideoPath] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState<string>('');
  const [isNameModalOpen, setIsNameModalOpen] = useState(false);
  const [isClosingNameModal, setIsClosingNameModal] = useState(false);

  const handleCloseNameModal = () => {
    setIsClosingNameModal(true);
    setTimeout(() => {
      setIsNameModalOpen(false);
      setIsClosingNameModal(false);
      setPendingVideoPath(null);
    }, 160);
  };

  const generateDefaultProjectName = () => {
    const d = new Date();
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    const baseName = `${day}${month}${year}`;

    const existingTitles = new Set(projectsList.map((p) => p.title.toLowerCase()));
    if (!existingTitles.has(baseName.toLowerCase())) {
      return baseName;
    }
    let counter = 1;
    while (existingTitles.has(`${baseName}_${counter}`.toLowerCase())) {
      counter++;
    }
    return `${baseName}_${counter}`;
  };

  // Open native video file dialog -> Show Project Naming Modal
  const handleOpenNewVideo = async () => {
    const selectedFile = await bridge.openVideoDialog();
    if (!selectedFile) return;

    setPendingVideoPath(selectedFile);
    setNewProjectName(generateDefaultProjectName());
    setIsNameModalOpen(true);
  };

  // Confirm project creation with user-specified or default name
  const handleConfirmCreateProject = async () => {
    if (!pendingVideoPath) return;
    const finalTitle = newProjectName.trim() || generateDefaultProjectName();
    setIsNameModalOpen(false);

    const res = await bridge.createProject(pendingVideoPath, finalTitle);
    setPendingVideoPath(null);

    if (res && res.status === 'success' && res.job_id) {
      setJobId(res.job_id);
      setProjectTitle(res.title || finalTitle);
      setVideoSrc(`/media/workspace/${res.job_id}/input.mp4`);
      await refreshProjects();
      await loadProject(res.job_id, res.title || finalTitle);
      setActiveTab('studio');
    }
  };

  // Delete a project and cleanly unbind state
  const handleDeleteProject = (deletedId: string) => {
    if (jobId === deletedId) {
      const remaining = projectsList.filter((p) => p.id !== deletedId);
      if (remaining.length > 0) {
        loadProject(remaining[0].id, remaining[0].title);
      } else {
        setJobId('');
        setProjectTitle('DubStudio');
        setVideoSrc(undefined);
        setVoiceSrc(undefined);
        setBgmSrc(undefined);
        setCues([]);
      }
    }
    refreshProjects();
  };

  const handleTabChange = (tab: NavTab) => {
    if (tab === 'updates') {
      setIsUpdatesOpen(true);
    } else if (tab === 'tutorial') {
      setIsTutorialOpen(true);
    } else if (tab === 'settings') {
      setIsSettingsOpen(true);
    } else {
      setActiveTab(tab);
      if (tab === 'projects' || tab === 'studio') {
        refreshProjects();
        if (jobId && tab === 'studio') {
          loadProject(jobId);
        }
      }
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#121214] text-zinc-100 overflow-hidden font-sans select-none">
      {/* 1. Frameless Native Titlebar */}
      <TitleBar projectTitle={jobId ? projectTitle : ''} />

      {/* 2. Main Workspace Layout */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Sidebar with strict order */}
        <Sidebar activeTab={activeTab} onTabChange={handleTabChange} />

        {/* Tab Canvas with smooth view transition and persistent background execution */}
        <main className="flex-1 flex flex-col bg-[#121214] overflow-hidden">
          <div className={`view-transition flex-1 flex-col overflow-hidden ${activeTab === 'projects' ? 'flex' : 'hidden'}`}>
            <ProjectsView
              projects={projectsList}
              currentJobId={jobId}
              isLoading={isLoadingProjects}
              onRefresh={refreshProjects}
              onOpenVideoDialog={handleOpenNewVideo}
              onSelectProject={(id, title) => loadProject(id, title)}
              onDeleteProject={handleDeleteProject}
              onNavigateToTab={(tab) => setActiveTab(tab)}
            />
          </div>

          <div className={`view-transition flex-1 flex-col overflow-hidden ${activeTab === 'studio' ? 'flex' : 'hidden'}`}>
            <StudioWorkspace
              jobId={jobId}
              projectTitle={projectTitle}
              allProjects={projectsList}
              onSelectProject={(id, title) => loadProject(id, title)}
              onOpenNewVideo={handleOpenNewVideo}
              videoSrc={videoSrc}
              voiceSrc={voiceSrc}
              bgmSrc={bgmSrc}
              cues={cues}
              onCuesChange={setCues}
              subtitleStyle={subtitleStyle}
              onSubtitleStyleChange={setSubtitleStyle}
              aspectRatio={aspectRatio}
              onAspectRatioChange={setAspectRatio}
              voiceVol={voiceVol}
              bgmVol={bgmVol}
              onVoiceVolChange={setVoiceVol}
              onBgmVolChange={setBgmVol}
              onNavigateToExport={() => setActiveTab('editor')}
              isActiveTab={activeTab === 'studio'}
              settingsVersion={settingsVersion}
            />
          </div>

          <div className={`view-transition flex-1 flex-col overflow-hidden ${activeTab === 'editor' ? 'flex' : 'hidden'}`}>
            <MergeExportView
              jobId={jobId}
              projectTitle={projectTitle}
              videoSrc={videoSrc}
              voiceSrc={voiceSrc}
              bgmSrc={bgmSrc}
              cues={cues}
              activeSubtitle={cues.length > 0 ? cues[0].text : ''}
              subtitleStyle={subtitleStyle}
              aspectRatio={aspectRatio}
              onAspectRatioChange={setAspectRatio}
              voiceVol={voiceVol}
              bgmVol={bgmVol}
              onVoiceVolChange={setVoiceVol}
              onBgmVolChange={setBgmVol}
              isActiveTab={activeTab === 'editor'}
            />
          </div>

          <div className={`view-transition flex-1 flex-col overflow-hidden ${activeTab === 'tools' ? 'flex' : 'hidden'}`}>
            <ToolsView />
          </div>
        </main>
      </div>

      {/* ─── NEW PROJECT NAME MODAL ─── */}
      {isNameModalOpen && (
        <div
          className={`fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm transition-opacity duration-160 ${
            isClosingNameModal ? 'opacity-0' : 'opacity-100'
          }`}
          onClick={handleCloseNameModal}
        >
          <div
            className={`w-full max-w-md bg-[#161619] border border-white/[0.08] rounded-xl shadow-2xl p-5 space-y-4 ${
              isClosingNameModal ? 'modal-pop-exit' : 'modal-pop'
            }`}
            onClick={(e) => e.stopPropagation()}
          >
            <div>
              <h3 className="text-sm font-semibold text-zinc-100">Đặt tên dự án</h3>
              <p className="text-xs text-zinc-400 mt-1 truncate">
                Tệp: <span className="text-zinc-300">{pendingVideoPath ? pendingVideoPath.split(/[\/\\]/).pop() : ''}</span>
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                Tên dự án:
              </label>
              <input
                type="text"
                value={newProjectName}
                autoFocus
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleConfirmCreateProject();
                  if (e.key === 'Escape') handleCloseNameModal();
                }}
                className="w-full bg-[#1F1F24] border border-white/[0.1] focus:border-zinc-400 text-zinc-100 rounded-lg px-3 py-2 text-xs focus:outline-none transition-colors"
                placeholder="Ví dụ: 25102026"
              />
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-white/[0.06]">
              <button
                onClick={handleCloseNameModal}
                className="px-3.5 py-1.5 rounded-lg bg-[#222226] hover:bg-[#2A2A30] text-zinc-300 hover:text-white text-xs font-medium transition-colors"
              >
                Hủy
              </button>
              <button
                onClick={handleConfirmCreateProject}
                className="px-4 py-1.5 rounded-lg bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-all active:scale-98 shadow-sm"
              >
                Xong
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Pipeline Toast */}
      {toastMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-[#1F1F24] border border-white/10 text-white text-xs px-3.5 py-2 rounded-lg shadow-xl flex items-center gap-2 animate-fade-in">
          <IconCheck size={13} className="text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Bottom Modals */}
      <UpdatesModal
        isOpen={isUpdatesOpen}
        onClose={() => setIsUpdatesOpen(false)}
      />

      <TutorialModal
        isOpen={isTutorialOpen}
        onClose={() => {
          setIsTutorialOpen(false);
          setIsFirstRunUser(false);
        }}
        isFirstRun={isFirstRunUser}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => {
          setIsSettingsOpen(false);
          setSettingsVersion((v) => v + 1);
        }}
      />
    </div>
  );
};

export default App;
