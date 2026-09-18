<script lang="ts">
  import { openSession, requestCode } from '../lib/admin';

  let { onconnected }: { onconnected: () => void } = $props();

  let step = $state<'email' | 'code'>('email');
  let email = $state('');
  let code = $state('');
  let error = $state('');
  let notice = $state('');
  let busy = $state(false);

  async function askCode(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    busy = true;
    const outcome = await requestCode(email.trim());
    busy = false;
    if (outcome.kind === 'error') {
      error = outcome.message;
      return;
    }
    // La réponse est identique pour une adresse inconnue : le message reste neutre.
    notice = `Si ${email.trim()} est une adresse d'organisateur, un code vient d'y être envoyé.`;
    step = 'code';
  }

  async function submitCode(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    if (!/^\d{6}$/.test(code.trim())) {
      error = 'Le code comporte six chiffres.';
      return;
    }
    busy = true;
    const outcome = await openSession(email.trim(), code.trim());
    busy = false;
    if (outcome.kind === 'ok') {
      onconnected();
      return;
    }
    error = outcome.kind === 'unauthorized' ? 'Connexion refusée.' : outcome.message;
    code = '';
  }

  function restart() {
    step = 'email';
    code = '';
    error = '';
    notice = '';
  }
</script>

<section class="login">
  <h1>Administration</h1>
  {#if step === 'email'}
    <form onsubmit={askCode}>
      <label for="admin-email">Votre adresse d'organisateur</label>
      <input
        id="admin-email"
        type="email"
        bind:value={email}
        autocomplete="email"
        required
        disabled={busy}
      />
      <button type="submit" disabled={busy || !email.trim()}>Recevoir un code</button>
    </form>
  {:else}
    <form onsubmit={submitCode}>
      <p class="notice">{notice}</p>
      <label for="admin-code">Code à six chiffres</label>
      <input
        id="admin-code"
        bind:value={code}
        inputmode="numeric"
        autocomplete="one-time-code"
        maxlength="6"
        required
        disabled={busy}
      />
      <button type="submit" disabled={busy || !code.trim()}>Se connecter</button>
      <button type="button" class="link" onclick={restart}>Changer d'adresse</button>
    </form>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
