<script lang="ts">
  import { untrack } from 'svelte';
  import { saveBooking } from '../lib/admin';
  import { formatTuesday } from '../lib/dates';
  import type { AdminBooking } from '../lib/types';

  let {
    date,
    theme,
    booking,
    onsaved,
    oncancel,
  }: {
    date: string;
    theme: string;
    booking: AdminBooking | null;
    onsaved: () => void;
    oncancel: () => void;
  } = $props();

  // La saisie ne doit pas se réinitialiser si `booking` change en cours d'édition :
  // seule la valeur initiale est capturée, volontairement.
  let name = $state(untrack(() => booking?.name ?? ''));
  let phone = $state(untrack(() => booking?.phone ?? ''));
  let error = $state('');
  let busy = $state(false);

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    if (name.trim().length < 2) {
      error = "Merci d'indiquer un nom (2 à 80 caractères).";
      return;
    }
    busy = true;
    const outcome = await saveBooking(date, { name, phone: phone.trim() || null });
    busy = false;
    if (outcome.kind === 'ok') {
      onsaved();
      return;
    }
    error = outcome.kind === 'unauthorized' ? 'Session expirée, reconnectez-vous.' : outcome.message;
  }
</script>

<form class="admin-form" onsubmit={submit}>
  <h3>{formatTuesday(date)} — {theme}</h3>
  <label for="form-name">Nom</label>
  <input id="form-name" bind:value={name} required disabled={busy} />
  <label for="form-phone">Téléphone (facultatif)</label>
  <input id="form-phone" bind:value={phone} inputmode="tel" disabled={busy} />
  <div class="actions">
    <button type="submit" disabled={busy}>Enregistrer</button>
    <button type="button" class="link" onclick={oncancel} disabled={busy}>Annuler</button>
  </div>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</form>
