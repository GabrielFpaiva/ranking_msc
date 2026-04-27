import { Outlet } from 'react-router-dom';

import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function Layout() {
  return (
    <div className="samid-app">
      <Sidebar />
      <div className="samid-main">
        <TopBar />
        <main className="samid-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
