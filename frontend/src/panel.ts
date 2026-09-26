/**
 * <listening-genome-panel>: the sidebar panel Home Assistant loads (panel_custom).
 *
 * Home Assistant hands it `hass`, `narrow`, `route` and `panel`. Two views, chosen by the
 * route's path: the genome itself ("") and the import page ("/import").
 */
import { LitElement, css, html, nothing } from "lit";
import { GenomeApi, type Hass } from "./api";
import { installFonts } from "./fonts";
import { genomeTokens } from "./styles";
import "./genome-view";
import "./components/import-view";

interface Route {
  prefix: string;
  path: string;
}
interface PanelInfo {
  url_path?: string;
  config?: { static_base?: string };
}

export class ListeningGenomePanel extends LitElement {
  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
    route: { attribute: false },
    panel: { attribute: false },
  };

  hass?: Hass;
  narrow = false;
  route?: Route;
  panel?: PanelInfo;
  private _api?: GenomeApi;
  private _apiFor?: Hass;

  static styles = [
    genomeTokens,
    css`
      :host {
        display: block;
        min-height: 100vh;
        background: var(--genome-ground);
      }
      .menu {
        position: absolute;
        top: 12px;
        left: 8px;
        z-index: 2;
        width: 40px;
        height: 40px;
        border: 0;
        background: transparent;
        color: hsl(215 12% 72%);
        cursor: pointer;
      }
    `,
  ];

  connectedCallback(): void {
    super.connectedCallback();
    installFonts(this.panel?.config?.static_base ?? "/listening_genome_static");
  }

  /** One API object per `hass`: Home Assistant replaces `hass` on every state change. */
  private get api(): GenomeApi | undefined {
    if (!this.hass) return undefined;
    if (this._apiFor !== this.hass) {
      // the connection is the same across `hass` replacements; only rebuild when it is new
      if (!this._api || !this._apiFor) this._api = new GenomeApi(this.hass);
      this._apiFor = this.hass;
    }
    return this._api;
  }

  private _navigate = (path: string): void => {
    const base = this.route?.prefix ?? "/listening-genome";
    history.pushState(null, "", `${base}${path}`);
    window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
  };

  private _toggleMenu(): void {
    this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
  }

  render() {
    const api = this.api;
    if (!api) return nothing;
    const onImport = (this.route?.path ?? "").startsWith("/import");
    return html`
      ${this.narrow
        ? html`<button class="menu" aria-label="Menu" @click=${this._toggleMenu}>
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
              <path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z" />
            </svg>
          </button>`
        : nothing}
      ${onImport
        ? html`<lg-import-view
            .api=${api}
            .isAdmin=${this.hass?.user?.is_admin ?? false}
            .narrow=${this.narrow}
            @navigate=${(e: CustomEvent<string>) => this._navigate(e.detail)}
          ></lg-import-view>`
        : html`<lg-genome-view
            .api=${api}
            .isAdmin=${this.hass?.user?.is_admin ?? false}
            .narrow=${this.narrow}
            @navigate=${(e: CustomEvent<string>) => this._navigate(e.detail)}
          ></lg-genome-view>`}
    `;
  }
}

if (!customElements.get("listening-genome-panel")) {
  customElements.define("listening-genome-panel", ListeningGenomePanel);
}
