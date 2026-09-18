<script lang="ts">
  import { onMount } from 'svelte';
  import AdminLogin from './components/AdminLogin.svelte';
  import { fetchAdminBookings } from './lib/admin';
  import type { AdminCalendar } from './lib/types';

  let calendar = $state<AdminCalendar | null>(null);
  let connected = $state(false);
  let loadError = $state('');
  // Distingue le premier chargement (pas encore connecté, silencieux) d'un
  // rechargement après une connexion réussie (une session refusée à ce
  // stade doit être signalée, pas passée sous silence).
  let attempted = $state(false);

  async function load() {
    const outcome = await fetchAdminBookings();
    if (outcome.kind === 'ok') {
      calendar = outcome.value;
      connected = true;
      loadError = '';
      attempted = true;
      return;
    }
    connected = false;
    calendar = null;
    if (outcome.kind === 'unauthorized') {
      loadError = attempted ? 'La session n\'a pas pu être ouverte, réessayez.' : '';
    } else {
      loadError = outcome.message;
    }
    attempted = true;
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
