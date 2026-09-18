<script lang="ts">
  import { onMount } from 'svelte';
  import AdminLogin from './components/AdminLogin.svelte';
  import { fetchAdminBookings } from './lib/admin';
  import type { AdminCalendar } from './lib/types';

  let calendar = $state<AdminCalendar | null>(null);
  let connected = $state(false);
  let loadError = $state('');

  async function load() {
    const outcome = await fetchAdminBookings();
    if (outcome.kind === 'ok') {
      calendar = outcome.value;
      connected = true;
      loadError = '';
      return;
    }
    connected = false;
    calendar = null;
    loadError = outcome.kind === 'error' ? outcome.message : '';
  }

  onMount(load);
</script>

<div class="page admin">
  {#if !connected}
    <AdminLogin onconnected={load} />
    {#if loadError}<p class="error" role="alert">{loadError}</p>{/if}
  {:else if calendar}
    <p>Connecté en tant que {calendar.email} — {calendar.sessions.length} mardis au programme.</p>
  {/if}
</div>
