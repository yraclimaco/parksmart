import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import '@fontsource-variable/newsreader';
import '@fontsource-variable/instrument-sans';
import 'maplibre-gl/dist/maplibre-gl.css';
import './index.css';

createRoot(document.getElementById('root')!).render(<App />);
