// Gerenciamento de token JWT em localStorage.
// Funções puras — sem estado React — para uso no client.ts e nos hooks.

const _KEY = 'mcra-token';

export const authStore = {
  getToken(): string | null {
    try {
      return window.localStorage.getItem(_KEY);
    } catch {
      return null;
    }
  },

  setToken(token: string): void {
    try {
      window.localStorage.setItem(_KEY, token);
    } catch {
      // localStorage indisponível (ex: modo privado sem storage)
    }
  },

  clearToken(): void {
    try {
      window.localStorage.removeItem(_KEY);
    } catch {
      // ignorado
    }
  },

  isAuthenticated(): boolean {
    return !!this.getToken();
  },
};
