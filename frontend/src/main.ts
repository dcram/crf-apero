import '@fontsource/cormorant-garamond/500-italic.css';
import '@fontsource/cormorant-garamond/600.css';
import '@fontsource/source-sans-3/400.css';
import '@fontsource/source-sans-3/600.css';
import './app.css';
import { mount } from 'svelte';
import App from './App.svelte';
import Admin from './Admin.svelte';

// Deux pages seulement : un routeur serait disproportionné.
const root = window.location.pathname.replace(/\/$/, '') === '/admin' ? Admin : App;

const app = mount(root, { target: document.getElementById('app')! });

export default app;
