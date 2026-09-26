/**
 * No listening data yet: point at the import settings, and offer a rebuild.
 * A port of the fork's GenomeEmptyState.vue. The Vue RouterLink to the import settings page
 * becomes a `navigate` event (detail "/import") that the panel routes; the rebuild button
 * dispatches `rebuild` and is only offered to someone allowed to run it.
 */
import { LitElement, css, html, nothing } from "lit";
import { t } from "../i18n";
import { iconDna, iconRefresh } from "../icons";
import { genomeBase, genomeTokens } from "../styles";

export class EmptyState extends LitElement {
  static properties = {
    loading: { type: Boolean },
    canRebuild: { type: Boolean },
  };

  loading = false;
  canRebuild = false;

  static styles = [
    genomeTokens,
    genomeBase,
    css`
      :host {
        display: block;
      }
      .panel {
        align-items: center;
        justify-content: center;
        gap: 24px;
        padding: 24px;
        text-align: center;
        text-wrap: balance;
        border-radius: 10px;
      }
      @media (min-width: 768px) {
        .panel {
          padding: 48px;
        }
      }
      .header {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        max-width: 24rem;
      }
      .media {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        margin-bottom: 8px;
        border-radius: 10px;
        color: var(--genome-accent);
        background: hsl(190 85% 62% / 0.1);
        border: 1px solid hsl(190 85% 62% / 0.25);
      }
      .media .icon {
        width: 24px;
        height: 24px;
      }
      h2 {
        margin: 0;
        font-size: 15px;
        text-transform: uppercase;
      }
      .body {
        font-size: 14px;
        line-height: 1.6;
        color: var(--genome-muted);
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 8px;
      }
    `,
  ];

  render() {
    return html`<section class="panel">
      <div class="header">
        <div class="media">${iconDna()}</div>
        <h2>${t("empty_title")}</h2>
        <p class="body">${t("empty_body")}</p>
      </div>
      <div class="actions">
        <button class="btn primary" @click=${this._navigate}>${t("empty_cta")}</button>
        ${this.canRebuild
          ? html`<button class="btn" ?disabled=${this.loading} @click=${this._rebuild}>
              ${iconRefresh(this.loading ? "icon spin" : "icon")} ${t("rebuild")}
            </button>`
          : nothing}
      </div>
    </section>`;
  }

  private _navigate(): void {
    this.dispatchEvent(new CustomEvent("navigate", { detail: "/import" }));
  }

  private _rebuild(): void {
    this.dispatchEvent(new CustomEvent("rebuild"));
  }
}

if (!customElements.get("lg-empty-state")) customElements.define("lg-empty-state", EmptyState);
