import React, { useRef, useState, useEffect } from 'react';
import type { CueItem } from '../../api/bridge';
import { 
  IconPlay, IconPause, IconRewind5, IconForward5, 
  IconMaximize 
} from '../icons/StudioIcons';

export interface SubtitleStyle {
  font_name?: string;
  fontSize?: number;
  font_size?: number;
  primary_color?: string;
  outline_color?: string;
  outline_width?: number;
  has_box?: boolean;
  box_color?: string;
  box_opacity?: number;
  box_radius?: number;
  box_mode?: 'wrap_text' | 'full_width';
  box_width_pct?: number;
  pos_y_pct?: number; // 5% - 95%
  position?: 'bottom' | 'middle' | 'top';
  marginV?: number;
  margin_v?: number;
  paddingX?: number;
  paddingY?: number;
}

export interface ColorBoxItem {
  id: string | number;
  x: number;
  y: number;
  w: number;
  h: number;
  color: string;
  opacity?: number;
  radius?: number;
  rotation?: number;
  text?: string;
  font_name?: string;
  font_size?: number;
  text_color?: string;
  text_outline_color?: string;
  text_outline_width?: number;
  text_align?: 'left' | 'center' | 'right';
  enabled?: boolean;
}

export interface WYSIWYGPlayerProps {
  videoSrc?: string;
  activeSubtitle?: string;
  cues?: CueItem[];
  subtitleStyle?: SubtitleStyle;
  onSubtitleStyleChange?: (updates: Partial<SubtitleStyle>) => void;
  aspectRatio?: string;
  onAspectRatioChange?: (ratio: string) => void;
  canvasColor?: string;
  colorBoxes?: ColorBoxItem[];
  selectedBoxIndex?: number;
  onSelectBoxIndex?: (index: number) => void;
  onUpdateColorBox?: (index: number, updates: Partial<ColorBoxItem>) => void;
  logo?: {
    path?: string;
    position?: string;
    margin?: number;
    scale_pct?: number;
    opacity?: number;
  };
  voiceSrc?: string;
  bgmSrc?: string;
  voiceVol?: number;
  bgmVol?: number;
  origRanges?: { start: number; end: number }[];
  customBgmSrc?: string;
  customBgmVol?: number;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  onPlayPauseToggle: () => void;
  onSeek: (time: number) => void;
  onTimeUpdate?: (time: number) => void;
  onDurationChange?: (dur: number) => void;
  hideHeader?: boolean;
}

function hexToRgba(hex: string, alpha: number): string {
  if (!hex) return `rgba(0, 0, 0, ${alpha})`;
  if (hex.startsWith('rgba')) return hex;
  let c = hex.replace('#', '');
  if (c.length === 3) {
    c = c.split('').map((x) => x + x).join('');
  }
  if (c.length === 6) {
    const r = parseInt(c.substring(0, 2), 16);
    const g = parseInt(c.substring(2, 4), 16);
    const b = parseInt(c.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
  return `rgba(0, 0, 0, ${alpha})`;
}

export const WYSIWYGPlayer: React.FC<WYSIWYGPlayerProps> = ({
  videoSrc,
  activeSubtitle = '',
  cues = [],
  subtitleStyle = {},
  onSubtitleStyleChange,
  aspectRatio = 'original',
  onAspectRatioChange,
  canvasColor = '#000000',
  colorBoxes = [],
  selectedBoxIndex = -1,
  onSelectBoxIndex,
  onUpdateColorBox,
  logo,
  voiceSrc,
  bgmSrc,
  voiceVol = 100,
  bgmVol = 100,
  origRanges = [],
  customBgmSrc,
  customBgmVol = 50,
  currentTime,
  duration,
  isPlaying,
  onPlayPauseToggle,
  onSeek,
  onTimeUpdate,
  onDurationChange,
  hideHeader = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const voiceAudioRef = useRef<HTMLAudioElement>(null);
  const bgmAudioRef = useRef<HTMLAudioElement>(null);
  const customBgmAudioRef = useRef<HTMLAudioElement>(null);

  const [videoDim, setVideoDim] = useState({ w: 1920, h: 1080 });
  const [innerRect, setInnerRect] = useState({ left: 0, top: 0, width: 0, height: 0, scale: 1 });
  const [outerCanvasRect, setOuterCanvasRect] = useState({ left: 0, top: 0, width: 0, height: 0 });
  const [canvasHeightPx, setCanvasHeightPx] = useState(40);

  // Subtitle Dragging & Resizing State
  const [isHovered, setIsHovered] = useState(false);
  const [dragMode, setDragMode] = useState<'move_y' | 'resize_left' | 'resize_right' | null>(null);
  const dragStartRef = useRef<{ clientX: number; clientY: number; startPosY: number; startWidth: number }>({
    clientX: 0,
    clientY: 0,
    startPosY: 86,
    startWidth: 85,
  });

  // Color Box Direct Preview Manipulation State
  const [boxDragMode, setBoxDragMode] = useState<'move' | 'resize_se' | 'resize_e' | 'resize_s' | 'rotate' | null>(null);
  const [activeDragBoxIdx, setActiveDragBoxIdx] = useState<number | null>(null);
  const boxDragStartRef = useRef<{
    clientX: number;
    clientY: number;
    startX: number;
    startY: number;
    startW: number;
    startH: number;
    startRot: number;
    centerPxX: number;
    centerPxY: number;
  }>({
    clientX: 0,
    clientY: 0,
    startX: 0,
    startY: 0,
    startW: 0,
    startH: 0,
    startRot: 0,
    centerPxX: 0,
    centerPxY: 0,
  });

  const fontName = subtitleStyle.font_name || 'Arial';
  const rawFontSize = subtitleStyle.fontSize || subtitleStyle.font_size || 26;
  const primaryColor = subtitleStyle.primary_color || '#FFFFFF';
  const outlineColor = subtitleStyle.outline_color || '#000000';
  const outlineWidth = subtitleStyle.outline_width !== undefined ? subtitleStyle.outline_width : 2;
  const hasBox = subtitleStyle.has_box !== undefined ? subtitleStyle.has_box : true;
  const boxColor = subtitleStyle.box_color || '#000000';
  const boxOpacity = subtitleStyle.box_opacity !== undefined ? subtitleStyle.box_opacity : 0.6;
  const boxRadius = subtitleStyle.box_radius !== undefined ? subtitleStyle.box_radius : 6;
  const boxMode = subtitleStyle.box_mode || 'full_width';
  const boxWidthPct = subtitleStyle.box_width_pct !== undefined ? subtitleStyle.box_width_pct : 85;
  const paddingX = subtitleStyle.paddingX || 14;
  const paddingY = subtitleStyle.paddingY || 8;

  // Resolve continuous Y position percentage (0% = top, 100% = bottom, default ~86%)
  let posYPct = 86;
  if (subtitleStyle.pos_y_pct !== undefined) {
    posYPct = subtitleStyle.pos_y_pct;
  } else if (subtitleStyle.position === 'top') {
    const mv = subtitleStyle.marginV || subtitleStyle.margin_v || 35;
    const refH = innerRect.height || 720;
    const cy = (mv / 720) * refH + canvasHeightPx / 2;
    posYPct = (cy / refH) * 100;
  } else if (subtitleStyle.position === 'middle') {
    posYPct = 50;
  } else if (subtitleStyle.marginV !== undefined || subtitleStyle.margin_v !== undefined) {
    const mv = subtitleStyle.marginV || subtitleStyle.margin_v || 35;
    const refH = innerRect.height || 720;
    const boxBottom = refH - (mv / 720) * refH;
    const cy = boxBottom - canvasHeightPx / 2;
    posYPct = Math.max(5, Math.min(95, (cy / refH) * 100));
  }

  // Synchronize audio element volumes & ducking with video playback, origRanges, and per-cue mute_tts
  const syncAudioVolumes = (curTime: number) => {
    // Check if curTime falls within any cue where user muted TTS
    const isMutedTtsCue = cues && cues.some((c) => {
      const isMuted = Boolean(c.mute_tts || (c as any).muted_tts);
      return isMuted && curTime >= c.start && curTime <= c.end;
    });

    if (!voiceSrc) {
      if (videoRef.current) {
        videoRef.current.volume = 1.0;
        videoRef.current.muted = false;
      }
      return;
    }

    const inOrig = (origRanges && origRanges.some((r) => curTime >= r.start && curTime <= r.end)) || isMutedTtsCue;
    if (inOrig) {
      // During origRanges (Giữ âm gốc) or when TTS is muted: video original audio is unmuted at 1.0
      if (videoRef.current) {
        videoRef.current.volume = 1.0;
        videoRef.current.muted = false;
      }
      if (bgmAudioRef.current) {
        bgmAudioRef.current.volume = Math.min(1.0, (bgmVol / 100.0) * (isMutedTtsCue ? 1.0 : 0.15));
      }
    } else {
      // Normal dubbing: video original audio is muted (0.0); BGM plays at full user volume
      if (videoRef.current) {
        videoRef.current.volume = 0.0;
        videoRef.current.muted = true;
      }
      if (bgmAudioRef.current) {
        bgmAudioRef.current.volume = Math.min(1.0, bgmVol / 100.0);
      }
    }

    if (voiceAudioRef.current) {
      if (isMutedTtsCue) {
        voiceAudioRef.current.volume = 0.0;
        voiceAudioRef.current.muted = true;
      } else {
        voiceAudioRef.current.volume = Math.min(1.0, voiceVol / 100.0);
        voiceAudioRef.current.muted = false;
      }
    }
    if (customBgmAudioRef.current) {
      customBgmAudioRef.current.volume = Math.min(1.0, (customBgmVol || 0) / 100.0);
    }
  };

  // Keep latest onTimeUpdate callback in ref to prevent tearing down the animation loop
  const onTimeUpdateRef = useRef(onTimeUpdate);
  useEffect(() => {
    onTimeUpdateRef.current = onTimeUpdate;
  });

  // Direct user-gesture playback control: avoids browser autoplay policy blocks on unmuted video
  const handleDirectPlayPause = () => {
    const v = videoRef.current;
    if (!v) {
      onPlayPauseToggle();
      return;
    }

    // If at the end, rewind to beginning
    if (v.duration && (v.currentTime >= v.duration - 0.08 || v.ended)) {
      v.currentTime = 0;
      if (voiceAudioRef.current) voiceAudioRef.current.currentTime = 0;
      if (bgmAudioRef.current) bgmAudioRef.current.currentTime = 0;
      if (customBgmAudioRef.current) customBgmAudioRef.current.currentTime = 0;
      onSeek(0);
    }

    if (v.paused) {
      v.play().catch((err) => {
        console.warn('[WYSIWYGPlayer] Direct video play error:', err);
      });
      if (voiceSrc) {
        voiceAudioRef.current?.play().catch(() => {});
        bgmAudioRef.current?.play().catch(() => {});
        customBgmAudioRef.current?.play().catch(() => {});
      }
    } else {
      v.pause();
      voiceAudioRef.current?.pause();
      bgmAudioRef.current?.pause();
      customBgmAudioRef.current?.pause();
    }
    onPlayPauseToggle();
  };

  const handleDirectSeek = (time: number) => {
    const safeT = Math.max(0, time);
    if (videoRef.current) videoRef.current.currentTime = safeT;
    if (voiceAudioRef.current) voiceAudioRef.current.currentTime = safeT;
    if (bgmAudioRef.current) bgmAudioRef.current.currentTime = safeT;
    if (customBgmAudioRef.current) customBgmAudioRef.current.currentTime = safeT;
    syncAudioVolumes(safeT);
    onSeek(safeT);
  };

  // Sync play / pause state across video and all audio stems
  useEffect(() => {
    if (isPlaying) {
      if (videoRef.current && videoRef.current.paused) {
        // If at end, rewind first
        if (videoRef.current.duration && (videoRef.current.currentTime >= videoRef.current.duration - 0.08 || videoRef.current.ended)) {
          videoRef.current.currentTime = 0;
          if (voiceAudioRef.current) voiceAudioRef.current.currentTime = 0;
          if (bgmAudioRef.current) bgmAudioRef.current.currentTime = 0;
          if (customBgmAudioRef.current) customBgmAudioRef.current.currentTime = 0;
        }
        videoRef.current.play().catch((err) => {
          console.warn('[WYSIWYGPlayer] Programmatic video play error:', err);
        });
      }
      if (voiceSrc) {
        if (voiceAudioRef.current && voiceAudioRef.current.paused) voiceAudioRef.current.play().catch(() => {});
        if (bgmAudioRef.current && bgmAudioRef.current.paused) bgmAudioRef.current.play().catch(() => {});
        if (customBgmAudioRef.current && customBgmAudioRef.current.paused) customBgmAudioRef.current.play().catch(() => {});
      }
    } else {
      videoRef.current?.pause();
      voiceAudioRef.current?.pause();
      bgmAudioRef.current?.pause();
      customBgmAudioRef.current?.pause();
    }
  }, [isPlaying, voiceSrc]);

  // Sync seek scrubber time across video and all audio stems
  useEffect(() => {
    if (videoRef.current && Math.abs(videoRef.current.currentTime - currentTime) > 0.15) {
      videoRef.current.currentTime = currentTime;
    }
    if (voiceAudioRef.current && Math.abs(voiceAudioRef.current.currentTime - currentTime) > 0.15) {
      voiceAudioRef.current.currentTime = currentTime;
    }
    if (bgmAudioRef.current && Math.abs(bgmAudioRef.current.currentTime - currentTime) > 0.15) {
      bgmAudioRef.current.currentTime = currentTime;
    }
    if (customBgmAudioRef.current && Math.abs(customBgmAudioRef.current.currentTime - currentTime) > 0.15) {
      customBgmAudioRef.current.currentTime = currentTime;
    }
    syncAudioVolumes(currentTime);
  }, [currentTime, voiceSrc, voiceVol, bgmVol, customBgmVol, origRanges, cues]);

  // High-precision smooth timeline tracking loop (~0.025s / 40fps instead of native 0.3s HTML5 timeupdate)
  useEffect(() => {
    if (!isPlaying) return;
    let animId: number;
    let lastDispatchedTime = -1;

    const tick = () => {
      const v = videoRef.current;
      if (v && !v.paused) {
        const cur = v.currentTime;
        if (Math.abs(cur - lastDispatchedTime) >= 0.025) {
          lastDispatchedTime = cur;
          syncAudioVolumes(cur);
          onTimeUpdateRef.current?.(cur);
        }
      }
      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => {
      if (animId) cancelAnimationFrame(animId);
    };
  }, [isPlaying]);

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const cur = videoRef.current.currentTime;
    syncAudioVolumes(cur);
    onTimeUpdateRef.current?.(cur);
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const vw = videoRef.current.videoWidth || 1920;
      const vh = videoRef.current.videoHeight || 1080;
      setVideoDim({ w: vw, h: vh });
      const dur = videoRef.current.duration;
      if (dur && onDurationChange) {
        onDurationChange(dur);
      }
    }
  };

  const handleDurationChange = () => {
    if (videoRef.current) {
      const dur = videoRef.current.duration;
      if (dur && onDurationChange) {
        onDurationChange(dur);
      }
    }
  };

  // Geometry calculation matching ass.py & video_player.py 1:1
  useEffect(() => {
    const updateGeometry = () => {
      if (!containerRef.current) return;
      const contRect = containerRef.current.getBoundingClientRect();
      const contW = contRect.width;
      const contH = contRect.height;
      if (contW <= 0 || contH <= 0) return;

      let canvasW = contW;
      let canvasH = contH;

      const normAR = (aspectRatio || 'original').toLowerCase();
      let targetAR = videoDim.w / Math.max(1, videoDim.h);

      if (normAR === '9:16') {
        targetAR = 9.0 / 16.0;
      } else if (normAR === '16:9') {
        targetAR = 16.0 / 9.0;
      } else if (normAR === '1:1') {
        targetAR = 1.0;
      } else if (normAR === '4:5') {
        targetAR = 4.0 / 5.0;
      } else if (normAR === '4:3') {
        targetAR = 4.0 / 3.0;
      } else if (normAR.includes(':')) {
        const parts = normAR.split(':');
        const pw = parseFloat(parts[0]);
        const ph = parseFloat(parts[1]);
        if (pw > 0 && ph > 0) targetAR = pw / ph;
      }

      if (normAR === 'original' || normAR === 'gốc') {
        const nativeAR = videoDim.w / Math.max(1, videoDim.h);
        if (contW / contH > nativeAR) {
          canvasH = contH;
          canvasW = contH * nativeAR;
        } else {
          canvasW = contW;
          canvasH = contW / nativeAR;
        }
        setInnerRect({
          left: (contW - canvasW) / 2,
          top: (contH - canvasH) / 2,
          width: canvasW,
          height: canvasH,
          scale: canvasW / Math.max(1, videoDim.w),
        });
        setOuterCanvasRect({
          left: (contW - canvasW) / 2,
          top: (contH - canvasH) / 2,
          width: canvasW,
          height: canvasH,
        });
      } else {
        // Padded canvas aspect ratio mode (9:16, 1:1, etc.)
        if (contW / contH > targetAR) {
          canvasH = contH;
          canvasW = contH * targetAR;
        } else {
          canvasW = contW;
          canvasH = contW / targetAR;
        }
        setOuterCanvasRect({
          left: (contW - canvasW) / 2,
          top: (contH - canvasH) / 2,
          width: canvasW,
          height: canvasH,
        });

        // Inner video sits centered inside the padded canvas
        const videoAR = videoDim.w / Math.max(1, videoDim.h);
        let innerW = canvasW;
        let innerH = canvasH;
        if (targetAR > videoAR) {
          innerW = canvasH * videoAR;
          innerH = canvasH;
        } else {
          innerW = canvasW;
          innerH = canvasW / videoAR;
        }

        const innerLeft = (contW - innerW) / 2;
        const innerTop = (contH - innerH) / 2;

        setInnerRect({
          left: innerLeft,
          top: innerTop,
          width: innerW,
          height: innerH,
          scale: innerW / Math.max(1, videoDim.w),
        });
      }
    };

    updateGeometry();
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
      ro = new ResizeObserver(() => {
        updateGeometry();
      });
      ro.observe(containerRef.current);
    }
    window.addEventListener('resize', updateGeometry);
    return () => {
      if (ro) ro.disconnect();
      window.removeEventListener('resize', updateGeometry);
    };
  }, [aspectRatio, videoDim]);

  // Mouse drag listeners on window for smooth movement
  useEffect(() => {
    if (!dragMode) return;

    const handleMouseMove = (e: MouseEvent) => {
      const { clientX, clientY, startPosY, startWidth } = dragStartRef.current;
      if (innerRect.height <= 0 || innerRect.width <= 0) return;

      if (dragMode === 'move_y') {
        const dy = e.clientY - clientY;
        const dyPct = (dy / innerRect.height) * 100;
        const newPosY = Math.max(5, Math.min(95, startPosY + dyPct));
        onSubtitleStyleChange?.({ pos_y_pct: Math.round(newPosY * 10) / 10 });
      } else if (dragMode === 'resize_left') {
        const dx = clientX - e.clientX; // moving left expands
        const dxPct = (dx / innerRect.width) * 200;
        const newW = Math.max(30, Math.min(98, startWidth + dxPct));
        onSubtitleStyleChange?.({
          box_width_pct: Math.round(newW * 10) / 10,
        });
      } else if (dragMode === 'resize_right') {
        const dx = e.clientX - clientX; // moving right expands
        const dxPct = (dx / innerRect.width) * 200;
        const newW = Math.max(30, Math.min(98, startWidth + dxPct));
        onSubtitleStyleChange?.({
          box_width_pct: Math.round(newW * 10) / 10,
        });
      }
    };

    const handleMouseUp = () => {
      setDragMode(null);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragMode, innerRect, onSubtitleStyleChange]);

  const handleStartDrag = (mode: 'move_y' | 'resize_left' | 'resize_right', e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setDragMode(mode);
    dragStartRef.current = {
      clientX: e.clientX,
      clientY: e.clientY,
      startPosY: posYPct,
      startWidth: boxWidthPct,
    };
  };

  // Color Box Dragging, Resizing & Rotating Effect
  useEffect(() => {
    if (!boxDragMode || activeDragBoxIdx === null || !onUpdateColorBox) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (innerRect.width <= 0 || innerRect.height <= 0) return;
      const { clientX, clientY, startX, startY, startW, startH, startRot, centerPxX, centerPxY } = boxDragStartRef.current;

      if (boxDragMode === 'move') {
        const dx = e.clientX - clientX;
        const dy = e.clientY - clientY;
        const dxPct = (dx / innerRect.width) * 100;
        const dyPct = (dy / innerRect.height) * 100;
        const newX = Math.max(0, Math.min(100 - startW, startX + dxPct));
        const newY = Math.max(0, Math.min(100 - startH, startY + dyPct));
        onUpdateColorBox(activeDragBoxIdx, {
          x: Math.round(newX * 10) / 10,
          y: Math.round(newY * 10) / 10,
        });
      } else if (boxDragMode === 'resize_se') {
        const dx = e.clientX - clientX;
        const dy = e.clientY - clientY;
        const dxPct = (dx / innerRect.width) * 100;
        const dyPct = (dy / innerRect.height) * 100;
        const newW = Math.max(5, Math.min(100 - startX, startW + dxPct));
        const newH = Math.max(2, Math.min(100 - startY, startH + dyPct));
        onUpdateColorBox(activeDragBoxIdx, {
          w: Math.round(newW * 10) / 10,
          h: Math.round(newH * 10) / 10,
        });
      } else if (boxDragMode === 'resize_e') {
        const dx = e.clientX - clientX;
        const dxPct = (dx / innerRect.width) * 100;
        const newW = Math.max(5, Math.min(100 - startX, startW + dxPct));
        onUpdateColorBox(activeDragBoxIdx, {
          w: Math.round(newW * 10) / 10,
        });
      } else if (boxDragMode === 'resize_s') {
        const dy = e.clientY - clientY;
        const dyPct = (dy / innerRect.height) * 100;
        const newH = Math.max(2, Math.min(100 - startY, startH + dyPct));
        onUpdateColorBox(activeDragBoxIdx, {
          h: Math.round(newH * 10) / 10,
        });
      } else if (boxDragMode === 'rotate') {
        const curAngle = Math.atan2(e.clientY - centerPxY, e.clientX - centerPxX) * (180 / Math.PI);
        const startAngle = Math.atan2(clientY - centerPxY, clientX - centerPxX) * (180 / Math.PI);
        let deltaAngle = curAngle - startAngle;
        let newRot = Math.round(startRot + deltaAngle);
        if (Math.abs(newRot) < 3) newRot = 0;
        while (newRot > 180) newRot -= 360;
        while (newRot < -180) newRot += 360;
        onUpdateColorBox(activeDragBoxIdx, {
          rotation: newRot,
        });
      }
    };

    const handleMouseUp = () => {
      setBoxDragMode(null);
      setActiveDragBoxIdx(null);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [boxDragMode, activeDragBoxIdx, innerRect, onUpdateColorBox]);

  const handleStartBoxDrag = (
    idx: number,
    mode: 'move' | 'resize_se' | 'resize_e' | 'resize_s' | 'rotate',
    e: React.MouseEvent,
    box: ColorBoxItem
  ) => {
    e.stopPropagation();
    e.preventDefault();
    onSelectBoxIndex?.(idx);
    setBoxDragMode(mode);
    setActiveDragBoxIdx(idx);

    const boxElem = (e.currentTarget.closest('[data-box-id]') as HTMLElement) || (e.currentTarget as HTMLElement);
    let cx = e.clientX;
    let cy = e.clientY;
    if (boxElem) {
      const r = boxElem.getBoundingClientRect();
      cx = r.left + r.width / 2;
      cy = r.top + r.height / 2;
    }

    boxDragStartRef.current = {
      clientX: e.clientX,
      clientY: e.clientY,
      startX: box.x,
      startY: box.y,
      startW: box.w,
      startH: box.h,
      startRot: box.rotation || 0,
      centerPxX: cx,
      centerPxY: cy,
    };
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    const ms = Math.floor((secs % 1) * 10);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms}`;
  };

  // Typography scale matching Windows GDI and ass.py (scale_v = video_h / 720) 1:1
  const videoScale = Math.max(0.05, innerRect.height / 720.0);
  const computedFontSize = Math.max(6, rawFontSize * videoScale);
  const computedOutlineWidth = Math.max(0.5, outlineWidth * videoScale);
  const computedPadX = Math.max(2, paddingX * videoScale);
  const computedPadY = Math.max(1, paddingY * videoScale);
  const computedBoxRadius = Math.max(0, boxRadius * videoScale);
  const boxBg = hasBox ? hexToRgba(boxColor, boxOpacity) : 'transparent';

  const guideWidthPx = Math.max(60, innerRect.width * (boxWidthPct / 100));

  // Canvas-based crisp vector subtitle rendering matching libass / Windows GDI 1:1
  useEffect(() => {
    if (!canvasRef.current || !activeSubtitle || innerRect.width <= 0) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
    const maxTextW = Math.max(30, guideWidthPx - computedPadX * 2);

    // Measure and wrap words dynamically to fill maxTextW
    ctx.font = `bold ${computedFontSize}px "${fontName}", Arial, sans-serif`;

    const paragraphs = activeSubtitle.split('\n');
    const lines: string[] = [];

    paragraphs.forEach((para) => {
      const words = para.trim().split(/\s+/).filter(Boolean);
      if (words.length === 0) return;
      let curLine = '';
      for (const w of words) {
        const testLine = curLine ? `${curLine} ${w}` : w;
        if (ctx.measureText(testLine).width <= maxTextW) {
          curLine = testLine;
        } else {
          if (curLine) lines.push(curLine);
          curLine = w;
        }
      }
      if (curLine) lines.push(curLine);
    });

    if (lines.length === 0) lines.push('');

    const lineH = computedFontSize * 1.35;
    const totalTextH = lines.length * lineH;
    const totalBoxH = totalTextH + computedPadY * 2;

    setCanvasHeightPx(Math.ceil(totalBoxH));

    canvas.width = Math.ceil(guideWidthPx * dpr);
    canvas.height = Math.ceil(totalBoxH * dpr);
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, guideWidthPx, totalBoxH);

    // CRITICAL: Restore context font immediately after canvas resize (canvas.width resets font to 10px!)
    ctx.font = `bold ${computedFontSize}px "${fontName}", Arial, sans-serif`;

    // Determine background box bounds based on boxMode
    let drawBoxW = guideWidthPx;
    let drawBoxX = 0;

    if (boxMode === 'wrap_text') {
      const maxLineWidth = Math.max(...lines.map((l) => ctx.measureText(l).width));
      const safeExtraPad = Math.max(computedPadX * 2, computedOutlineWidth * 2 + 16);
      drawBoxW = Math.min(guideWidthPx, maxLineWidth + safeExtraPad);
      drawBoxX = (guideWidthPx - drawBoxW) / 2;
    }

    // Draw background rounded box
    if (hasBox) {
      ctx.fillStyle = boxBg;
      ctx.beginPath();
      const r = Math.min(computedBoxRadius, drawBoxW / 2, totalBoxH / 2);
      if (typeof (ctx as any).roundRect === 'function') {
        (ctx as any).roundRect(drawBoxX, 0, drawBoxW, totalBoxH, r);
      } else {
        ctx.rect(drawBoxX, 0, drawBoxW, totalBoxH);
      }
      ctx.fill();
    }

    // Draw text with round vector stroke (behind fill) and crisp fill
    ctx.font = `bold ${computedFontSize}px "${fontName}", Arial, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    const startY = (totalBoxH - totalTextH) / 2 + lineH / 2;
    lines.forEach((line, idx) => {
      const lineY = startY + idx * lineH;
      const lineX = guideWidthPx / 2;

      if (computedOutlineWidth > 0) {
        ctx.lineJoin = 'round';
        ctx.miterLimit = 2;
        ctx.lineWidth = computedOutlineWidth * 2;
        ctx.strokeStyle = outlineColor;
        ctx.strokeText(line, lineX, lineY);
      }

      ctx.fillStyle = primaryColor;
      ctx.fillText(line, lineX, lineY);
    });
  }, [
    activeSubtitle,
    guideWidthPx,
    computedFontSize,
    fontName,
    computedPadX,
    computedPadY,
    computedBoxRadius,
    boxMode,
    hasBox,
    boxBg,
    computedOutlineWidth,
    outlineColor,
    primaryColor,
    innerRect.width,
  ]);

  return (
    <div className="w-full h-full flex-1 flex flex-col min-h-0 bg-[#161619] border border-white/[0.06] rounded-xl overflow-hidden select-none">
      {/* Top Header (Optional when parent doesn't have one) */}
      {!hideHeader && (
        <div className="px-3.5 py-2 border-b border-white/[0.06] flex items-center justify-between shrink-0">
          <span className="text-xs font-medium text-zinc-300">Xem trước</span>
          
          <div className="flex items-center bg-[#1F1F23] rounded p-0.5">
            <button
              onClick={() => onAspectRatioChange?.('original')}
              className={`px-2 py-0.5 text-[11px] rounded transition-all ${
                aspectRatio === 'original' || aspectRatio === '16:9' ? 'bg-[#2E2E33] text-white font-medium shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Gốc
            </button>
            <button
              onClick={() => onAspectRatioChange?.('9:16')}
              className={`px-2 py-0.5 text-[11px] rounded transition-all ${
                aspectRatio === '9:16' ? 'bg-[#2E2E33] text-white font-medium shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              9:16 Shorts
            </button>
          </div>
        </div>
      )}

      {/* Main Video Viewport (Stretches spacious and centered) */}
      <div 
        ref={containerRef}
        className="flex-1 w-full h-full min-h-0 bg-[#0A0A0C] relative flex items-center justify-center p-2 overflow-hidden"
      >
        {/* Aspect Ratio Padded Canvas with User Selected Background Color */}
        {aspectRatio && aspectRatio !== 'original' && aspectRatio !== 'gốc' && (
          <div 
            style={{
              position: 'absolute',
              left: `${outerCanvasRect.left}px`,
              top: `${outerCanvasRect.top}px`,
              width: `${outerCanvasRect.width}px`,
              height: `${outerCanvasRect.height}px`,
              backgroundColor: canvasColor || '#000000',
            }}
            className="shadow-2xl flex items-center justify-center transition-colors pointer-events-none"
          />
        )}

        {/* Inner Video Container with distinct crisp border */}
        <div
          style={{
            position: 'absolute',
            left: `${innerRect.left}px`,
            top: `${innerRect.top}px`,
            width: `${innerRect.width}px`,
            height: `${innerRect.height}px`,
          }}
          className={`relative overflow-hidden bg-black flex items-center justify-center shadow-2xl ${
            aspectRatio && aspectRatio !== 'original' && aspectRatio !== 'gốc'
              ? 'ring-1 ring-white/35 ring-offset-1 ring-offset-black/50'
              : ''
          }`}
        >
          {videoSrc ? (
            <>
              <video
                ref={videoRef}
                src={videoSrc}
                onClick={handleDirectPlayPause}
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleLoadedMetadata}
                onDurationChange={handleDurationChange}
                onEnded={() => {
                  if (videoRef.current) videoRef.current.currentTime = 0;
                  onSeek(0);
                  if (isPlaying) onPlayPauseToggle();
                }}
                playsInline
                className="w-full h-full object-contain cursor-pointer"
              />
              {voiceSrc && (
                <audio
                  ref={voiceAudioRef}
                  src={voiceSrc}
                  preload="auto"
                  onError={() => {
                    setTimeout(() => {
                      if (voiceAudioRef.current) voiceAudioRef.current.load();
                    }, 500);
                  }}
                />
              )}
              {bgmSrc && (
                <audio
                  ref={bgmAudioRef}
                  src={bgmSrc}
                  preload="auto"
                  onError={() => {
                    setTimeout(() => {
                      if (bgmAudioRef.current) bgmAudioRef.current.load();
                    }, 500);
                  }}
                />
              )}
              {customBgmSrc && (
                <audio
                  ref={customBgmAudioRef}
                  src={customBgmSrc}
                  preload="auto"
                  onError={() => {
                    setTimeout(() => {
                      if (customBgmAudioRef.current) customBgmAudioRef.current.load();
                    }, 500);
                  }}
                />
              )}
            </>
          ) : (
            <div className="text-zinc-600 text-xs font-light">
              Chưa có video được nạp
            </div>
          )}

          {/* Color Boxes & Text Overlays (Interactive Direct Manipulation on Preview) */}
          {colorBoxes && colorBoxes.length > 0 && colorBoxes.map((box, idx) => {
            if (box.enabled === false) return null;
            const rot = box.rotation || 0;
            const isSelected = selectedBoxIndex === idx;
            const isDraggingThis = boxDragMode !== null && activeDragBoxIdx === idx;
            const canInteract = Boolean(onUpdateColorBox);

            return (
              <div
                key={box.id || idx}
                data-box-id={box.id || idx}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectBoxIndex?.(idx);
                }}
                onMouseDown={(e) => {
                  if (e.button === 0 && canInteract) {
                    handleStartBoxDrag(idx, 'move', e, box);
                  }
                }}
                style={{
                  position: 'absolute',
                  left: `${box.x}%`,
                  top: `${box.y}%`,
                  width: `${box.w}%`,
                  height: `${box.h}%`,
                  backgroundColor: box.color || '#000000',
                  opacity: box.opacity !== undefined ? box.opacity : 0.85,
                  borderRadius: `${box.radius ?? 6}px`,
                  transform: rot ? `rotate(${rot}deg)` : undefined,
                  transformOrigin: 'center center',
                  zIndex: isSelected ? 35 : 25,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: box.text_align === 'left' ? 'flex-start' : box.text_align === 'right' ? 'flex-end' : 'center',
                  padding: '0 8px',
                  color: box.text_color || '#FFFFFF',
                  fontSize: `${box.font_size || 14}px`,
                  fontFamily: box.font_name || 'Arial, sans-serif',
                  textShadow: box.text_outline_width ? `0 0 ${box.text_outline_width}px ${box.text_outline_color || '#000000'}` : undefined,
                  overflow: isSelected ? 'visible' : 'hidden',
                  cursor: canInteract ? 'move' : 'default',
                  userSelect: 'none',
                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.2,
                }}
                className={`transition-shadow ${
                  isSelected
                    ? 'ring-2 ring-cyan-400 shadow-2xl'
                    : canInteract ? 'hover:ring-1 hover:ring-white/40' : ''
                }`}
                title={canInteract ? 'Nhấp để chọn; Kéo chuột để di chuyển; Kéo góc để đổi kích thước' : undefined}
              >
                <span className="truncate max-w-full pointer-events-none select-none">
                  {box.text || ''}
                </span>

                {/* Direct On-Screen Interactive Handles when Selected */}
                {isSelected && canInteract && (
                  <>
                    {/* Top Rotation Handle */}
                    <div
                      onMouseDown={(e) => handleStartBoxDrag(idx, 'rotate', e, box)}
                      className="absolute -top-7 left-1/2 -translate-x-1/2 w-5 h-5 rounded-full bg-cyan-400 text-black flex items-center justify-center cursor-grab active:cursor-grabbing shadow-lg hover:scale-125 transition-transform z-40"
                      title="Kéo chuột xoay khối tự do"
                    >
                      <span className="text-[11px] font-bold leading-none select-none">↻</span>
                    </div>
                    <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-0.5 h-2 bg-cyan-400/80 pointer-events-none" />

                    {/* Bottom-Right Corner Resize Handle */}
                    <div
                      onMouseDown={(e) => handleStartBoxDrag(idx, 'resize_se', e, box)}
                      className="absolute -bottom-1.5 -right-1.5 w-3.5 h-3.5 rounded-sm bg-cyan-400 border border-white cursor-nwse-resize shadow-md hover:scale-125 transition-transform z-40"
                      title="Kéo để co giãn kích thước khối"
                    />

                    {/* Right Edge Resize Handle */}
                    <div
                      onMouseDown={(e) => handleStartBoxDrag(idx, 'resize_e', e, box)}
                      className="absolute top-1/2 -right-1.5 -translate-y-1/2 w-2 h-4 rounded-sm bg-cyan-400/90 border border-white cursor-ew-resize shadow-sm hover:scale-125 transition-transform z-40"
                      title="Kéo đổi bề rộng"
                    />

                    {/* Bottom Edge Resize Handle */}
                    <div
                      onMouseDown={(e) => handleStartBoxDrag(idx, 'resize_s', e, box)}
                      className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-4 h-2 rounded-sm bg-cyan-400/90 border border-white cursor-ns-resize shadow-sm hover:scale-125 transition-transform z-40"
                      title="Kéo đổi chiều cao"
                    />

                    {/* Live Drag Indicator Tooltip */}
                    {isDraggingThis && (
                      <div className="absolute -top-12 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded bg-black/95 text-cyan-300 text-[10px] pointer-events-none shadow-xl whitespace-nowrap border border-cyan-500/40 font-mono z-50">
                        {boxDragMode === 'rotate'
                          ? `Xoay: ${rot}°`
                          : `X: ${box.x}% | Y: ${box.y}% | ${box.w}% × ${box.h}%`}
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })}

          {/* Logo / Watermark Overlay Preview */}
          {logo && logo.path && (
            <div
              style={{
                position: 'absolute',
                top: logo.position?.includes('bottom') ? undefined : `${logo.margin || 16}px`,
                bottom: logo.position?.includes('bottom') ? `${logo.margin || 16}px` : undefined,
                left: logo.position?.includes('left') ? `${logo.margin || 16}px` : undefined,
                right: logo.position?.includes('left') ? undefined : `${logo.margin || 16}px`,
                maxWidth: `${logo.scale_pct || 15}%`,
                opacity: logo.opacity !== undefined ? logo.opacity : 1.0,
                zIndex: 30,
              }}
              className="pointer-events-none select-none drop-shadow"
            >
              <img
                src={logo.path.startsWith('http') || logo.path.startsWith('/') || logo.path.startsWith('data:') ? logo.path : `/api/local-file?path=${encodeURIComponent(logo.path)}`}
                alt="Logo"
                className="w-full h-auto object-contain"
              />
            </div>
          )}

          {/* Interactive Subtitle Overlay (Draggable vertically & Stretchable horizontally) */}
          {activeSubtitle && (
            <div
              style={{
                position: 'absolute',
                top: `${posYPct}%`,
                left: '50%',
                transform: 'translate(-50%, -50%)',
                width: `${guideWidthPx}px`,
                height: `${canvasHeightPx}px`,
                zIndex: 40,
              }}
              onMouseEnter={() => setIsHovered(true)}
              onMouseLeave={() => {
                if (!dragMode) setIsHovered(false);
              }}
              className="group cursor-grab active:cursor-grabbing"
              title="Nhấp giữ kéo lên/xuống để đổi vị trí Y; kéo 2 cạnh bên để co giãn bề ngang"
            >
              {/* Outer Bounding & Resize Handles when hovered or dragging */}
              <div
                onMouseDown={(e) => {
                  if (e.button !== 0) return;
                  handleStartDrag('move_y', e);
                }}
                className={`relative w-full h-full flex items-center justify-center transition-all ${
                  isHovered || dragMode
                    ? 'ring-1 ring-cyan-400/90 shadow-2xl rounded'
                    : 'ring-0'
                }`}
              >
                {/* Left Grip Handle */}
                {(isHovered || dragMode) && (
                  <div
                    onMouseDown={(e) => {
                      if (e.button !== 0) return;
                      handleStartDrag('resize_left', e);
                    }}
                    className="absolute -left-3 top-1/2 -translate-y-1/2 w-3.5 h-6 rounded bg-white text-zinc-900 shadow-md flex items-center justify-center cursor-col-resize z-50 hover:scale-110 active:scale-95 transition-transform"
                    title="Kéo co giãn bề ngang"
                  >
                    <span className="text-[9px] font-bold leading-none select-none opacity-70">||</span>
                  </div>
                )}

                {/* Subtitle Canvas (Crisp High-DPI Vector Canvas 2D) */}
                <canvas
                  ref={canvasRef}
                  style={{
                    width: `${guideWidthPx}px`,
                    height: `${canvasHeightPx}px`,
                  }}
                  className="pointer-events-none select-none"
                />

                {/* Right Grip Handle */}
                {(isHovered || dragMode) && (
                  <div
                    onMouseDown={(e) => {
                      if (e.button !== 0) return;
                      handleStartDrag('resize_right', e);
                    }}
                    className="absolute -right-3 top-1/2 -translate-y-1/2 w-3.5 h-6 rounded bg-white text-zinc-900 shadow-md flex items-center justify-center cursor-col-resize z-50 hover:scale-110 active:scale-95 transition-transform"
                    title="Kéo co giãn bề ngang"
                  >
                    <span className="text-[9px] font-bold leading-none select-none opacity-70">||</span>
                  </div>
                )}

                {/* Drag Indicator Tooltip */}
                {dragMode && (
                  <div className="absolute -top-7 left-1/2 -translate-x-1/2 px-2.5 py-0.5 rounded bg-black/90 text-cyan-300 text-[11px] pointer-events-none shadow-lg whitespace-nowrap border border-cyan-500/30">
                    Y: {posYPct.toFixed(1)}% | Rộng: {boxWidthPct.toFixed(0)}%
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Playback Controls & Scrubber */}
      <div className="px-4 py-2 bg-[#141416] border-t border-white/[0.06] shrink-0 space-y-1.5">
        {/* Scrubber Progress Bar */}
        <div 
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            handleDirectSeek(pos * (duration || 1));
          }}
          className="w-full bg-[#27272A] h-1.5 rounded-full cursor-pointer relative group"
        >
          <div 
            style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
            className="bg-white h-full rounded-full relative"
          >
            <span className="absolute right-0 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-white opacity-0 group-hover:opacity-100 transition-opacity shadow" />
          </div>
        </div>

        {/* Timecode and Buttons */}
        <div className="flex items-center justify-between">
          <div className="text-[11px] text-zinc-400">
            {formatTime(currentTime)} / {formatTime(duration)}
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => handleDirectSeek(Math.max(0, currentTime - 5))}
              className="w-7 h-7 rounded text-zinc-400 hover:text-white flex items-center justify-center transition-colors"
              title="Lùi 5 giây"
            >
              <IconRewind5 size={14} />
            </button>
            <button
              onClick={handleDirectPlayPause}
              className="w-8 h-8 rounded-full bg-white hover:bg-zinc-200 text-black flex items-center justify-center transition-transform active:scale-95"
              title={isPlaying ? "Tạm dừng" : "Phát"}
            >
              {isPlaying ? <IconPause size={13} /> : <IconPlay size={13} className="ml-0.5" />}
            </button>
            <button
              onClick={() => handleDirectSeek(Math.min(duration, currentTime + 5))}
              className="w-7 h-7 rounded text-zinc-400 hover:text-white flex items-center justify-center transition-colors"
              title="Tới 5 giây"
            >
              <IconForward5 size={14} />
            </button>
          </div>

          <button 
            onClick={() => {
              if (containerRef.current?.requestFullscreen) {
                containerRef.current.requestFullscreen();
              }
            }}
            className="text-zinc-400 hover:text-white p-1"
            title="Toàn màn hình"
          >
            <IconMaximize size={14} />
          </button>
        </div>
      </div>
    </div>
  );
};