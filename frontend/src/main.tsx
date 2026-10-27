import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './index.css';

// Self-Healing CSS Watchdog: Guarantees styles are applied even on cold start race conditions
(function initCssWatchdog() {
  function verifyStyles() {
    try {
      const bodyBg = window.getComputedStyle(document.body).backgroundColor;
      const isDarkMode = bodyBg.includes('18, 18, 20') || bodyBg.includes('18,18,20');
      const inlineStyle = document.getElementById('dubstudio-core-css');
      if (!isDarkMode && !inlineStyle) {
        console.warn('[CSS Watchdog] Dark mode background not detected, attempting self-healing CSS injection...');
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = `/assets/index.css?t=${Date.now()}`;
        document.head.appendChild(link);
      }
    } catch (e) {
      console.error('[CSS Watchdog] Error checking style:', e);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', verifyStyles);
  } else {
    verifyStyles();
  }
  setTimeout(verifyStyles, 100);
})();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

