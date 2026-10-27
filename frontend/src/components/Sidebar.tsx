import React from 'react';
import { 
  IconFolder, IconMic, IconFilm, 
  IconRefresh, IconInfo, IconSettings,
  IconScissors 
} from './icons/StudioIcons';

export type NavTab = 'projects' | 'studio' | 'editor' | 'tools' | 'updates' | 'tutorial' | 'settings';

interface SidebarProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange }) => {
  const topNavItems = [
    { id: 'projects' as NavTab, label: 'Dự án', icon: IconFolder },
    { id: 'studio' as NavTab, label: 'Lồng tiếng', icon: IconMic },
    { id: 'editor' as NavTab, label: 'Chỉnh sửa và xuất', icon: IconFilm },
    { id: 'tools' as NavTab, label: 'Công cụ khác', icon: IconScissors },
  ];

  const bottomNavItems = [
    { id: 'updates' as NavTab, label: 'Kiểm tra cập nhật', icon: IconRefresh },
    { id: 'tutorial' as NavTab, label: 'Hướng dẫn', icon: IconInfo },
    { id: 'settings' as NavTab, label: 'Cài đặt', icon: IconSettings },
  ];

  return (
    <aside className="w-52 bg-[#161618] border-r border-white/[0.06] flex flex-col justify-between shrink-0 select-none py-3">
      {/* 1. Top Navigation Group: Dự án -> Lồng tiếng -> Chỉnh sửa và xuất */}
      <div className="space-y-1 px-2.5">
        <div className="px-3 py-1 text-[10px] font-semibold tracking-wider text-zinc-500 uppercase">
          Điều hướng
        </div>
        <nav className="space-y-0.5">
          {topNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-md text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-[#222226] text-white font-semibold shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]'
                }`}
              >
                <Icon size={16} className={isActive ? 'text-white' : 'text-zinc-400'} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* 2. Bottom Navigation Group: Kiểm tra cập nhật -> Hướng dẫn -> Cài đặt */}
      <div className="space-y-1 px-2.5 pt-3 border-t border-white/[0.06]">
        <div className="px-3 py-1 text-[10px] font-semibold tracking-wider text-zinc-500 uppercase">
          Hệ thống
        </div>
        <nav className="space-y-0.5">
          {bottomNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-[#222226] text-white font-semibold'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]'
                }`}
              >
                <Icon size={15} className={isActive ? 'text-white' : 'text-zinc-400'} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Subtle version indicator */}
        <div className="px-3 pt-2 text-[10px] text-zinc-600 font-normal">
          DubStudio v2.0.0 Stable
        </div>
      </div>
    </aside>
  );
};
