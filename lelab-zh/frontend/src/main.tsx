import './i18n' // zh-TW add-on (中文/EN toggle), see I18N.zh-TW.md
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

createRoot(document.getElementById("root")!).render(<App />);
