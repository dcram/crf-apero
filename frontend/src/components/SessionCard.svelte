<script lang="ts">
  import { formatTuesday } from '../lib/dates';
  import type { SessionItem } from '../lib/types';

  let { session, onpick }: { session: SessionItem; onpick: () => void } = $props();

  const label = $derived(formatTuesday(session.date));
</script>

<article class="card" class:taken={!session.available}>
  <p class="date">{label}</p>
  <p class="theme">{session.theme}</p>
  {#if session.available}
    <button type="button" class="primary" onclick={onpick} aria-label="Je m'en charge : {label}">
      Je m'en charge
    </button>
  {:else}
    <p class="badge">Pris</p>
  {/if}
</article>
