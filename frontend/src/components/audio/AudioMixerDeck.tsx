import React, { useEffect, useRef } from 'react';
import { IconVolume, IconVolumeMute, IconSliders } from '../icons/StudioIcons';

interface AudioMixerDeckProps {
  viVoiceVol: number;
  bgmVol: number;
  onViVoiceVolChange: (vol: number) => void;
  onBgmVolChange: (vol: number) => void;
  voiceAudioElement?: HTMLAudioElement | null;
  bgmAudioElement?: HTMLAudioElement | null;
  hasCustomBgm?: boolean;
  customBgmVol?: number;
  onCustomBgmVolChange?: (vol: number) => void;
  customBgmAudioElement?: HTMLAudioElement | null;
}

export const AudioMixerDeck: React.FC<AudioMixerDeckProps> = ({
  viVoiceVol,
  bgmVol,
  onViVoiceVolChange,
  onBgmVolChange,
  voiceAudioElement,
  bgmAudioElement,
  hasCustomBgm = false,
  customBgmVol = 50,
  onCustomBgmVolChange,
  customBgmAudioElement: _customBgmAudioElement,
}) => {
  const audioCtxRef = useRef<AudioContext | null>(null);
  const voiceGainRef = useRef<GainNode | null>(null);
  const bgmGainRef = useRef<GainNode | null>(null);
  const limiterRef = useRef<DynamicsCompressorNode | null>(null);

  // Initialize Web Audio Graph with Peak Limiter at end of chain
  useEffect(() => {
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextClass) return;

      const ctx = new AudioContextClass();
      audioCtxRef.current = ctx;

      // 1. Transparent Peak Limiter (Threshold -1.0dB, ratio 20, 1ms attack, 50ms release)
      // Strictly protects against digital clipping without pumping or reverb boosting
      const limiter = ctx.createDynamicsCompressor();
      limiter.threshold.setValueAtTime(-1.0, ctx.currentTime);
      limiter.knee.setValueAtTime(0.0, ctx.currentTime);
      limiter.ratio.setValueAtTime(20.0, ctx.currentTime);
      limiter.attack.setValueAtTime(0.001, ctx.currentTime);
      limiter.release.setValueAtTime(0.05, ctx.currentTime);
      limiter.connect(ctx.destination);
      limiterRef.current = limiter;

      // 2. Voice Stem GainNode
      const vGain = ctx.createGain();
      vGain.connect(limiter);
      voiceGainRef.current = vGain;

      // 3. BGM Stem GainNode
      const bGain = ctx.createGain();
      bGain.connect(limiter);
      bgmGainRef.current = bGain;

      if (voiceAudioElement) {
        const vSource = ctx.createMediaElementSource(voiceAudioElement);
        vSource.connect(vGain);
      }
      if (bgmAudioElement) {
        const bSource = ctx.createMediaElementSource(bgmAudioElement);
        bSource.connect(bGain);
      }
    } catch {
      // Graceful fallback to native HTML5 volume if Web Audio node graph already connected
    }

    return () => {
      if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
        audioCtxRef.current.close().catch(() => {});
      }
    };
  }, [voiceAudioElement, bgmAudioElement]);

  // Update Voice Gain:
  // 0% -> 100%: Pure linear gain (1.0 = 100% original amplitude, zero modification)
  // 101% -> 200%: Linear amplification up to +9.0 dB (approx 2.818x amplitude)
  useEffect(() => {
    let targetGain = viVoiceVol / 100.0;
    if (viVoiceVol > 100) {
      const factor9db = 2.81838;
      targetGain = 1.0 + ((viVoiceVol - 100) / 100.0) * (factor9db - 1.0);
    }

    if (voiceGainRef.current && audioCtxRef.current) {
      voiceGainRef.current.gain.setTargetAtTime(targetGain, audioCtxRef.current.currentTime, 0.015);
    } else if (voiceAudioElement) {
      voiceAudioElement.volume = Math.min(1.0, viVoiceVol / 100.0);
    }
  }, [viVoiceVol, voiceAudioElement]);

  // Update BGM Gain
  useEffect(() => {
    const targetGain = Math.max(0.0, bgmVol / 100.0);
    if (bgmGainRef.current && audioCtxRef.current) {
      bgmGainRef.current.gain.setTargetAtTime(targetGain, audioCtxRef.current.currentTime, 0.015);
    } else if (bgmAudioElement) {
      bgmAudioElement.volume = Math.min(1.0, targetGain);
    }
  }, [bgmVol, bgmAudioElement]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-300">
        <IconSliders size={14} className="text-zinc-400" />
        <span>Hòa âm & Âm lượng</span>
      </div>

      {/* 1. Thuyết minh tiếng Việt (0% - 200%) */}
      <div>
        <div className="flex items-center justify-between text-xs text-zinc-400 mb-1.5">
          <div className="flex items-center gap-1.5">
            {viVoiceVol === 0 ? <IconVolumeMute size={13} /> : <IconVolume size={13} />}
            <span>Giọng thuyết minh</span>
          </div>
          <span className="text-zinc-200">{viVoiceVol}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="200"
          value={viVoiceVol}
          onChange={(e) => onViVoiceVolChange(Number(e.target.value))}
          className="w-full"
        />
        <div className="flex justify-between text-[10px] text-zinc-500 mt-0.5">
          <span>0%</span>
          <span>100% Gốc</span>
          <span>200%</span>
        </div>
      </div>

      {/* 2. Nhạc nền video (BGM) */}
      <div>
        <div className="flex items-center justify-between text-xs text-zinc-400 mb-1.5">
          <div className="flex items-center gap-1.5">
            {bgmVol === 0 ? <IconVolumeMute size={13} /> : <IconVolume size={13} />}
            <span>Nhạc nền (BGM)</span>
          </div>
          <span className="text-zinc-200">{bgmVol}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="200"
          value={bgmVol}
          onChange={(e) => onBgmVolChange(Number(e.target.value))}
          className="w-full"
        />
        <div className="flex justify-between text-[10px] text-zinc-500 mt-0.5">
          <span>0%</span>
          <span>100%</span>
          <span>200%</span>
        </div>
      </div>

      {/* 3. Nhạc nền ngoài đính kèm (Chỉ hiển thị khi có tệp) */}
      {hasCustomBgm && onCustomBgmVolChange && (
        <div className="pt-2 border-t border-white/[0.04] animate-fade-in">
          <div className="flex items-center justify-between text-xs text-zinc-400 mb-1.5">
            <div className="flex items-center gap-1.5">
              {customBgmVol === 0 ? <IconVolumeMute size={13} /> : <IconVolume size={13} className="text-purple-300" />}
              <span className="text-purple-200">Âm lượng nhạc nền ngoài</span>
            </div>
            <span className="text-purple-200 font-semibold">{customBgmVol}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="200"
            value={customBgmVol}
            onChange={(e) => onCustomBgmVolChange(Number(e.target.value))}
            className="w-full accent-purple-400"
          />
          <div className="flex justify-between text-[10px] text-zinc-500 mt-0.5">
            <span>0%</span>
            <span>100%</span>
            <span>200%</span>
          </div>
        </div>
      )}
    </div>
  );
};
