import type { ReactNode } from 'react';

import { useDrawer } from '../store/useDrawer';

interface DrawerProps {
  title: string;
  eyebrow: string;
  children: ReactNode;
  meta?: ReactNode;
}

export function Drawer({ title, eyebrow, children, meta }: DrawerProps) {
  const { close } = useDrawer();

  return (
    <div
      className="samid-drawer-overlay"
      onClick={close}
      role="presentation"
      style={{ WebkitBackdropFilter: 'blur(3px)' }}
    >
      <aside
        className="samid-drawer"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header className="samid-drawer-head">
          <div>
            <div className="samid-eyebrow">{eyebrow}</div>
            <h2 className="samid-drawer-title">{title}</h2>
            {meta && <div className="samid-drawer-meta">{meta}</div>}
          </div>
          <button
            type="button"
            className="samid-icon-btn"
            onClick={close}
            aria-label="Fechar"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>
        <div className="samid-drawer-body">{children}</div>
      </aside>
    </div>
  );
}
