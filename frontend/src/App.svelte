<script lang="ts">
  import { onMount } from 'svelte';
  import BookingDialog from './components/BookingDialog.svelte';
  import SessionCard from './components/SessionCard.svelte';
  import { fetchCalendar } from './lib/api';
  import { groupByMonth } from './lib/dates';
  import type { Calendar, SessionItem } from './lib/types';

  const SKELETONS = [1, 2, 3, 4, 5, 6];

  let calendar = $state<Calendar | null>(null);
  let loadError = $state(false);
  let selected = $state<SessionItem | null>(null);

  const groups = $derived(calendar ? groupByMonth(calendar.sessions) : []);
  const allTaken = $derived(
    calendar !== null &&
      calendar.sessions.length > 0 &&
      calendar.sessions.every((session) => !session.available),
  );
  const season = $derived.by(() => {
    const sessions = calendar?.sessions ?? [];
    if (sessions.length === 0) return '';
    const first = sessions[0].date.slice(0, 4);
    const last = sessions[sessions.length - 1].date.slice(0, 4);
    return first === last ? first : `${first}–${last}`;
  });

  async function load() {
    try {
      calendar = await fetchCalendar();
      loadError = false;
    } catch {
      loadError = true;
    }
  }

  function closeDialog() {
    selected = null;
    load();
  }

  onMount(load);
</script>

<div class="page">
  <header class="masthead">
    <p class="eyebrow">Fraternité Saint-Pierre · Nantes</p>
    <h1>Le moment convivial<em>des commençants et recommençants dans la foi</em></h1>
    {#if season}<p class="season">Saison {season}</p>{/if}
    <div class="ornament" aria-hidden="true"><img src="/logo-crf.png" alt="" /></div>
    <p class="lead">
      Un mardi sur deux, le parcours <em>Commencer – Recommencer dans la Foi</em> se termine par
      un moment convivial. Chaque fois, un paroissien différent l'offre : il apporte de quoi boire
      et grignoter, et repart avec ce qui reste. C'est l'occasion de rencontrer ceux qui découvrent
      ou redécouvrent la foi.
    </p>
    <p class="lead">Choisissez le mardi qui vous convient.</p>
    {#if calendar?.event_info || calendar?.event_address}
      <div class="event-info">
        {#if calendar.event_info}<p>{calendar.event_info}</p>{/if}
        {#if calendar.event_address}
          <p class="address">
            {#if calendar.event_map_url}
              <a href={calendar.event_map_url} target="_blank" rel="noopener noreferrer">
                {calendar.event_address}
              </a>
            {:else}
              {calendar.event_address}
            {/if}
          </p>
        {/if}
      </div>
    {/if}
  </header>

  <main>
    {#if loadError}
      <p class="notice" role="alert">
        Impossible de charger les dates pour le moment.
        <button type="button" class="link" onclick={load}>Réessayer</button>
      </p>
    {:else if !calendar}
      <ul class="grid" aria-busy="true" aria-label="Chargement des dates">
        {#each SKELETONS as n (n)}<li class="skeleton"></li>{/each}
      </ul>
    {:else if calendar.sessions.length === 0}
      <p class="notice">Aucune rencontre n'est programmée pour le moment. Revenez bientôt !</p>
    {:else}
      {#if allTaken}
        <p class="notice">Tous les apéros de la saison ont trouvé preneur, merci !</p>
      {/if}
      {#each groups as group (group.key)}
        <section class="month" aria-labelledby="month-{group.key}">
          <h2 id="month-{group.key}">{group.label}</h2>
          <ul class="grid">
            {#each group.items as session (session.date)}
              <li><SessionCard {session} onpick={() => (selected = session)} /></li>
            {/each}
          </ul>
        </section>
      {/each}
    {/if}
  </main>

  <footer>
    Vos nom et téléphone sont transmis uniquement aux organisateurs du parcours CRF pour préparer
    l'apéro.
    {#if calendar?.contact_email}
      Pour les faire supprimer :
      <a href="mailto:{calendar.contact_email}">{calendar.contact_email}</a>.
    {/if}
  </footer>
</div>

{#if selected && calendar}
  <BookingDialog session={selected} {calendar} onclose={closeDialog} />
{/if}
