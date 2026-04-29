import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import { App } from './App';
import { DrawerProvider } from './store/drawer';
import { MCRAProvider } from './store/mcra';
import './styles/globals.css';

const rootElement = document.getElementById('root');
if (!rootElement) throw new Error('Root container #root not found in index.html');

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <MCRAProvider>
        <DrawerProvider>
          <App />
        </DrawerProvider>
      </MCRAProvider>
    </BrowserRouter>
  </StrictMode>,
);
