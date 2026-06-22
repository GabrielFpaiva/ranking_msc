# F5-19 — Seletor de Competência na TopBar (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar um dropdown de competência na TopBar que troca a competência ativa entre os meses já enviados, fazendo todas as telas refletirem a escolha.

**Architecture:** Mudança contida em `web/src/components/TopBar.tsx`: busca `api.competencias(siconfi)`, renderiza um `<select>` no lugar do chip estático, e no `onChange` chama `store.setCurrent(siconfi, mes)`. As demais telas já re-fetcham via `useEffect([siconfi, competencia])` — nada mais muda.

**Tech Stack:** React + TypeScript (Vite), store de contexto MCRA, fetch via `api` client.

## Global Constraints

- Apenas competência (um ente); `siconfi` permanece rótulo read-only (multi-ente é futuro).
- Sem mudança de backend, de outras telas, nem de assinaturas do store/API.
- Sem runner de teste unitário no frontend → verificação por `npm run lint`/`typecheck`/`build` + checagem manual no navegador.
- Seguir os padrões do arquivo: efeito com flag `cancelled`, classes `samid-*`, `<select className="samid-select">` como no Comparar.
- Rodar comandos a partir de `web/`.

---

## File Structure

- Modify: `web/src/components/TopBar.tsx` — estado `comps`, efeito de busca, render do `<select>`.
- Modify (se necessário no passo de verificação): `web/src/index.css` — pequeno ajuste para o select casar com a faixa da TopBar.

---

### Task 1: Dropdown de competência na TopBar

**Files:**
- Modify: `web/src/components/TopBar.tsx`

**Interfaces:**
- Consumes: `useMCRA()` → `{ siconfi: string | null, competencia: string | null, setCurrent: (s: string, c: string) => void }`; `api.competencias(siconfi: string) => Promise<Competencia[]>` onde `Competencia = { siconfi: string; competencia: string; has_resultado: boolean }`.

- [ ] **Step 1: Adicionar imports e estado**

No topo de `web/src/components/TopBar.tsx`, ajustar o import do React para incluir `useMemo`:

```tsx
import { useEffect, useMemo, useRef, useState } from 'react';
```

Adicionar o import do tipo `Competencia` (junto aos outros imports de topo):

```tsx
import type { Competencia } from '../types';
```

Trocar a desestruturação do store para incluir `setCurrent`:

```tsx
  const { competencia, siconfi, setCurrent } = useMCRA();
```

Adicionar, logo após os `useState` de export, o estado da lista:

```tsx
  const [comps, setComps] = useState<Competencia[]>([]);
```

- [ ] **Step 2: Buscar competências quando há ente ativo**

Adicionar, depois do `useEffect` de cleanup do timer (após a linha `}, []);`), um efeito de busca:

```tsx
  useEffect(() => {
    if (!siconfi) {
      setComps([]);
      return;
    }
    let cancelled = false;
    api
      .competencias(siconfi)
      .then((items) => {
        if (!cancelled) setComps(items);
      })
      .catch(() => {
        if (!cancelled) setComps([]);
      });
    return () => {
      cancelled = true;
    };
  }, [siconfi, competencia]);
```

- [ ] **Step 3: Montar a lista de opções (garante a competência ativa presente)**

Adicionar, antes do `return (`:

```tsx
  const competenciaOptions = useMemo(() => {
    const months = comps.map((item) => item.competencia);
    if (competencia && !months.includes(competencia)) {
      return [competencia, ...months];
    }
    return months;
  }, [comps, competencia]);
```

- [ ] **Step 4: Renderizar o `<select>` no lugar do valor estático**

Substituir o bloco atual:

```tsx
        <div className="samid-competencia">
          <div className="samid-competencia-lbl">
            {siconfi ? `ENTE ${siconfi}` : 'COMPETÊNCIA'}
          </div>
          <div className="samid-competencia-val">{competencia ?? '—'}</div>
        </div>
```

por:

```tsx
        <div className="samid-competencia">
          <div className="samid-competencia-lbl">
            {siconfi ? `ENTE ${siconfi}` : 'COMPETÊNCIA'}
          </div>
          {siconfi && competencia ? (
            <select
              className="samid-select samid-competencia-select"
              aria-label="Trocar competência"
              value={competencia}
              onChange={(e) => setCurrent(siconfi, e.target.value)}
            >
              {competenciaOptions.map((mes) => (
                <option key={mes} value={mes}>
                  {mes}
                </option>
              ))}
            </select>
          ) : (
            <div className="samid-competencia-val">{competencia ?? '—'}</div>
          )}
        </div>
```

- [ ] **Step 5: Verificar typecheck e build**

Run (em `web/`): `npm run lint && npm run typecheck && npm run build`
Expected: tudo verde, sem erros de tipo (o `<select>` controlado por `value={competencia}` é `string`; `setCurrent(siconfi, ...)` recebe `string`).

- [ ] **Step 6: Commit**

```bash
git add web/src/components/TopBar.tsx
git commit -m "F5-19: competência selector dropdown in TopBar"
```

---

### Task 2: Verificação manual + ajuste visual + docs

**Files:**
- Modify (se o select destoar visualmente): `web/src/index.css`
- Modify: `doc/backlog.md`

- [ ] **Step 1: Subir back e front**

```bash
# backend (raiz)
.venv/bin/python -m uvicorn app.api.main:app --reload --port 8000 &
# frontend (web/)
npm run dev
```

- [ ] **Step 2: Validar o fluxo no navegador**

- Logar (`admin` / `admin123`).
- Subir 2+ CSVs de competências diferentes (`ref/amostras/msc_2025-11.csv`, `msc_2025-12.csv`, `msc_2026-01.csv`).
- Confirmar que o dropdown na TopBar lista os meses (mais novo primeiro).
- Trocar o mês no dropdown e confirmar que **Início/Pendências/Caixa/Executivo** atualizam (score/contagens mudam).
- Antes de qualquer upload (estado pós-reset), confirmar que aparece o placeholder "COMPETÊNCIA / —" sem dropdown.

- [ ] **Step 3: Ajustar CSS se necessário**

Se o `<select>` ficar ilegível na faixa da TopBar, adicionar em `web/src/index.css` uma regra `.samid-competencia-select` (fundo claro, texto escuro, borda sutil) coerente com `.samid-select`. Se já ficar legível reusando `.samid-select`, pular este passo.

- [ ] **Step 4: Registrar no backlog**

Em `doc/backlog.md`, na seção de Usabilidade, adicionar:

```markdown
### F5-19 - Seletor de competência na TopBar — CONCLUIDA

Dropdown na TopBar lista as competências enviadas do ente ativo e troca a
competência ativa (`store.setCurrent`), com todas as telas refletindo via
`useEffect([siconfi, competencia])`. Apenas competência (um ente); ente segue
read-only, multi-ente fica para o futuro. So frontend (`web/src/components/TopBar.tsx`).
```

- [ ] **Step 5: Commit**

```bash
git add doc/backlog.md web/src/index.css
git commit -m "F5-19: document competência selector and visual polish"
```

---

## Self-Review

- **Cobertura do spec:** dropdown na TopBar (Task 1), busca por ente + re-busca em upload (Task 1 Step 2), opção sintética p/ competência órfã (Task 1 Step 3), placeholder sem ente (Task 1 Step 4), verificação lint/typecheck/build + manual (Tasks 1.5 e 2). Fora de escopo (ente/Comparar/backend) respeitado.
- **Placeholders:** nenhum — todo o código está nos steps.
- **Consistência de tipos:** `competencia: string | null`; o `<select>` só renderiza quando `competencia` é `string` (guard `siconfi && competencia`), então `value`/`setCurrent` recebem `string`. `Competencia.competencia` é `string`.
