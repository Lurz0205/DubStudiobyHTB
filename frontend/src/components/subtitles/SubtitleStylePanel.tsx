import React, { useState } from 'react';
import { SubtitleStyle } from '../video/WYSIWYGPlayer';

interface SubtitleStylePanelProps {
  style: SubtitleStyle;
  onChange: (updated: Partial<SubtitleStyle>) => void;
}

const FONT_OPTIONS = [
  'Arial',
  'Segoe UI',
  'Tahoma',
  'Calibri',
  'Verdana',
  'Times New Roman',
];

export const SubtitleStylePanel: React.FC<SubtitleStylePanelProps> = ({
  style,
  onChange,
}) => {
  const fontName = style.font_name || 'Arial';
  const fontSize = style.fontSize || style.font_size || 26;
  const primaryColor = style.primary_color || '#FFFFFF';
  const outlineColor = style.outline_color || '#000000';
  const outlineWidth = style.outline_width !== undefined ? style.outline_width : 2;
  const hasBox = style.has_box !== undefined ? style.has_box : true;
  const boxColor = style.box_color || '#000000';
  const boxOpacity = style.box_opacity !== undefined ? style.box_opacity : 0.6;
  const boxRadius = style.box_radius !== undefined ? style.box_radius : 6;
  const boxMode = style.box_mode || 'full_width';
  const boxWidthPct = style.box_width_pct !== undefined ? style.box_width_pct : 85;

  // Recent 4 text colors history
  const [recentTextColors, setRecentTextColors] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem('dubstudio_recent_text_colors');
      if (stored) return JSON.parse(stored);
    } catch {}
    return ['#FFFFFF', '#FDE047', '#38BDF8', '#4ADE80'];
  });

  const handleSelectTextColor = (hex: string) => {
    onChange({ primary_color: hex });
    setRecentTextColors((prev) => {
      const filtered = prev.filter((c) => c.toLowerCase() !== hex.toLowerCase());
      const next = [hex, ...filtered].slice(0, 4);
      try {
        localStorage.setItem('dubstudio_recent_text_colors', JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  // Recent 4 box colors history
  const [recentBoxColors, setRecentBoxColors] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem('dubstudio_recent_box_colors');
      if (stored) return JSON.parse(stored);
    } catch {}
    return ['#000000', '#1E293B', '#1E1B4B', '#3F3F46'];
  });

  const handleSelectBoxColor = (hex: string) => {
    onChange({ box_color: hex });
    setRecentBoxColors((prev) => {
      const filtered = prev.filter((c) => c.toLowerCase() !== hex.toLowerCase());
      const next = [hex, ...filtered].slice(0, 4);
      try {
        localStorage.setItem('dubstudio_recent_box_colors', JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  let posYPct = 86.0;
  if (style.pos_y_pct !== undefined) {
    posYPct = style.pos_y_pct;
  } else if (style.marginV !== undefined || style.margin_v !== undefined) {
    const mv = style.marginV || style.margin_v || 35;
    posYPct = Math.max(5, Math.min(95, 100 - (mv / 720) * 100));
  }

  return (
    <div className="space-y-4 text-xs select-none">
      {/* 1. Phông chữ */}
      <div>
        <label className="block text-[11px] font-medium text-zinc-400 mb-1">
          Phông chữ (Font)
        </label>
        <select
          value={fontName}
          onChange={(e) => onChange({ font_name: e.target.value })}
          className="w-full bg-[#1A1A1E] border border-white/10 rounded px-2.5 py-1.5 text-zinc-200 focus:outline-none focus:border-zinc-500 cursor-pointer"
        >
          {FONT_OPTIONS.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
      </div>

      {/* 2. Cỡ chữ */}
      <div>
        <div className="flex items-center justify-between text-[11px] text-zinc-400 mb-1">
          <span>Cỡ chữ</span>
          <span className="text-zinc-200">{fontSize} px</span>
        </div>
        <input
          type="range"
          min="14"
          max="48"
          value={fontSize}
          onChange={(e) => {
            const v = Number(e.target.value);
            onChange({ fontSize: v, font_size: v });
          }}
          className="w-full accent-white cursor-pointer"
        />
      </div>

      {/* 3. Màu chữ */}
      <div>
        <div className="flex items-center justify-between text-[11px] text-zinc-400 mb-1.5">
          <span>Màu chữ</span>
          <span className="text-zinc-300 uppercase">{primaryColor}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {recentTextColors.map((hex) => (
            <button
              key={hex}
              onClick={() => handleSelectTextColor(hex)}
              style={{ backgroundColor: hex }}
              className={`w-6 h-6 rounded-full border transition-transform ${
                primaryColor.toLowerCase() === hex.toLowerCase()
                  ? 'border-white scale-110 shadow'
                  : 'border-white/20 hover:scale-105'
              }`}
              title={hex}
            />
          ))}
          <input
            type="color"
            value={primaryColor}
            onChange={(e) => handleSelectTextColor(e.target.value)}
            className="w-6 h-6 rounded border border-white/20 bg-transparent cursor-pointer p-0"
            title="Tùy chọn màu"
          />
        </div>
      </div>

      {/* 4. Viền chữ (Outline) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-[11px] text-zinc-400">
          <span>Độ dày viền chữ</span>
          <span className="text-zinc-200">{outlineWidth} px</span>
        </div>
        <input
          type="range"
          min="0"
          max="6"
          value={outlineWidth}
          onChange={(e) => onChange({ outline_width: Number(e.target.value) })}
          className="w-full accent-white cursor-pointer"
        />

        <div className="flex items-center justify-between text-[11px] text-zinc-400 pt-1">
          <span>Màu viền</span>
          <div className="flex items-center gap-1.5">
            {[
              { label: 'Đen', hex: '#000000' },
              { label: 'Xám', hex: '#374151' },
              { label: 'Trắng', hex: '#FFFFFF' },
            ].map((c) => (
              <button
                key={c.hex}
                onClick={() => onChange({ outline_color: c.hex })}
                style={{ backgroundColor: c.hex }}
                className={`w-5 h-5 rounded-full border transition-transform ${
                  outlineColor.toLowerCase() === c.hex.toLowerCase()
                    ? 'border-white scale-110 shadow'
                    : 'border-white/20 hover:scale-105'
                }`}
                title={c.label}
              />
            ))}
            <input
              type="color"
              value={outlineColor}
              onChange={(e) => onChange({ outline_color: e.target.value })}
              className="w-5 h-5 rounded border border-white/20 bg-transparent cursor-pointer p-0"
              title="Chọn màu viền"
            />
          </div>
        </div>
      </div>

      {/* 5. Vị trí độ cao & Bề ngang tối đa */}
      <div className="pt-2 border-t border-white/[0.06] space-y-3">
        {/* Vị trí Y (Độ cao) */}
        <div>
          <div className="flex items-center justify-between text-[11px] text-zinc-300 mb-1">
            <span className="font-medium">Vị trí độ cao Y</span>
            <span className="text-cyan-300">{posYPct.toFixed(1)}%</span>
          </div>
          <input
            type="range"
            min="5"
            max="95"
            step="0.5"
            value={posYPct}
            onChange={(e) => {
              const v = Number(e.target.value);
              const mv = Math.round(((100 - v) / 100) * 720);
              onChange({ pos_y_pct: v, marginV: mv, margin_v: mv });
            }}
            className="w-full accent-cyan-400 cursor-pointer"
          />
          <p className="text-[10px] text-zinc-500 mt-0.5">
            Mẹo: Có thể nhấp giữ kéo trực tiếp hộp phụ đề trên màn hình Preview.
          </p>
        </div>

        {/* Độ rộng tối đa (Max Width) */}
        {/* Độ rộng bề ngang */}
        <div>
          <div className="flex items-center justify-between text-[11px] text-zinc-300 mb-1">
            <span className="font-medium">
              {boxMode === 'full_width' ? 'Bề ngang hộp phụ đề' : 'Giới hạn dòng tối đa'}
            </span>
            <span className="text-cyan-300">{boxWidthPct.toFixed(0)}%</span>
          </div>
          <input
            type="range"
            min="30"
            max="98"
            step="1"
            value={boxWidthPct}
            onChange={(e) => {
              const val = Number(e.target.value);
              onChange({ box_width_pct: val, box_mode: 'full_width' });
            }}
            className="w-full accent-cyan-400 cursor-pointer"
          />
          <p className="text-[10px] text-zinc-500 mt-0.5">
            Mẹo: Kéo 2 tay nắm (||) ở hai cạnh bên phụ đề trên Preview để co giãn trực tiếp.
          </p>
        </div>
      </div>

      {/* 6. Khung nền phụ đề (Background Box) */}
      <div className="pt-2 border-t border-white/[0.06] space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium text-zinc-300">
            Hộp nền phụ đề
          </span>
          <input
            type="checkbox"
            checked={hasBox}
            onChange={(e) => onChange({ has_box: e.target.checked })}
            className="rounded bg-[#26262B] border-white/10 text-white focus:ring-0 cursor-pointer"
          />
        </div>

        {hasBox && (
          <div className="space-y-3 pl-1">
            {/* Chế độ hộp */}
            <div className="grid grid-cols-2 gap-1.5 bg-[#1F1F23] p-0.5 rounded">
              <button
                type="button"
                onClick={() => onChange({ box_mode: 'wrap_text' })}
                className={`py-1 text-[11px] rounded transition-all ${
                  boxMode === 'wrap_text'
                    ? 'bg-[#2E2E33] text-white font-medium'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Ôm sát chữ
              </button>
              <button
                type="button"
                onClick={() => onChange({ box_mode: 'full_width' })}
                className={`py-1 text-[11px] rounded transition-all ${
                  boxMode === 'full_width'
                    ? 'bg-[#2E2E33] text-white font-medium'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Tràn viền ngang
              </button>
            </div>

            {/* Màu nền hộp */}
            <div>
              <div className="flex items-center justify-between text-[11px] text-zinc-400 mb-1.5">
                <span>Màu nền hộp</span>
                <span className="text-zinc-300 uppercase">{boxColor}</span>
              </div>
              <div className="flex items-center gap-1.5">
                {recentBoxColors.map((hex) => (
                  <button
                    key={hex}
                    onClick={() => handleSelectBoxColor(hex)}
                    style={{ backgroundColor: hex }}
                    className={`w-6 h-6 rounded border transition-transform ${
                      boxColor.toLowerCase() === hex.toLowerCase()
                        ? 'border-white scale-110 shadow'
                        : 'border-white/20 hover:scale-105'
                    }`}
                    title={hex}
                  />
                ))}
                <input
                  type="color"
                  value={boxColor}
                  onChange={(e) => handleSelectBoxColor(e.target.value)}
                  className="w-6 h-6 rounded border border-white/20 bg-transparent cursor-pointer p-0"
                  title="Chọn màu hộp"
                />
              </div>
            </div>

            {/* Độ trong suốt nền */}
            <div>
              <div className="flex items-center justify-between text-[11px] text-zinc-400 mb-1">
                <span>Độ đậm đục (Opacity)</span>
                <span className="text-zinc-200">{Math.round(boxOpacity * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={Math.round(boxOpacity * 100)}
                onChange={(e) => onChange({ box_opacity: Number(e.target.value) / 100 })}
                className="w-full accent-white cursor-pointer"
              />
            </div>

            {/* Bo góc hộp */}
            <div>
              <div className="flex items-center justify-between text-[11px] text-zinc-400 mb-1">
                <span>Bo góc</span>
                <span className="text-zinc-200">{boxRadius} px</span>
              </div>
              <input
                type="range"
                min="0"
                max="20"
                value={boxRadius}
                onChange={(e) => onChange({ box_radius: Number(e.target.value) })}
                className="w-full accent-white cursor-pointer"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};