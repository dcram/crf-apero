import '@fontsource/cormorant-garamond/500-italic.css';
import '@fontsource/cormorant-garamond/600.css';
import '@fontsource/source-sans-3/400.css';
import '@fontsource/source-sans-3/600.css';
import './app.css';
import { mount } from 'svelte';
import App from './App.svelte';

const app = mount(App, { target: document.getElementById('app')! });

export default app;
