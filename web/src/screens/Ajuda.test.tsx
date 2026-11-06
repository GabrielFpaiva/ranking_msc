// Testes da tela /ajuda — acordeão do FAQ, GIF só nas perguntas que têm e
// acesso sem login (a tela não depende da API).

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import faq from '../ajuda/faq.json';
import { App } from '../App';
import { authStore } from '../store/auth';
import { Ajuda } from './Ajuda';

function renderAjuda() {
  return render(
    <MemoryRouter initialEntries={['/ajuda']}>
      <Ajuda />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  authStore.clearToken();
});

describe('Ajuda', () => {
  it('renderiza as 12 perguntas do faq.json', () => {
    renderAjuda();

    const botoes = screen.getAllByRole('button', { expanded: false });
    expect(botoes.map((b) => b.textContent)).toEqual(faq.map((f) => f.pergunta));
    expect(botoes).toHaveLength(12);
  });

  it('abrir pergunta com gif mostra a imagem', async () => {
    const user = userEvent.setup();
    renderAjuda();

    await user.click(screen.getByRole('button', { name: 'Como faço login e saio?' }));

    const img = screen.getByRole('img');
    expect(img.getAttribute('src')).toBe('/ajuda/login.gif');
    expect(img.getAttribute('loading')).toBe('lazy');
    expect(screen.getByText(faq[0].passos[0])).toBeTruthy();
  });

  it('pergunta sem gif nao mostra imagem', async () => {
    const user = userEvent.setup();
    renderAjuda();

    await user.click(screen.getByRole('button', { name: 'Esqueci a senha, e agora?' }));

    expect(screen.getByText(faq[10].passos[0])).toBeTruthy();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('abre uma pergunta por vez', async () => {
    const user = userEvent.setup();
    renderAjuda();

    await user.click(screen.getByRole('button', { name: 'Como faço login e saio?' }));
    await user.click(screen.getByRole('button', { name: 'Como envio a MSC do mês?' }));

    expect(screen.queryByText(faq[0].passos[0])).toBeNull();
    expect(screen.getByText(faq[1].passos[0])).toBeTruthy();
  });

  it('voltar leva para o login quando nao ha sessao', () => {
    renderAjuda();

    expect(screen.getByRole('link', { name: /Voltar/ }).getAttribute('href')).toBe('/login');
  });

  it('voltar leva para o inicio quando ha sessao', () => {
    vi.spyOn(authStore, 'isAuthenticated').mockReturnValue(true);
    renderAjuda();

    expect(screen.getByRole('link', { name: /Voltar/ }).getAttribute('href')).toBe('/inicio');
  });

  it('ajuda abre sem login', () => {
    render(
      <MemoryRouter initialEntries={['/ajuda']}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole('button', { name: faq[0].pergunta })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Entrar' })).toBeNull();
  });
});
