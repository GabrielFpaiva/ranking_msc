import { useEffect, useState } from 'react';

import { Outlet, useLocation } from 'react-router-dom';

import { DrawerHost } from './DrawerHost';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function Layout() {
  const { pathname } = useLocation();
  const [navOpen, setNavOpen] = useState(false);

  // Fecha o drawer mobile sempre que a rota muda.
  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  return (
    <div className="samid-app">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      {navOpen && (
        <button
          type="button"
          className="samid-nav-backdrop"
          aria-label="Fechar menu"
          onClick={() => setNavOpen(false)}
        />
      )}
      <div className="samid-main">
        <TopBar onMenuToggle={() => setNavOpen((prev) => !prev)} />
        <main className="samid-content">
          <Outlet />
        </main>
      </div>
      <DrawerHost />
    </div>
  );
}
