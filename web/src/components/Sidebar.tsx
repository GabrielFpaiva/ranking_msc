import { useEffect, useState } from 'react';

import { NavLink, useNavigate } from 'react-router-dom';

import { api } from '../api/client';
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
  {
    label: 'Ajuda',
    items: [{ to: '/ajuda', label: 'Ajuda', icon: 'ajuda' }],
  },
];

// Só aparece para quem `GET /api/invites/capability` diz que pode convidar;
// para os demais o menu fica idêntico ao de antes. Entra antes do grupo Ajuda.
const GRUPO_CONVITES: NavGroup = {
  label: 'Administração',
  items: [{ to: '/convidar', label: 'Convidar', icon: 'convidar' }],
};

function userInitials(name: string | null): string {
  if (!name) return 'U';
  return name.slice(0, 2).toUpperCase();
}

interface SidebarProps {
  onBeforeLogout?: () => void;
  /** Indica se o drawer mobile está aberto. */
  open?: boolean;
  /** Fecha o drawer mobile (acionado ao navegar ou tocar fora). */
  onClose?: () => void;
}

export function Sidebar({ open = false, onClose, onBeforeLogout }: SidebarProps) {
  const user = authStore.getUser();
  const navigate = useNavigate();
  const [podeConvidar, setPodeConvidar] = useState(false);

  useEffect(() => {
    let cancelado = false;
    api
      .inviteCapability()
      .then((pode) => {
        if (!cancelado) setPodeConvidar(pode);
      })
      .catch(() => {
        // Falha na consulta (API antiga, rede): sem o item, como para todos os outros.
      });
    return () => {
      cancelado = true;
    };
  }, []);

  const grupos = podeConvidar
    ? [...NAV_GROUPS.slice(0, -1), GRUPO_CONVITES, ...NAV_GROUPS.slice(-1)]
    : NAV_GROUPS;

  function handleLogout() {
    onBeforeLogout?.();
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
        {grupos.map((group) => (
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
        <NavLink to="/senha" onClick={onClose} className="samid-trocar-senha">
          Trocar senha
        </NavLink>
        <button type="button" className="samid-logout" onClick={handleLogout}>
          <NavIcon name="sair" />
          <span>Sair</span>
        </button>
      </div>
    </aside>
  );
}
