export interface TurnstileApi {
  render(container: HTMLElement, options: Record<string, unknown>): string;
  reset(widgetId: string): void;
  remove(widgetId: string): void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const SCRIPT_URL = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

let loading: Promise<TurnstileApi> | null = null;

export function loadTurnstile(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  loading ??= new Promise<TurnstileApi>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SCRIPT_URL;
    script.onload = () =>
      window.turnstile ? resolve(window.turnstile) : reject(new Error('Turnstile absent'));
    script.onerror = () => {
      loading = null;
      script.remove();
      reject(new Error('Chargement de Turnstile impossible'));
    };
    document.head.appendChild(script);
  });
  return loading;
}
