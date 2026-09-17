<script lang="ts">
  import { onMount } from 'svelte';
  import { loadTurnstile } from '../lib/turnstile';

  let { siteKey, ontoken }: { siteKey: string; ontoken: (token: string) => void } = $props();

  let container: HTMLDivElement;
  let widgetId: string | undefined;
  let failed = $state(false);

  export function reset() {
    ontoken('');
    if (widgetId !== undefined) window.turnstile?.reset(widgetId);
  }

  onMount(() => {
    let cancelled = false;
    loadTurnstile()
      .then((turnstile) => {
        if (cancelled) return;
        widgetId = turnstile.render(container, {
          sitekey: siteKey,
          language: 'fr',
          callback: (token: string) => ontoken(token),
          'expired-callback': () => ontoken(''),
          'error-callback': () => ontoken(''),
        });
      })
      .catch(() => {
        failed = true;
      });
    return () => {
      cancelled = true;
      if (widgetId !== undefined) window.turnstile?.remove(widgetId);
    };
  });
</script>

<div bind:this={container}></div>
{#if failed}
  <p class="form-error" role="alert">
    La vérification anti-robot n'a pas pu se charger. Vérifiez votre connexion puis rechargez la
    page.
  </p>
{/if}
