import React from 'react';
import { LogoDubStudio, IconMinus, IconSquare, IconClose } from './icons/StudioIcons';
import { bridge } from '../api/bridge';

interface TitleBarProps {
  projectTitle?: string;
}

export const TitleBar: React.FC<TitleBarProps> = ({ projectTitle = 'Dự án mới' }) => {
  return (
    <header 
      className="h-9 w-full bg-[#121214] border-b border-white/[0.06] flex items-center justify-between px-3 select-none pywebview-drag-region app-drag shrink-0 z-50 cursor-default"
      onDoubleClick={() => bridge.toggleMaximize()}
    >
      {/* Left: Brand Identity */}
      <div 
        className="flex items-center gap-2 app-no-drag"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <LogoDubStudio size={18} className="text-zinc-200" />
        <span className="font-medium text-xs tracking-wide text-zinc-200">DubStudio</span>
      </div>

      {/* Center: Current Project File Name */}
      <div className="text-xs text-zinc-400 font-normal truncate max-w-sm pointer-events-none">
        {projectTitle}
      </div>

      {/* Right: Window Controls */}
      <div 
        className="flex items-center gap-0.5 app-no-drag"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <button
          onClick={() => bridge.minimize()}
          className="w-7 h-7 rounded hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 flex items-center justify-center transition-colors"
          title="Thu nhỏ"
        >
          <IconMinus size={11} />
        </button>
        <button
          onClick={() => bridge.toggleMaximize()}
          className="w-7 h-7 rounded hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 flex items-center justify-center transition-colors"
          title="Phóng to / Khôi phục"
        >
          <IconSquare size={10} />
        </button>
        <button
          onClick={() => bridge.close()}
          className="w-7 h-7 rounded hover:bg-red-600 text-zinc-400 hover:text-white flex items-center justify-center transition-colors"
          title="Đóng"
        >
          <IconClose size={11} />
        </button>
      </div>
    </header>
  );
};
