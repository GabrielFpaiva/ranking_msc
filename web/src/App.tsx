import type { ReactElement } from 'react';

import { Navigate, Route, Routes } from 'react-router-dom';

import { Layout } from './components/Layout';
import { Ajuda } from './screens/Ajuda';
import { Caixa } from './screens/Caixa';
import { Comparar } from './screens/Comparar';
import { Convidar } from './screens/Convidar';
import { TrocarSenha } from './screens/TrocarSenha';
import Entregas from './screens/Entregas';
import { Execucao } from './screens/Execucao';
import { Executivo } from './screens/Executivo';
import { Home } from './screens/Home';
import { Login } from './screens/Login';
import { MeuTempo } from './screens/MeuTempo';
import { Passivos } from './screens/Passivos';
import { Pendencias } from './screens/Pendencias';
import { Regras } from './screens/Regras';
import { Superavit } from './screens/Superavit';
import { authStore } from './store/auth';

function ProtectedRoute({ children }: { children: ReactElement }): ReactElement {
  if (!authStore.isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/ajuda" element={<Ajuda />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/inicio" replace />} />
        <Route path="inicio" element={<Home />} />
        <Route path="executivo" element={<Executivo />} />
        <Route path="execucao" element={<Execucao />} />
        <Route path="regras" element={<Regras />} />
        <Route path="pendencias" element={<Pendencias />} />
        <Route path="caixa" element={<Caixa />} />
        <Route path="passivos" element={<Passivos />} />
        <Route path="superavit" element={<Superavit />} />
        <Route path="comparar" element={<Comparar />} />
        <Route path="entregas" element={<Entregas />} />
        <Route path="uso" element={<MeuTempo />} />
        <Route path="convidar" element={<Convidar />} />
        <Route path="senha" element={<TrocarSenha />} />
        <Route path="*" element={<Navigate to="/inicio" replace />} />
      </Route>
    </Routes>
  );
}
