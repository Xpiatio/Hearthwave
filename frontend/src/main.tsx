import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { DisplayApp } from './components/DisplayApp/DisplayApp';
import './index.css';

const isDisplay = window.location.pathname === '/display';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isDisplay ? <DisplayApp /> : <App />}
  </React.StrictMode>,
);
