import React from 'react';
import ReactDOM from 'react-dom/client';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './context/ToastContext';
import { ConversationProvider } from './context/ConversationContext';
import App from './App';
import './App.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider>
      <ToastProvider>
        <ConversationProvider>
          <App />
        </ConversationProvider>
      </ToastProvider>
    </ThemeProvider>
  </React.StrictMode>
);
