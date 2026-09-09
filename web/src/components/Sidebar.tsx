import { NavLink, useNavigate } from 'react-router-dom';

import { authStore } from '../store/auth';
import { NavIcon } from './NavIcon';
import type { IconName } from './NavIcon';
import { UsoMini } from './UsoMini';

interface NavGroup {
  label: string;
  items: { to: string; label: string; icon: IconName }[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Análise',
    items: [
      { to: '/inicio', label: 'Início', icon: 'inicio' },
      { to: '/pendencias', label: 'Pendências', icon: 'pendencias' },
    ],
  },
  {
    label: 'Contas',
    items: [
      { to: '/caixa', label: 'Caixa', icon: 'caixa' },
      { to: '/passivos', label: 'Passivos', icon: 'passivos' },
      { to: '/superavit', label: 'Superávit', icon: 'superavit' },
    ],
  },
  {
    label: 'Visões',
    items: [
      { to: '/executivo', label: 'Executivo', icon: 'executivo' },
      { to: '/comparar', label: 'Comparar', icon: 'comparar' },
      { to: '/entregas', label: 'Entregas', icon: 'entregas' },
    ],
  },
  {
    label: 'Referência',
    items: [
      { to: '/regras', label: 'Regras', icon: 'regras' },
      { to: '/execucao', label: 'Execução', icon: 'execucao' },
    ],
  },
];

function userInitials(name: string | null): string {
  if (!name) return 'U';
  return name.slice(0, 2).toUpperCase();
}

interface SidebarProps {
  /** Indica se o drawer mobile está aberto. */
  open?: boolean;
  /** Fecha o drawer mobile (acionado ao navegar ou tocar fora). */
  onClose?: () => void;
}

export function Sidebar({ open = false, onClose }: SidebarProps) {
  const user = authStore.getUser();
  const navigate = useNavigate();

  function handleLogout() {
    authStore.clearToken();
    onClose?.();
    void navigate('/login', { replace: true });
  }

  return (
    <aside className={`samid-sidebar${open ? ' open' : ''}`}>
      <div className="samid-brand">
        <div className="samid-brand-mark" aria-hidden>
          <img src="/brand/brasao-vermelho.png" alt="" />
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
                onClick={onClose}
                className={({ isActive }) =>
                  `samid-nav-item${isActive ? ' active' : ''}`
                }
              >
                <NavIcon name={item.icon} />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="samid-sidebar-footer">
        <UsoMini />
        <div className="samid-user">
          <div className="samid-user-avatar">{userInitials(user)}</div>
          <div>
            <div className="samid-user-name">{user ?? 'Usuário'}</div>
            <div className="samid-user-role">PMJP</div>
          </div>
        </div>
        <button type="button" className="samid-logout" onClick={handleLogout}>
          <NavIcon name="sair" />
          <span>Sair</span>
        </button>
      </div>
    </aside>
  );
}
