import React, { useRef, useState, useLayoutEffect, useEffect } from 'react';
import { createPortal } from 'react-dom';

interface FloatingContextMenuProps {
  x: number;
  y: number;
  triggerKey?: string | number;
  onClose: () => void;
  children: React.ReactNode;
}

export const FloatingContextMenu: React.FC<FloatingContextMenuProps> = ({
  x,
  y,
  triggerKey,
  onClose,
  children,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: x, top: y });

  useLayoutEffect(() => {
    if (!menuRef.current) return;
    const rect = menuRef.current.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const margin = 12;

    // Khởi tạo ngay sát đầu con trỏ chuột (+4px để không đè mũi chuột)
    let nextLeft = x + 4;
    let nextTop = y + 4;

    // Nếu tràn mép phải -> lật sang bên trái con trỏ chuột
    if (nextLeft + rect.width > vw - margin) {
      nextLeft = x - rect.width - 4;
    }
    // Nếu tràn mép dưới -> lật mọc ngược lên phía trên con trỏ chuột
    if (nextTop + rect.height > vh - margin) {
      nextTop = y - rect.height - 4;
    }

    // Kẹp cứng không bao giờ vượt ra ngoài [margin, vw/vh - margin]
    nextLeft = Math.max(margin, Math.min(nextLeft, vw - rect.width - margin));
    nextTop = Math.max(margin, Math.min(nextTop, vh - rect.height - margin));

    setPos({ left: nextLeft, top: nextTop });
  }, [x, y, triggerKey]);

  useEffect(() => {
    const handleGlobalClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleScrollOrResize = () => onClose();

    window.addEventListener('mousedown', handleGlobalClick);
    window.addEventListener('resize', handleScrollOrResize);

    return () => {
      window.removeEventListener('mousedown', handleGlobalClick);
      window.removeEventListener('resize', handleScrollOrResize);
    };
  }, [onClose]);

  return createPortal(
    <div
      ref={menuRef}
      style={{ left: `${pos.left}px`, top: `${pos.top}px` }}
      className="menu-pop fixed z-[99999] bg-[#1A1A1E]/95 border border-white/10 rounded-lg shadow-2xl py-1.5 min-w-[200px] text-xs text-zinc-200 backdrop-blur-md"
      onClick={(e) => e.stopPropagation()}
      onContextMenu={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      {children}
    </div>,
    document.body
  );
};
