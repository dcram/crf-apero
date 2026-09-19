<script lang="ts">
  import { onMount } from 'svelte';

  let { contactEmail, onclose }: { contactEmail: string; onclose: () => void } = $props();

  let dialog = $state<HTMLDialogElement>();

  onMount(() => dialog?.showModal());
</script>

<dialog bind:this={dialog} class="sheet wide" aria-labelledby="mission-title" {onclose}>
  <div class="sheet-body mission">
    <button
      type="button"
      class="sheet-close"
      aria-label="Fermer"
      onclick={() => dialog?.close()}
    >
      ×
    </button>

    <header>
      <p class="eyebrow">Ce qu'on vous demande</p>
      <h2 id="mission-title">Votre mission</h2>
    </header>

    <section>
      <h3>En deux mots</h3>
      <p>
        Accueillir ceux qui font la démarche d'entrer ou de revenir dans l'Église, et prendre en
        charge la logistique de la soirée. Vous choisissez un mardi, ou plusieurs, vous apportez
        l'apéritif, vous restez discuter, vous repartez avec ce qui reste.
      </p>
    </section>

    <section>
      <h3>Le déroulement de la soirée</h3>
      <table class="schedule">
        <tbody>
          <tr><th scope="row">19h30</th><td>enseignement</td></tr>
          <tr><th scope="row">20h15</th><td>questions</td></tr>
          <tr>
            <th scope="row">20h30</th>
            <td><strong>moment convivial</strong> (c'est là que vous intervenez)</td>
          </tr>
          <tr><th scope="row">21h00</th><td>fin officielle de la soirée</td></tr>
        </tbody>
      </table>
      <p>
        Venez dès 19h30 suivre l'enseignement avec eux : c'est la meilleure façon d'entrer dans
        leurs questions avant de les retrouver au moment convivial.
      </p>
      <p>
        En pratique, les conversations débordent. Si vous le pouvez, restez jusqu'à 21h30. Rien ne
        vous y oblige : vous partez quand vous voulez, en emportant les restes.
      </p>
    </section>

    <section>
      <h3>Ce que vous apportez</h3>
      <p>
        Quelques boissons (bière, vin ou cidre, et de quoi boire sans alcool) et des amuse-bouches.
        Les effectifs varient beaucoup d'un mardi à l'autre ; tablez sur quinze personnes au
        maximum. Ce qui reste repart avec vous, et il en reste presque toujours.
      </p>
      <p>
        Si besoin, vous trouverez des verres en plastique et des couverts dans la cuisine du
        presbytère.
      </p>
    </section>

    <section>
      <h3>Pourquoi nous comptons sur vous</h3>
      <p>
        Les catéchumènes ont beaucoup de questions et sont très demandeurs d'accompagnement.
        Certains ne connaissent aucun catholique dans leur entourage, et ils sont encore trop
        nombreux à chercher un parrain à l'approche du sacrement.
      </p>
    </section>

    {#if contactEmail}
      <p class="ask">
        Une question ? <a href="mailto:{contactEmail}">{contactEmail}</a>
      </p>
    {/if}

    <div class="actions">
      <button type="button" class="primary" onclick={() => dialog?.close()}>
        Choisir mon mardi
      </button>
    </div>
  </div>
</dialog>
