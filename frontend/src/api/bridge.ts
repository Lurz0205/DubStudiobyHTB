/**
 * Zero-Port Native Bridge Client for DubStudio 2.0.
 * Directly communicates with Python via window.pywebview.api in memory.
 * Falls back to REST/fetch only when developing in standalone browser.
 */

export interface ProjectSummary {
  id: string;
  title: string;
  modified_time: number;
  has_video: boolean;
  has_subtitles: boolean;
  has_dub?: boolean;
  has_export?: boolean;
  step?: number;
}

export interface PipelineEvent {
  stage: string;
  progress: number;
  message: string;
  level: 'info' | 'warning' | 'error' | 'success' | 'manual_input_required';
  job_id: string;
  out_path?: string;
}

export interface CueItem {
  id: number;
  start: number;
  end: number;
  text: string;
  vi_text?: string;
  orig?: string;
  source_text?: string;
  voice?: string;
  speed?: number;
  gender?: string;
  has_tts?: boolean;
  tts_file?: string;
  tts_dur?: number;
  voice_start?: number;
  voice_dur?: number;
  fit?: any;
  fit_rate?: number;
  cues?: any[];
  user_edited_voice?: boolean;
  mute_sub?: boolean;
  muted_sub?: boolean;
  mute_tts?: boolean;
  muted_tts?: boolean;
}

export const DEFAULT_MALE_VOICES = [
  'Adam', 'Adam bựa', 'Hải Đăng', 'Minh Triết', 'Minh Đức', 'Phạm Tuyên',
  'Quang Sơn', 'Quốc Tuấn', 'Thanh Bình', 'Thiền Tâm Đức', 'Thiện Minh',
  'Thái Sơn', 'Xuân Vĩnh', 'Đức Trí'
];

export const DEFAULT_FEMALE_VOICES = [
  'Kim Thanh', 'Mai Anh', 'Mỹ Duyên', 'Ngọc Huyền', 'Ngọc Linh',
  'Ngọc Trân', 'Quỳnh Anh', 'Thùy Dung', 'Thục Đoan', 'Trúc Ly', 'Đoan Trang'
];

export const isNativeDesktop = (): boolean => {
  return typeof (window as any).pywebview?.api !== 'undefined';
};

/**
 * Wait for pywebview bridge to be injected into the window.
 * Resolves immediately if already available, or waits for 'pywebviewready' event,
 * with fast polling fallback (every 25ms up to 3.5s).
 */
export const ensureBridgeReady = (): Promise<boolean> => {
  if (typeof (window as any).pywebview?.api !== 'undefined') {
    return Promise.resolve(true);
  }

  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (!done) {
        done = true;
        clearInterval(timer);
        window.removeEventListener('pywebviewready', finish);
        resolve(typeof (window as any).pywebview?.api !== 'undefined');
      }
    };

    window.addEventListener('pywebviewready', finish);

    const timer = setInterval(() => {
      if (typeof (window as any).pywebview?.api !== 'undefined') {
        finish();
      }
    }, 25);

    setTimeout(finish, 3500);
  });
};

export const bridge = {
  // 1. Native Window Controls
  minimize: () => {
    if (isNativeDesktop()) (window as any).pywebview.api.minimize();
  },
  toggleMaximize: () => {
    if (isNativeDesktop()) (window as any).pywebview.api.toggle_maximize();
  },
  close: () => {
    if (isNativeDesktop()) (window as any).pywebview.api.close();
  },

  // 2. Native File & Folder Dialogs
  openVideoDialog: async (): Promise<string | null> => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.open_video_dialog();
    }
    return null;
  },

  openMultipleVideosDialog: async (): Promise<string[]> => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.open_multiple_videos_dialog();
    }
    return [];
  },

  probeVideoInfo: async (videoPath: string): Promise<any> => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.probe_video_info(videoPath);
    }
    return { status: 'error', message: 'Chỉ khả dụng trong chế độ Desktop' };
  },

  trimVideo: async (options: {
    videoPath: string;
    startS: number;
    endS: number;
    outputName?: string;
    fastCopy?: boolean;
  }): Promise<any> => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.trim_video(
        options.videoPath,
        options.startS,
        options.endS,
        options.outputName || '',
        options.fastCopy !== false
      );
    }
    return { status: 'error', message: 'Chỉ khả dụng trong chế độ Desktop' };
  },

  mergeVideos: async (options: {
    videoPaths: string[];
    outputName?: string;
    forceReencode?: boolean;
  }): Promise<any> => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.merge_videos(
        options.videoPaths,
        options.outputName || 'merged_video.mp4',
        Boolean(options.forceReencode)
      );
    }
    return { status: 'error', message: 'Chỉ khả dụng trong chế độ Desktop' };
  },

  previewVoice: async (voice: string): Promise<any> => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.preview_voice(voice);
    }
    return {
      status: 'success',
      audio_url: `/api/voices/preview?voice=${encodeURIComponent(voice)}`,
    };
  },

  openImageDialog: async (): Promise<string | null> => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.open_image_dialog();
    }
    return null;
  },

  openFolderDialog: async (defaultDir?: string): Promise<string | null> => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.open_folder_dialog(defaultDir);
    }
    return null;
  },

  // 3. Project Management
  createProject: async (videoPath: string, title?: string) => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.create_project(videoPath, title || '');
    }
    return { status: 'error', message: 'Chỉ khả dụng trong chế độ Desktop' };
  },

  getProjects: async (): Promise<ProjectSummary[]> => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.get_projects();
    }
    try {
      const res = await fetch('/api/jobs');
      const data = await res.json();
      return (data.jobs || []).map((j: any) => ({
        id: j.id,
        title: j.video_name || j.title || j.id,
        modified_time: j.updated_at || 0,
        has_video: true,
        has_subtitles: true,
        step: 2,
      }));
    } catch {
      return [];
    }
  },

  deleteProject: async (jobId: string) => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.delete_project(jobId);
    }
    const res = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
    return await res.json();
  },

  renameProject: async (jobId: string, newTitle: string) => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.rename_project(jobId, newTitle);
    }
    return { status: 'success' };
  },

  getProjectData: async (jobId: string) => {
    await ensureBridgeReady();
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.get_project_data(jobId);
    }
    const res = await fetch(`/api/jobs/${jobId}/cues`);
    return await res.json();
  },

  saveProjectSegments: async (jobId: string, segments: any[]) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.save_project_segments(jobId, segments);
    }
    const res = await fetch(`/api/jobs/${jobId}/cues`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ segments }),
    });
    return await res.json();
  },

  saveProjectStyle: async (jobId: string, style: any) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.save_project_style(jobId, style);
    }
    const res = await fetch(`/api/jobs/${jobId}/style`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(style),
    });
    return await res.json();
  },

  saveProjectConfig: async (jobId: string, config: any) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.save_project_config(jobId, config);
    }
    const res = await fetch(`/api/jobs/${jobId}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    return await res.json();
  },

  autoSplitCues: async (jobId: string, wordsPerLine: number = 6) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.auto_split_cues(jobId, wordsPerLine);
    }
    return { status: 'error', message: 'Desktop required' };
  },

  // 4. Pipeline Execution
  runPipeline: async (jobId: string, options: any) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.run_pipeline(jobId, options);
    }
    const res = await fetch(`/api/jobs/${jobId}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options),
    });
    return await res.json();
  },

  exportProjectVideo: async (jobId: string, options?: any) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.export_project_video(jobId, options);
    }
    return { status: 'started' };
  },

  // 5. System Utilities
  openFilePath: async (path: string) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.open_file_path(path);
    }
    return { status: 'error' };
  },

  openFolderPath: async (path: string) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.open_folder_path(path);
    }
    return { status: 'error' };
  },

  synthesizeSingleSegment: async (
    jobId: string,
    segId: number,
    options?: { text?: string; speed?: number; voice?: string }
  ) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.synthesize_single_segment(
        jobId,
        segId,
        options?.text,
        options?.speed,
        options?.voice
      );
    }
    const res = await fetch(`/api/jobs/${jobId}/segments/${segId}/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options || {}),
    });
    return await res.json();
  },

  // 6. Settings, Gemini Browser & Updates
  isFirstRun: async (): Promise<boolean> => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.is_first_run();
    }
    return false;
  },

  markFirstRunDone: async (done: boolean = true) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.mark_first_run_done(done);
    }
    return { status: 'success' };
  },

  launchGeminiBrowser: async () => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.launch_gemini_browser();
    }
    window.open('https://gemini.google.com/app', '_blank');
    return { status: 'success' };
  },

  checkGeminiBrowserStatus: async () => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.check_gemini_browser_status();
    }
    return { ready: false, message: 'Desktop required' };
  },

  getAppSettings: async () => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.get_app_settings();
    }
    const res = await fetch('/api/settings');
    return await res.json();
  },

  saveAppSettings: async (settings: any) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.save_app_settings(settings);
    }
    return { status: 'success', message: 'Đã lưu cài đặt thành công!' };
  },

  testApiKey: async (provider: string, key: string) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.test_api_key(provider, key);
    }
    return { status: 'success', message: 'API key format valid' };
  },

  checkForUpdates: async () => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.check_for_updates();
    }
    return { has_update: false, current_version: 'v2.0.0' };
  },

  checkAppUpdate: async () => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.check_for_updates();
    }
    return { has_update: false, current_version: 'v2.0.0' };
  },

  getComponentsStatus: async () => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.get_components_status();
    }
    return [];
  },

  downloadComponent: async (pkgId: string) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.download_component(pkgId);
    }
    return { status: 'error', message: 'Desktop required' };
  },

  // Manual Translation
  submitManualTranslation: async (jobId: string, text: string, cancelled: boolean = false) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.submit_manual_translation(jobId, text, cancelled);
    }
    return { status: 'success' };
  },

  getManualTranslatePrompt: async (jobId: string) => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.get_manual_translate_prompt(jobId);
    }
    return { status: 'error', message: 'Desktop required' };
  },

  // Hardware Diagnostics
  getGpuInfo: async () => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.get_gpu_info();
    }
    return { status: 'OK_CUDA', card_name: 'NVIDIA GPU (Dev)', vram_gb: 4.0, cur_driver: '535.00' };
  },

  exportDiagnosticBundle: async () => {
    if (isNativeDesktop()) {
      return await (window as any).pywebview.api.export_diagnostic_bundle();
    }
    return { status: 'error', message: 'Desktop required' };
  },

  // 7. Real-time Event Subscription
  onPipelineEvent: (callback: (event: PipelineEvent) => void) => {
    const handler = (e: any) => {
      if (e.detail) callback(e.detail);
    };
    window.addEventListener('dubstudio-event', handler);
    return () => window.removeEventListener('dubstudio-event', handler);
  },
};
