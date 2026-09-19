<script lang="ts">
  import { onMount } from 'svelte';
  import AdminBookingForm from './components/AdminBookingForm.svelte';
  import AdminLogin from './components/AdminLogin.svelte';
  import { closeSession, deleteBooking, fetchAdminBookings } from './lib/admin';
  import { formatTuesday, groupByMonth } from './lib/dates';
  import type { AdminCalendar, AdminSessionItem } from './lib/types';

  let calendar = $state<AdminCalendar | null>(null);
  let connected = $state(false);
  let loadError = $state('');
  let editing = $state<AdminSessionItem | null>(null);
  // Distingue le premier chargement (pas encore connecté, silencieux) d'un
  // rechargement après une connexion réussie (une session refusée à ce
  // stade doit être signalée, pas passée sous silence).
  let attempted = $state(false);
  // Une session déjà établie qui échoue à se recharger a expiré ; une
  // tentative de connexion qui échoue vient juste d'être refusée. Les deux
  // cas passent par la même branche `unauthorized` de load() mais méritent
  // des messages différents.
  let hadSession = $state(false);

  const groups = $derived(calendar ? groupByMonth(calendar.sessions) : []);

  async function load() {
    const outcome = await fetchAdminBookings();
    if (outcome.kind === 'ok') {
      calendar = outcome.value;
      connected = true;
      loadError = '';
      attempted = true;
      hadSession = true;
      return;
    }
    connected = false;
    calendar = null;
    if (outcome.kind === 'unauthorized') {
      if (!attempted) {
        loadError = '';
      } else if (hadSession) {
        loadError = 'Votre session a expiré, reconnectez-vous.';
      } else {
        loadError = 'La connexion a échoué, réessayez.';
      }
    } else {
      loadError = outcome.message;
    }
    attempted = true;
    hadSession = false;
  }

  async function remove(date: string, name: string) {
    if (!confirm(`Supprimer la réservation de ${name} pour le ${formatTuesday(date)} ?`)) return;
    const outcome = await deleteBooking(date);
    if (outcome.kind === 'error') {
      loadError = outcome.message;
      return;
    }
    await load();
  }

  async function logout() {
    await closeSession();
    // Déconnexion volontaire et réussie : le prochain rechargement échouera
    // forcément (plus de session), mais il ne faut rien signaler.
    attempted = false;
    await load();
  }

  function saved() {
    editing = null;
    load();
  }

  function sessionLost() {
    editing = null;
    load();
  }

  onMount(load);
</script>

<div class="page admin">
  {#if !connected}
    <AdminLogin onconnected={load} />
    {#if loadError}<p class="error" role="alert">{loadError}</p>{/if}
  {:else if calendar}
    <header class="admin-head">
      <h1>Administration</h1>
      <p>
        Connecté : {calendar.email}
        <button type="button" class="link" onclick={logout}>Se déconnecter</button>
      </p>
    </header>

    {#if loadError}<p class="error" role="alert">{loadError}</p>{/if}

    {#each groups as group (group.key)}
      <section aria-labelledby="admin-{group.key}">
        <h2 id="admin-{group.key}">{group.label}</h2>
        <ul class="admin-list">
          {#each group.items as session (session.date)}
            <li>
              <div class="who">
                <strong>{formatTuesday(session.date)}</strong>
                <span class="theme">{session.theme}</span>
                {#if session.booking}
                  <span class="name">{session.booking.name}</span>
                  <span class="phone">{session.booking.phone ?? 'téléphone non renseigné'}</span>
                {:else}
                  <span class="free">libre</span>
                {/if}
              </div>
              <div class="actions">
                <button type="button" onclick={() => (editing = session)}>
                  {session.booking ? 'Modifier' : 'Ajouter'}
                </button>
                {#if session.booking}
                  <button
                    type="button"
                    class="danger"
                    onclick={() => remove(session.date, session.booking!.name)}
                  >
                    Supprimer
                  </button>
                {/if}
              </div>
              {#if editing?.date === session.date}
                <AdminBookingForm
                  date={session.date}
                  theme={session.theme}
                  booking={session.booking}
                  onsaved={saved}
                  oncancel={() => (editing = null)}
                  onsessionlost={sessionLost}
                />
              {/if}
            </li>
          {/each}
        </ul>
      </section>
    {/each}

    {#if calendar.orphans.length > 0}
      <section aria-labelledby="orphans">
        <h2 id="orphans">Réservations hors programme</h2>
        <p class="notice">
          Ces mardis ne figurent plus dans le programme de la saison. Vous pouvez les supprimer.
        </p>
        <ul class="admin-list">
          {#each calendar.orphans as orphan (orphan.date)}
            <li>
              <div class="who">
                <strong>{formatTuesday(orphan.date)}</strong>
                <span class="name">{orphan.name}</span>
              </div>
              <div class="actions">
                <button type="button" class="danger" onclick={() => remove(orphan.date, orphan.name)}>
                  Supprimer
                </button>
              </div>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</div>
