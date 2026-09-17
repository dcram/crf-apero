<script lang="ts">
  import { onMount } from 'svelte';
  import { createBooking } from '../lib/api';
  import { formatLongDate, formatTuesday } from '../lib/dates';
  import { buildIcs, icsFilename } from '../lib/ics';
  import type { BookingConfirmation, Calendar, SessionItem } from '../lib/types';
  import Turnstile from './Turnstile.svelte';

  let {
    session,
    calendar,
    onclose,
  }: { session: SessionItem; calendar: Calendar; onclose: () => void } = $props();

  let dialog = $state<HTMLDialogElement>();
  let turnstile: ReturnType<typeof Turnstile> | undefined = $state();
  let name = $state('');
  let phone = $state('');
  let website = $state('');
  let token = $state('');
  let submitting = $state(false);
  let error = $state('');
  let taken = $state(false);
  let showContact = $state(false);
  let confirmation = $state<BookingConfirmation | null>(null);

  onMount(() => dialog?.showModal());

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    showContact = false;
    if (name.trim().length < 2) {
      error = "Merci d'indiquer votre nom (2 à 80 caractères).";
      return;
    }
    if (!token) {
      error = 'Merci de patienter pendant la vérification anti-robot.';
      return;
    }
    submitting = true;
    const outcome = await createBooking({
      date: session.date,
      name,
      phone,
      turnstile_token: token,
      website,
    });
    submitting = false;

    if (outcome.kind === 'ok') {
      confirmation = outcome.booking;
      return;
    }
    error = outcome.message;
    if (outcome.kind === 'taken') {
      taken = true;
      return;
    }
    showContact = outcome.kind === 'unavailable';
    turnstile?.reset(); // un jeton Turnstile n'est valable qu'une fois
  }

  function addToCalendar() {
    const ics = buildIcs({
      date: session.date,
      startTime: calendar.apero_start_time,
      theme: session.theme,
      eventInfo: calendar.event_info,
      address: calendar.event_address,
    });
    const url = URL.createObjectURL(new Blob([ics], { type: 'text/calendar;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = icsFilename(session.date);
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
</script>

<dialog bind:this={dialog} class="sheet" aria-labelledby="dialog-title" {onclose}>
  {#if confirmation}
    <div class="sheet-body success" aria-live="polite">
      <div class="ornament" aria-hidden="true">❦</div>
      <h2 id="dialog-title">Merci {confirmation.name} !</h2>
      <p>
        Vous accueillez l'apéro du <strong>{formatLongDate(confirmation.date)}</strong>. Les
        organisateurs sont prévenus.
      </p>
      <div class="actions">
        <button type="button" class="secondary" onclick={addToCalendar}>
          Ajouter à mon agenda
        </button>
        <button type="button" class="primary" onclick={() => dialog?.close()}>Fermer</button>
      </div>
    </div>
  {:else}
    <form class="sheet-body" onsubmit={submit} novalidate>
      <header>
        <p class="eyebrow">Je m'en charge</p>
        <h2 id="dialog-title">{formatTuesday(session.date)}</h2>
        <p class="theme">{session.theme}</p>
      </header>

      <label>
        Votre nom
        <input
          name="name"
          autocomplete="name"
          maxlength="80"
          required
          bind:value={name}
          disabled={taken}
        />
      </label>
      <label>
        <span>Téléphone <span class="optional">(facultatif)</span></span>
        <input
          name="phone"
          type="tel"
          inputmode="tel"
          autocomplete="tel"
          bind:value={phone}
          disabled={taken}
        />
      </label>
      <div class="trap" aria-hidden="true">
        <label>
          Site web
          <input name="website" tabindex="-1" autocomplete="off" bind:value={website} />
        </label>
      </div>

      {#if !taken}
        <Turnstile
          bind:this={turnstile}
          siteKey={calendar.turnstile_site_key}
          ontoken={(value) => (token = value)}
        />
      {/if}

      <p class="form-error" role="alert">{error}</p>
      {#if showContact && calendar.contact_email}
        <p class="contact">
          Si le problème persiste, écrivez à
          <a href="mailto:{calendar.contact_email}">{calendar.contact_email}</a>.
        </p>
      {/if}

      <div class="actions">
        <button type="button" class="secondary" onclick={() => dialog?.close()}>
          {taken ? 'Choisir un autre mardi' : 'Annuler'}
        </button>
        {#if !taken}
          <button type="submit" class="primary" disabled={submitting}>
            {submitting ? 'Envoi…' : 'Confirmer'}
          </button>
        {/if}
      </div>
    </form>
  {/if}
</dialog>
