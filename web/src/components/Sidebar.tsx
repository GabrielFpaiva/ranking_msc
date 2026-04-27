import { NavLink } from 'react-router-dom';

interface NavGroup {
  label: string;
  items: { to: string; label: string }[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Análise',
    items: [
      { to: '/inicio', label: 'Início' },
      { to: '/execucao', label: 'Execução' },
      { to: '/regras', label: 'Regras' },
      { to: '/pendencias', label: 'Pendências' },
    ],
  },
  {
    label: 'Contas',
    items: [
      { to: '/caixa', label: 'Caixa' },
      { to: '/passivos', label: 'Passivos' },
      { to: '/superavit', label: 'Superávit' },
    ],
  },
  {
    label: 'Visões',
    items: [
      { to: '/executivo', label: 'Executivo' },
      { to: '/comparar', label: 'Comparar' },
      { to: '/ranking', label: 'Ranking' },
    ],
  },
];

export function Sidebar() {
  return (
    <aside className="samid-sidebar">
      <div className="samid-brand">
        <div className="samid-brand-mark" aria-hidden>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect x="3" y="3" width="3" height="14" fill="#C9A449" />
            <rect x="8" y="6" width="3" height="11" fill="#C9A449" />
            <rect x="13" y="9" width="3" height="8" fill="#C9A449" />
          </svg>
        </div>
        <div>
          <div className="samid-brand-wm">MCRA</div>
          <div className="samid-brand-sub">PMJP · MSC</div>
        </div>
      </div>

      <nav>
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <div className="samid-nav-section">{group.label}</div>
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `samid-nav-item${isActive ? ' active' : ''}`
                }
              >
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="samid-sidebar-footer">
        <div className="samid-user">
          <div className="samid-user-avatar">PM</div>
          <div>
            <div className="samid-user-name">Controladoria</div>
            <div className="samid-user-role">PMJP</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
