import { Navigate, Route, Routes } from 'react-router-dom';

import { Layout } from './components/Layout';
import { Caixa } from './screens/Caixa';
import { Comparar } from './screens/Comparar';
import { Execucao } from './screens/Execucao';
import { Executivo } from './screens/Executivo';
import { Home } from './screens/Home';
import { Passivos } from './screens/Passivos';
import { Pendencias } from './screens/Pendencias';
import { Regras } from './screens/Regras';
import { Superavit } from './screens/Superavit';

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
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
        <Route path="*" element={<Navigate to="/inicio" replace />} />
      </Route>
    </Routes>
  );
}
