var re=globalThis,oe=re.ShadowRoot&&(re.ShadyCSS===void 0||re.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,ve=Symbol(),it=new WeakMap,J=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==ve)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(oe&&t===void 0){let s=e!==void 0&&e.length===1;s&&(t=it.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&it.set(e,t))}return t}toString(){return this.cssText}},ae=n=>new J(typeof n=="string"?n:n+"",void 0,ve),b=(n,...t)=>{let e=n.length===1?n[0]:t.reduce((s,i,r)=>s+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+n[r+1],n[0]);return new J(e,n,ve)},nt=(n,t)=>{if(oe)n.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let s=document.createElement("style"),i=re.litNonce;i!==void 0&&s.setAttribute("nonce",i),s.textContent=e.cssText,n.appendChild(s)}},ye=oe?n=>n:n=>n instanceof CSSStyleSheet?(t=>{let e="";for(let s of t.cssRules)e+=s.cssText;return ae(e)})(n):n;var{is:ws,defineProperty:$s,getOwnPropertyDescriptor:ks,getOwnPropertyNames:Ss,getOwnPropertySymbols:As,getPrototypeOf:Es}=Object,le=globalThis,rt=le.trustedTypes,Ms=rt?rt.emptyScript:"",Ts=le.reactiveElementPolyfillSupport,Y=(n,t)=>n,xe={toAttribute(n,t){switch(t){case Boolean:n=n?Ms:null;break;case Object:case Array:n=n==null?n:JSON.stringify(n)}return n},fromAttribute(n,t){let e=n;switch(t){case Boolean:e=n!==null;break;case Number:e=n===null?null:Number(n);break;case Object:case Array:try{e=JSON.parse(n)}catch{e=null}}return e}},at=(n,t)=>!ws(n,t),ot={attribute:!0,type:String,converter:xe,reflect:!1,useDefault:!1,hasChanged:at};Symbol.metadata??=Symbol("metadata"),le.litPropertyMetadata??=new WeakMap;var T=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=ot){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let s=Symbol(),i=this.getPropertyDescriptor(t,s,e);i!==void 0&&$s(this.prototype,t,i)}}static getPropertyDescriptor(t,e,s){let{get:i,set:r}=ks(this.prototype,t)??{get(){return this[e]},set(o){this[e]=o}};return{get:i,set(o){let p=i?.call(this);r?.call(this,o),this.requestUpdate(t,p,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??ot}static _$Ei(){if(this.hasOwnProperty(Y("elementProperties")))return;let t=Es(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(Y("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(Y("properties"))){let e=this.properties,s=[...Ss(e),...As(e)];for(let i of s)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[s,i]of e)this.elementProperties.set(s,i)}this._$Eh=new Map;for(let[e,s]of this.elementProperties){let i=this._$Eu(e,s);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let s=new Set(t.flat(1/0).reverse());for(let i of s)e.unshift(ye(i))}else t!==void 0&&e.push(ye(t));return e}static _$Eu(t,e){let s=e.attribute;return s===!1?void 0:typeof s=="string"?s:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return nt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){let s=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,s);if(i!==void 0&&s.reflect===!0){let r=(s.converter?.toAttribute!==void 0?s.converter:xe).toAttribute(e,s.type);this._$Em=t,r==null?this.removeAttribute(i):this.setAttribute(i,r),this._$Em=null}}_$AK(t,e){let s=this.constructor,i=s._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let r=s.getPropertyOptions(i),o=typeof r.converter=="function"?{fromAttribute:r.converter}:r.converter?.fromAttribute!==void 0?r.converter:xe;this._$Em=i;let p=o.fromAttribute(e,r.type);this[i]=p??this._$Ej?.get(i)??p,this._$Em=null}}requestUpdate(t,e,s,i=!1,r){if(t!==void 0){let o=this.constructor;if(i===!1&&(r=this[t]),s??=o.getPropertyOptions(t),!((s.hasChanged??at)(r,e)||s.useDefault&&s.reflect&&r===this._$Ej?.get(t)&&!this.hasAttribute(o._$Eu(t,s))))return;this.C(t,e,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:i,wrapped:r},o){s&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,o??e??this[t]),r!==!0||o!==void 0)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,r]of this._$Ep)this[i]=r;this._$Ep=void 0}let s=this.constructor.elementProperties;if(s.size>0)for(let[i,r]of s){let{wrapped:o}=r,p=this[i];o!==!0||this._$AL.has(i)||p===void 0||this.C(i,void 0,r,p)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(e)):this._$EM()}catch(s){throw t=!1,this._$EM(),s}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};T.elementStyles=[],T.shadowRootOptions={mode:"open"},T[Y("elementProperties")]=new Map,T[Y("finalized")]=new Map,Ts?.({ReactiveElement:T}),(le.reactiveElementVersions??=[]).push("2.1.2");var Me=globalThis,lt=n=>n,pe=Me.trustedTypes,pt=pe?pe.createPolicy("lit-html",{createHTML:n=>n}):void 0,gt="$lit$",C=`lit$${Math.random().toFixed(9).slice(2)}$`,ft="?"+C,Ps=`<${ft}>`,H=document,X=()=>H.createComment(""),Q=n=>n===null||typeof n!="object"&&typeof n!="function",Te=Array.isArray,Rs=n=>Te(n)||typeof n?.[Symbol.iterator]=="function",we=`[ 	
\f\r]`,Z=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,ct=/-->/g,dt=/>/g,O=RegExp(`>|${we}(?:([^\\s"'>=/]+)(${we}*=${we}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),ht=/'/g,ut=/"/g,_t=/^(?:script|style|textarea|title)$/i,Pe=n=>(t,...e)=>({_$litType$:n,strings:t,values:e}),l=Pe(1),v=Pe(2),xi=Pe(3),j=Symbol.for("lit-noChange"),d=Symbol.for("lit-nothing"),mt=new WeakMap,I=H.createTreeWalker(H,129);function bt(n,t){if(!Te(n)||!n.hasOwnProperty("raw"))throw Error("invalid template strings array");return pt!==void 0?pt.createHTML(t):t}var Cs=(n,t)=>{let e=n.length-1,s=[],i,r=t===2?"<svg>":t===3?"<math>":"",o=Z;for(let p=0;p<e;p++){let c=n[p],h,m,u=-1,g=0;for(;g<c.length&&(o.lastIndex=g,m=o.exec(c),m!==null);)g=o.lastIndex,o===Z?m[1]==="!--"?o=ct:m[1]!==void 0?o=dt:m[2]!==void 0?(_t.test(m[2])&&(i=RegExp("</"+m[2],"g")),o=O):m[3]!==void 0&&(o=O):o===O?m[0]===">"?(o=i??Z,u=-1):m[1]===void 0?u=-2:(u=o.lastIndex-m[2].length,h=m[1],o=m[3]===void 0?O:m[3]==='"'?ut:ht):o===ut||o===ht?o=O:o===ct||o===dt?o=Z:(o=O,i=void 0);let _=o===O&&n[p+1].startsWith("/>")?" ":"";r+=o===Z?c+Ps:u>=0?(s.push(h),c.slice(0,u)+gt+c.slice(u)+C+_):c+C+(u===-2?p:_)}return[bt(n,r+(n[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),s]},ee=class n{constructor({strings:t,_$litType$:e},s){let i;this.parts=[];let r=0,o=0,p=t.length-1,c=this.parts,[h,m]=Cs(t,e);if(this.el=n.createElement(h,s),I.currentNode=this.el.content,e===2||e===3){let u=this.el.content.firstChild;u.replaceWith(...u.childNodes)}for(;(i=I.nextNode())!==null&&c.length<p;){if(i.nodeType===1){if(i.hasAttributes())for(let u of i.getAttributeNames())if(u.endsWith(gt)){let g=m[o++],_=i.getAttribute(u).split(C),k=/([.?@])?(.*)/.exec(g);c.push({type:1,index:r,name:k[2],strings:_,ctor:k[1]==="."?ke:k[1]==="?"?Se:k[1]==="@"?Ae:B}),i.removeAttribute(u)}else u.startsWith(C)&&(c.push({type:6,index:r}),i.removeAttribute(u));if(_t.test(i.tagName)){let u=i.textContent.split(C),g=u.length-1;if(g>0){i.textContent=pe?pe.emptyScript:"";for(let _=0;_<g;_++)i.append(u[_],X()),I.nextNode(),c.push({type:2,index:++r});i.append(u[g],X())}}}else if(i.nodeType===8)if(i.data===ft)c.push({type:2,index:r});else{let u=-1;for(;(u=i.data.indexOf(C,u+1))!==-1;)c.push({type:7,index:r}),u+=C.length-1}r++}}static createElement(t,e){let s=H.createElement("template");return s.innerHTML=t,s}};function F(n,t,e=n,s){if(t===j)return t;let i=s!==void 0?e._$Co?.[s]:e._$Cl,r=Q(t)?void 0:t._$litDirective$;return i?.constructor!==r&&(i?._$AO?.(!1),r===void 0?i=void 0:(i=new r(n),i._$AT(n,e,s)),s!==void 0?(e._$Co??=[])[s]=i:e._$Cl=i),i!==void 0&&(t=F(n,i._$AS(n,t.values),i,s)),t}var $e=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:s}=this._$AD,i=(t?.creationScope??H).importNode(e,!0);I.currentNode=i;let r=I.nextNode(),o=0,p=0,c=s[0];for(;c!==void 0;){if(o===c.index){let h;c.type===2?h=new te(r,r.nextSibling,this,t):c.type===1?h=new c.ctor(r,c.name,c.strings,this,t):c.type===6&&(h=new Ee(r,this,t)),this._$AV.push(h),c=s[++p]}o!==c?.index&&(r=I.nextNode(),o++)}return I.currentNode=H,i}p(t){let e=0;for(let s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}},te=class n{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,i){this.type=2,this._$AH=d,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=F(this,t,e),Q(t)?t===d||t==null||t===""?(this._$AH!==d&&this._$AR(),this._$AH=d):t!==this._$AH&&t!==j&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):Rs(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==d&&Q(this._$AH)?this._$AA.nextSibling.data=t:this.T(H.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:s}=t,i=typeof s=="number"?this._$AC(t):(s.el===void 0&&(s.el=ee.createElement(bt(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(e);else{let r=new $e(i,this),o=r.u(this.options);r.p(e),this.T(o),this._$AH=r}}_$AC(t){let e=mt.get(t.strings);return e===void 0&&mt.set(t.strings,e=new ee(t)),e}k(t){Te(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,s,i=0;for(let r of t)i===e.length?e.push(s=new n(this.O(X()),this.O(X()),this,this.options)):s=e[i],s._$AI(r),i++;i<e.length&&(this._$AR(s&&s._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let s=lt(t).nextSibling;lt(t).remove(),t=s}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},B=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,i,r){this.type=1,this._$AH=d,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=r,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=d}_$AI(t,e=this,s,i){let r=this.strings,o=!1;if(r===void 0)t=F(this,t,e,0),o=!Q(t)||t!==this._$AH&&t!==j,o&&(this._$AH=t);else{let p=t,c,h;for(t=r[0],c=0;c<r.length-1;c++)h=F(this,p[s+c],e,c),h===j&&(h=this._$AH[c]),o||=!Q(h)||h!==this._$AH[c],h===d?t=d:t!==d&&(t+=(h??"")+r[c+1]),this._$AH[c]=h}o&&!i&&this.j(t)}j(t){t===d?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},ke=class extends B{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===d?void 0:t}},Se=class extends B{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==d)}},Ae=class extends B{constructor(t,e,s,i,r){super(t,e,s,i,r),this.type=5}_$AI(t,e=this){if((t=F(this,t,e,0)??d)===j)return;let s=this._$AH,i=t===d&&s!==d||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,r=t!==d&&(s===d||i);i&&this.element.removeEventListener(this.name,this,s),r&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},Ee=class{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){F(this,t)}};var Ls=Me.litHtmlPolyfillSupport;Ls?.(ee,te),(Me.litHtmlVersions??=[]).push("3.3.3");var vt=(n,t,e)=>{let s=e?.renderBefore??t,i=s._$litPart$;if(i===void 0){let r=e?.renderBefore??null;s._$litPart$=i=new te(t.insertBefore(X(),r),r,void 0,e??{})}return i._$AI(n),i};var Re=globalThis,f=class extends T{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=vt(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return j}};f._$litElement$=!0,f.finalized=!0,Re.litElementHydrateSupport?.({LitElement:f});var Ns=Re.litElementPolyfillSupport;Ns?.({LitElement:f});(Re.litElementVersions??=[]).push("4.2.2");var S="listening_genome",ce=class{constructor(t){this.hass=t;this.getGenome=()=>this.hass.callWS({type:`${S}/get`});this.rebuild=(t=!0)=>this.hass.callWS({type:`${S}/rebuild`,enrich:t});this.jobs=()=>this.hass.callWS({type:`${S}/jobs`});this.live=()=>this.hass.callWS({type:`${S}/live`});this.unresolvedArtists=(t=100)=>this.hass.callWS({type:`${S}/unresolved_artists`,limit:t});this.retryArtists=()=>this.hass.callWS({type:`${S}/retry_artists`});this.dismissUnresolved=()=>this.hass.callWS({type:`${S}/dismiss_unresolved`});this.discovery=()=>this.hass.callWS({type:`${S}/discovery`});this.discoveryRefresh=()=>this.hass.callWS({type:`${S}/discovery_refresh`});this.players=()=>this.hass.callWS({type:`${S}/players`});this.play=(t,e,s)=>this.hass.callWS({type:`${S}/play`,entity_id:t,artist:e,song:s});this.importLastfm=(t=0)=>this.hass.callWS({type:`${S}/import_lastfm`,max_pages:t})}async importApple(t){let e=new FormData;e.append("file",t);let s=await this.hass.fetchWithAuth("/api/file_upload",{method:"POST",body:e});if(!s.ok)throw new Error(s.status===413?"The file is larger than Home Assistant accepts (100 MB).":`Upload failed (HTTP ${s.status}).`);let{file_id:i}=await s.json();await this.hass.callWS({type:`${S}/import_apple`,file_id:i,filename:t.name})}};function A(n){return n&&typeof n=="object"&&"message"in n?String(n.message):String(n)}var zs=[["Syncopate",400,"Syncopate-Regular.woff2"],["Syncopate",700,"Syncopate-Bold.woff2"],["Jura",300,"Jura-Light.woff2"],["Jura",500,"Jura-Medium.woff2"],["Jura",600,"Jura-SemiBold.woff2"]];function yt(n){if(document.getElementById("listening-genome-fonts"))return;let t=document.createElement("style");t.id="listening-genome-fonts",t.textContent=zs.map(([e,s,i])=>`@font-face{font-family:"${e}";font-style:normal;font-weight:${s};font-display:swap;src:url("${n}/fonts/${i}") format("woff2");}`).join(`
`),document.head.append(t)}var y=b`
  :host {
    --genome-display: "Syncopate", ui-sans-serif, system-ui, sans-serif;
    --genome-text: "Jura", ui-sans-serif, system-ui, sans-serif;
    --genome-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    --genome-accent: hsl(190 85% 62%);
    --genome-panel-bg: hsl(215 40% 60% / 0.05);
    --genome-panel-border: hsl(200 65% 70% / 0.3);
    --genome-panel-rim: hsl(200 65% 70% / 0.07);
    --genome-tick: hsl(190 90% 66% / 0.95);
    --genome-ground: #070a10;
    --genome-fg: #e7e9ee;
    --genome-muted: hsl(215 8% 55%);
    --genome-radius: 14px;
    font-family: var(--genome-text);
    font-feature-settings:
      "tnum" 1,
      "zero" 1;
    color: var(--genome-fg);
  }
`,w=b`
  * {
    box-sizing: border-box;
  }
  h1,
  h2 {
    font-family: var(--genome-display);
    font-weight: 400;
    letter-spacing: 0.04em;
  }
  h3 {
    font-family: var(--genome-text);
    font-weight: 600;
    letter-spacing: 0.1em;
  }
  p {
    margin: 0;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  /* ---- panels: the corner ticks are the signature ---------------------------------- */
  .panel {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 20px;
    border-radius: var(--genome-radius);
    background: var(--genome-panel-bg);
    backdrop-filter: blur(6px);
  }
  /* The rim: a hairline that is bright at the top-left and bottom-right corners and fades out
     along both edges, like the rule under the page title. It is painted as a gradient and
     masked down to a 1px ring, because a real border cannot fade along its length and still
     follow the rounded corners. */
  .panel::before {
    content: "";
    position: absolute;
    inset: 0;
    padding: 1px;
    border-radius: inherit;
    pointer-events: none;
    background:
      radial-gradient(
        45% 180px at 0 0,
        var(--genome-tick),
        hsl(200 65% 70% / 0.14) 40%,
        transparent 100%
      ),
      radial-gradient(
        30% 120px at 100% 100%,
        var(--genome-tick),
        hsl(200 65% 70% / 0.12) 40%,
        transparent 100%
      ),
      var(--genome-panel-rim);
    -webkit-mask:
      linear-gradient(#000 0 0) content-box,
      linear-gradient(#000 0 0);
    -webkit-mask-composite: xor;
    mask:
      linear-gradient(#000 0 0) content-box exclude,
      linear-gradient(#000 0 0);
  }
  .panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }
  /* card titles are instrument labels: small, uppercase, tracked, quiet */
  .panel-title {
    margin: 0;
    font-family: var(--genome-display);
    font-weight: 400;
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: hsl(215 10% 62%);
  }
  .panel-description {
    margin: 4px 0 0;
    font-family: var(--genome-text);
    font-size: 12px;
    letter-spacing: 0.01em;
    color: hsl(215 8% 48%);
  }

  /* any big figure */
  .figure {
    font-family: var(--genome-display);
    font-weight: 400;
    font-size: 24px;
    line-height: 1.2;
    letter-spacing: 0.005em;
    font-variant-numeric: tabular-nums;
  }
  .code {
    font: 600 9.5px/1 var(--genome-mono);
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: hsl(215 8% 48%);
  }
  .muted {
    color: var(--genome-muted);
  }
  .small {
    font-size: 12px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: var(--genome-mono);
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    border-radius: 3px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.04);
    color: hsl(215 12% 72%);
    padding: 4px 9px;
  }

  /* ---- buttons ------------------------------------------------------------------ */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-height: 32px;
    padding: 6px 12px;
    font: 600 10.5px/1 var(--genome-mono);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--genome-fg);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 6px;
    cursor: pointer;
    transition:
      border-color 120ms ease,
      background-color 120ms ease,
      color 120ms ease;
  }
  .btn:hover:not([disabled]) {
    border-color: var(--genome-accent);
    color: var(--genome-accent);
  }
  .btn:focus-visible,
  .icon-btn:focus-visible,
  .tab:focus-visible {
    outline: 1px solid var(--genome-accent);
    outline-offset: 2px;
  }
  .btn[disabled] {
    opacity: 0.45;
    cursor: default;
  }
  .btn.primary {
    background: hsl(190 85% 62% / 0.13);
    border-color: hsl(190 85% 62% / 0.5);
    color: var(--genome-accent);
  }
  .icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    color: hsl(215 12% 72%);
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    cursor: pointer;
  }
  .icon-btn:hover:not([disabled]) {
    color: var(--genome-accent);
    border-color: hsl(190 85% 62% / 0.35);
  }
  .icon-btn[disabled] {
    opacity: 0.45;
    cursor: default;
  }
  .icon {
    width: 16px;
    height: 16px;
    flex: none;
  }
  .spin {
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* ---- tabs: the active one is the brighter of the two --------------------------- */
  .tabs {
    display: inline-flex;
    gap: 3px;
    padding: 3px;
    background: hsl(215 40% 60% / 0.06);
    border: 1px solid var(--genome-panel-border);
    border-radius: 7px;
  }
  .tab {
    padding: 6px 10px;
    font: 600 9.5px/1 var(--genome-mono);
    letter-spacing: 0.14em;
    text-transform: uppercase;
    border: 0;
    border-radius: 5px;
    background: transparent;
    color: hsl(215 10% 52%);
    cursor: pointer;
    transition:
      background-color 120ms ease,
      color 120ms ease;
  }
  .tab:hover {
    color: hsl(210 14% 76%);
  }
  .tab[aria-selected="true"] {
    background: hsl(190 85% 62% / 0.13);
    color: var(--genome-accent);
  }

  /* ---- form fields --------------------------------------------------------------- */
  select,
  input[type="text"] {
    min-height: 32px;
    padding: 4px 8px;
    font: 500 13px var(--genome-text);
    color: var(--genome-fg);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 6px;
  }
  select:focus-visible,
  input:focus-visible {
    outline: 1px solid var(--genome-accent);
  }
  option {
    background: #10141c;
    color: var(--genome-fg);
  }

  /* ---- progress: indeterminate or a value ----------------------------------------- */
  .progress {
    position: relative;
    height: 3px;
    overflow: hidden;
    border-radius: 2px;
    background: rgba(255, 255, 255, 0.08);
  }
  .progress > span {
    position: absolute;
    inset: 0 auto 0 0;
    background: var(--genome-accent);
    box-shadow: 0 0 6px hsl(190 90% 60% / 0.6);
  }
  .progress.indeterminate > span {
    width: 35%;
    animation: slide 1.2s ease-in-out infinite;
  }
  @keyframes slide {
    from {
      left: -35%;
    }
    to {
      left: 100%;
    }
  }

  .error {
    color: hsl(0 80% 72%);
  }
  @media (prefers-reduced-motion: reduce) {
    .spin,
    .progress.indeterminate > span {
      animation-duration: 3s;
    }
  }
`;function L(n){return`${Math.round(n*100)}%`}function de(n){let t=Math.round(n*10)/10;return Number.isInteger(t)?`${t}x`:`${t.toFixed(1)}x`}function D(n){return n.toLocaleString("en-US")}function xt(n){return n.reduce((t,e)=>Math.max(t,e.share),0)}function wt(n){return Math.round(n).toString()}function Ce(n){return n.artists_pending>0}function $t(n){return Ce(n)?!1:n.artists_failed>0&&!n.unresolved_dismissed}var kt={title:"Listening Genome",subtitle:"A DNA profile of what this household actually listens to.",divergence_caption:"off-mainstream",ring_aria:"{percent}% off-mainstream",genre_share:"Genre share",others:"+{count} others",obscurity:"Obscurity index",obscurity_tooltip:"Play-weighted share of listening on artists below the configured popularity percentile.",low_confidence:"Low confidence",era_center:"Era centre",era_center_tooltip:"The weighted average release year of everything played.",years:"years",exploration:"Exploration",exploration_tooltip:"Share of listening on artists first heard in the last 90 days.",new_artists:"{count} new artists in 90 days",top_lists:"Top artists & tracks",top_artists:"Top artists",top_tracks:"Top tracks",rhythm:"Listening rhythm",players:"Rooms",plays:"{count} plays",vs_average:"{ratio} average",stats_footer:"{listens} listens \xB7 {artists} artists \xB7 {tracks} tracks",stale_notice:"Data may be out of date, rebuild for the latest numbers",empty_title:"No listening data yet",empty_body:"Import your history or let Music Assistant collect plays for a few days.",empty_cta:"Go to settings",load_error:"Could not load the listening genome",open_settings:"Import history & settings",rebuild:"Rebuild genome",rebuild_success:"Genome rebuilt",rebuild_error:"Could not rebuild the genome",weekday_mon:"Mon",weekday_tue:"Tue",weekday_wed:"Wed",weekday_thu:"Thu",weekday_fri:"Fri",weekday_sat:"Sat",weekday_sun:"Sun",settings:{title:"Listening Genome",import_hub_description:"Import your Last.fm scrobble history or an Apple Music export.",import_apple:"Import Apple Music export",import_apple_hint:"From your privacy.apple.com export, upload Apple Music - Play History Daily Tracks.csv. It is the only file in the export that names the artist.",export_title:"Export genome database",export_hint:"Write a copy of the genome database to the first shared folder this app can reach (usually /media), where the file editor and Samba can pick it up. Temporary, for moving this data to the standalone Home Assistant integration.",export_action:"Export database",export_result:"Exported {listens} listens to {path}",import_lastfm:"Import Last.fm history",import_lastfm_hint:"Pull your public scrobble history from Last.fm.",lastfm_username:"Last.fm username",lastfm_api_key:"Last.fm API key",lastfm_api_key_placeholder:"Enter your Last.fm API key",lastfm_api_key_set_placeholder:"Unchanged (a key is already set)",lastfm_api_key_hint:"Stored once and shared with the Listening Genome config page; leave blank to keep the current key.",lastfm_get_api_key:"Get a Last.fm API key",lastfm_ready:"Username and API key are set \u2014 ready to import.",lastfm_missing_username:"Add a Last.fm username to enable importing.",lastfm_missing_api_key:"Add a Last.fm API key to enable importing.",lastfm_missing_both:"Add a Last.fm username and API key to enable importing.",import_result_detail:"{imported} added, {skipped} skipped, {duplicate} already imported",choose_file:"Choose file...",no_file_chosen:"No file chosen",import_success:"Imported {count} listens",import_error:"Import failed",job_running_lastfm:"Importing from Last.fm\u2026",job_running_apple:"Processing the uploaded file\u2026",job_running_export:"Writing the database copy\u2026",job_uploading:"Uploading\u2026 {percent}%",job_result_when:"{message} \xB7 {when}",time_just_now:"just now",time_minute_ago:"1 minute ago",time_minutes_ago:"{count} minutes ago",time_hour_ago:"1 hour ago",time_hours_ago:"{count} hours ago",time_day_ago:"1 day ago",time_days_ago:"{count} days ago"},enriching_title:"Genres still resolving",enriching_body:"{resolved} artists resolved, {pending} still to go. The genre mix and divergence score will keep firming up as this finishes in the background.",molecule:{title:"Genome \u2014 molecular plate",subtitle:"The backbone is what you listen to; the rungs are what makes you unique.",svg_aria:"Genome molecule: a DNA-shaped plot of your top genres and their secondary genre pairs",hint:"Hover or focus any lit rung or backbone strand. The molecule holds still while you read.",bases_heading:"Base pairs",bases_subtitle:"Your top genres.",no_bases:"Not enough resolved listening yet to identify your top genres.",backbone_explainer:"Each strand runs through your top genres in turn. A rung takes its colour from the strands it joins. The six brightest are where you sit furthest from average.",backbone_label:"Backbone",backbone_desc:"All {plays} listens \xB7 the library itself",backbone_desc_empty:"Not enough resolved listening yet to blend a backbone.",share_of_listening:"{percent} of listening \xB7 {plays} plays",mix_unknown:"Genre mix not yet known \u2014 still resolving.",status_overexpressed:"Overexpressed",status_stable:"Stable",status_underexpressed:"Underexpressed",rung_aria:"{label}, {percent} of listening, {status}",leg_aria:"Backbone strand, blend of {count} base genres",leg_aria_empty:"Backbone strand, not enough data yet to blend",legend_heading:"Expression",legend_over:"Overexpressed \u2014 you play this far more than the average listener: at least twice the baseline share.",legend_stable:"Stable \u2014 close to the baseline. Present in your listening at roughly the rate it is present in everyone's.",legend_under:"Underexpressed \u2014 present, but well below the baseline: under 70% of the average listener's share.",legend_note:"Measured against a reference profile built from global ListenBrainz listening, so \u201Caverage\u201D means average across many people, not across your own library.",mix_heading:"Colour mixing",mix_lead:"Every rung is mixed from the four base genres above, in proportion to how much of that genre's listening belongs to each.",mix_pure:"Almost all one base \u2014 the rung takes that base's colour outright.",mix_blend:"Split between two bases \u2014 the rung lands on the colour between them, and belongs to neither.",mix_even:"Spread evenly across all four \u2014 the colours cancel and the rung comes back nearly grey. That is the honest reading: no particular allegiance.",mix_note:"Brightness is separate: the six rungs where you diverge most from the baseline are shown in full colour, the rest in the same hue drained back.",genre_desc:{afrobeats:"West African pop rhythms with drums, synths and dancehall",ambient:"Slow-moving atmospheric music, minimal rhythm, textural focus",anime_and_video_game_music:"Orchestral and electronic scores from Japanese anime and games",asian_music:"Pop and traditional styles from East and Southeast Asia",bluegrass:"Acoustic Appalachian string-band music, banjo to the front",blues:"12-bar guitar and vocal tradition from the American South",brazilian_music:"Samba, bossa nova and MPB rhythms from Brazil",chanson:"French vocal tradition centered on lyrics and storytelling",childrens_music:"Simple songs made for young children",christmas_music:"Seasonal songs tied to the Christmas holiday",church_music:"Music composed and performed for Christian worship services",classical:"Notated orchestral and chamber music, Western tradition",comedy:"Spoken comic material, sketches and stand-up routines",country:"Guitar and storytelling music from the rural American South",dance:"Uptempo electronic music built for club dancefloors",dark_ambient:"Ambient music using drones and textures for a bleak mood",dark_wave:"Post-punk-descended electronic music with a gothic, moody tone",disco:"Four-on-the-floor dance music from 1970s discotheques",electronic:"Music made primarily with synthesizers and digital production",experimental:"Music that departs from conventional structure, form or sound",field_recording:"Unstaged audio captured in place; environments, not songs",folk:"Acoustic traditional and singer-driven music, often narrative",funk:"Syncopated bass and drum grooves, rhythm-first dance music",gangsta_rap:"Hip-hop focused on street life, crime and urban hardship",gospel:"Christian vocal music with choirs, testimony and call-response",hip_hop:"Rhythmic spoken vocals over beats, born in 1970s New York",indian_classical:"Raga-based classical traditions of the Indian subcontinent",industrial:"Harsh electronic music using noise, machinery and distortion",jazz:"Improvised music built on swing, syncopation and harmony",klezmer:"Instrumental dance music from Eastern European Jewish life",latin:"Spanish and Portuguese-language music from Latin America",marching_band:"Wind, brass and percussion music performed while marching",middle_eastern_music:"Traditional and pop styles from the Middle East region",musical:"Songs written for stage and film musical theater",new_age:"Calm instrumental music meant for relaxation and meditation",poetry:"Spoken verse recordings, rhythm and language over music",polka:"Upbeat accordion-led dance music of Central European origin",pop:"Melodic, hook-driven mainstream music built for broad appeal",psychedelic:"Studio-effects rock built on drift, repetition and drone",punk:"Fast, stripped-down guitar rock from the mid-1970s underground",r_b:"Black American pop built on soul, gospel and swung grooves",ragtime:"Syncopated piano music popular in the US around 1900",rai:"North African dance-pop with roots in Algeria's Oran region",reggae:"Offbeat guitar skank and bass grooves from 1960s Jamaica",reggaeton:"Dembow-rhythm Latin urban music from Puerto Rico",rock:"Guitar, bass and drums descended from 1950s rock and roll",salsa:"Cuban-rooted dance music with horns and clave rhythm",singer_songwriter:"Personal, lyric-focused music performed by its own writer",ska:"Upbeat offbeat guitar rhythms and horns, Jamaican in origin",soul:"Gospel-rooted Black American vocal music with heavy emotion",sound_effects:"Non-musical recorded sounds used for production or effect",soundtrack:"Music composed for film, television or other visual media",spoken_word:"Recorded speech performance, prose or verse without singing",swing:"Big-band jazz built for dancing, popular in the 1930s-40s",tango:"Bandoneon-led dance music from Buenos Aires and Montevideo",trap:"Hip-hop subgenre with heavy 808s and rapid hi-hats",waltz:"Instrumental dance music in triple meter",wellness:"Instrumental audio intended for relaxation and mindfulness",metal:"Distorted, guitar-heavy rock with amplified aggression"},status_unmeasured:"No baseline",legend_unmeasured:"No baseline \u2014 the reference profile is built from the world's most-played artists, so quieter genres are absent from it entirely. Your listening here still counts; there is simply nothing to compare it against."},eclecticism:"Eclecticism",eclecticism_tooltip:"The effective number of genres in your listening \u2014 the count you would have if your play time were spread evenly across that many. A library dominated by one genre scores near 1 however many genres it technically contains.",eclecticism_vs_average:"vs {baseline} for the average listener",eclecticism_no_baseline:"No baseline to compare against yet",unresolved_title:"Some artists could not be identified",unresolved_body:"{failed} artist(s) failed to resolve against MusicBrainz and are no longer being retried on every pass. Their listening still counts; only their genre and era are missing.",unresolved_show:"Show which ones",unresolved_dialog_hint:"These artists' names could not be matched against MusicBrainz. Their plays still count toward your totals; only their genre and era are missing.",attempted_recently:"just tried",attempted_hours:"{hours}h ago",attempted_days:"{days}d ago",loading:"Loading\u2026",share_of_plays:"Share of plays",unresolved_retry:"Try these again",unresolved_dismiss:"Dismiss",unresolved_what_to_do:"A lookup failure usually comes down to how the artist is named in your library \u2014 a compilation credit, a \u201Cfeat.\u201D string, or a typo will not match anything in MusicBrainz. Fixing the tag and rebuilding is the real repair. If it was just a bad night for the network, try them again.",unresolved_dismiss_hint:"Dismissing hides the notice for exactly these artists. If different ones fail later, it comes back.",unresolved_retried:"Queued for another attempt",discovery:{title:"Discovery",lead:"Drawn from the genres where your listening diverges most from the baseline.",suggested_heading:"Not in your library",cold_heading:"Yours, barely played",because:"similar to {seed}",match_title:"How close Last.fm rates the match",never_played:"Never played",n_plays:"{plays} plays",pending:"Working through your most distinctive artists. Suggestions appear here once the background pass has run.",no_lastfm:"Suggestions need a Last.fm API key.",no_lastfm_action:"Add one in settings",no_suggestions:"No suggestions yet that aren't already in your library.",no_cold:"Nothing neglected \u2014 you've played everything in your library.",refresh:"Look for new suggestions",error:"Could not load discovery data."},rhythm_quieter:"Quieter",rhythm_busier:"Busier",panel:{discovery:{try:"Try: {song}",speaker_label:"Play on",speaker_unavailable:"{name} (unavailable)",no_speakers:"No Music Assistant speakers",no_speaker_title:"No Music Assistant speaker is available to play on",play_aria:"Play {song} by {artist} on {speaker}",starting:"Starting\u2026",playing_on:"Playing on {speaker}",refreshing:"Looking for new suggestions\u2026 the list updates when the pass finishes.",refresh_failed:"Could not start a discovery pass: {error}",no_lastfm_where:"Suggestions need a Last.fm account. Set it in Settings > Devices & services > Listening Genome > Configure."},import:{back:"Back to the genome",title:"Import & status",subtitle:"Bring in listening history, and see what the background jobs are doing.",apple_choose:"Choose export file",apple_uploading:"Uploading {file}\u2026",apple_started:"Import of {file} started. Its progress shows below.",lastfm_title:"Last.fm history",lastfm_hint:"Pull the configured account's public scrobble history from Last.fm. The first import sweeps the whole history and can take several minutes.",lastfm_import_now:"Import now",lastfm_started:"Last.fm import started. Its progress shows below.",lastfm_where:"Set the Last.fm username and API key in Settings > Devices & services > Listening Genome > Configure.",lastfm_unset:"Last.fm is not set up yet.",admin_only:"Only a Home Assistant administrator can start imports.",status_title:"Background jobs",status_description:"Updated every 2 seconds while anything is running.",status_error:"Could not read the job status: {error}",live_title:"Music Assistant connection",live_connected:"Connected",live_disconnected:"Disconnected",live_version:"Music Assistant {version}",live_plays:"{count} plays captured",live_last_play:"Last play: {play}",live_last_play_when:"Last play: {play} \xB7 {when}",live_no_play:"No play captured yet",live_last_error:"Last error: {error}",live_error:"Could not read the connection status: {error}"},job:{rebuild:"Genome rebuild",enrichment:"Genre lookup (MusicBrainz)",lastfm_import:"Last.fm import",apple_import:"Apple Music import",duplicates:"Duplicate cleanup",discovery:"Discovery"},state:{idle:"Idle",running:"Running",ok:"Done",error:"Failed",interrupted:"Interrupted"},job_working:"Working\u2026",job_started:"{message} \xB7 started {when}",job_never:"Not run yet",progress_aria:"{job} progress"}};function a(n,t={}){let e=kt;for(let s of n.split("."))e=typeof e=="object"?e[s]:void 0;return typeof e!="string"?n:e.replace(/\{(\w+)\}/g,(s,i)=>i in t?String(t[i]):s)}var N=(n,t="icon")=>v`<svg class=${t} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${n}</svg>`,he=n=>N(v`<path d="m10 16 1.5 1.5"/><path d="m14 8-1.5-1.5"/><path d="M15 2c-1.798 1.998-2.518 3.995-2.807 5.993"/><path d="m16.5 10.5 1 1"/><path d="m17 6-2.891-2.891"/><path d="M2 15c6.667-6 13.333 0 20-6"/><path d="m20 9 .891.891"/><path d="M3.109 14.109 4 15"/><path d="m6.5 12.5 1 1"/><path d="m7 18 2.891 2.891"/><path d="M9 22c1.798-1.998 2.518-3.995 2.807-5.993"/>`,n),V=n=>N(v`<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>`,n),St=n=>N(v`<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>`,n),At=n=>N(v`<polygon points="6 3 20 12 6 21 6 3"/>`,n),Et=n=>N(v`<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>`,n),Mt=n=>N(v`<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>`,n),z=(n="icon spin")=>N(v`<path d="M21 12a9 9 0 1 1-6.219-8.56"/>`,n),Tt=n=>N(v`<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>`,n);var Pt=9*Math.PI/180,Rt=26,zt=.032,Le=6;function Us(n){let t=n>>>0;return()=>(t=Math.imul(t,1664525)+1013904223>>>0,t/4294967296)}var Os=3,Ct=150,Is=2,Lt=44;function Gt(n=7){let t=Us(n),e=()=>(t()+t()+t()+t()-2)*.9,s=[];for(let r=0;r<Ct;r++){let o=r/Ct;for(let p of[0,1]){for(let c=0;c<Os;c++)s.push({leg:p,t:o,dTheta:e()*.028,dRadius:e()*5.5,dY:e()*3.4,size:1.4+t()*2.4,gain:.5+t()});for(let c=0;c<Is;c++)s.push({leg:p,t:o,dTheta:e()*.085,dRadius:e()*13,dY:e()*8,size:1.1+t()*1.8,gain:.08+t()*.16})}}let i=[];for(let r=0;r<Rt;r++){let o=(r+.5)/Rt,p=[];for(let c=0;c<Lt;c++)p.push({f:(c+.5)/Lt+e()*.012,dRadius:e()*3.2,dY:e()*2.6,size:1.3+t()*2.2,gain:.45+t()});i.push({index:r,t:o,particles:p})}return{legs:s,rungs:i}}function Hs(n,t){let e=n-270,s=t-700/2,i=Math.cos(Pt),r=Math.sin(Pt);return[270+e*i-s*r,700/2+e*r+s*i]}function x(n,t,e,s=0,i=0,r=0){let o=e+2*Math.PI*3.5*n+(t?Math.PI:0)+s,p=1/(1+.18*Math.abs(n-.5)*2),c=(116+i)*p,[h,m]=Hs(270+c*Math.cos(o),66+n*568+r);return{x:h,y:m,depth:(c*Math.sin(o)/116+1)/2}}function Ut(n,t){let e=new Set(t.map(s=>s.key));return n.filter(s=>!e.has(s.key))}function Ot(n,t=Le){return[...n].filter(e=>e.contribution>0).sort((e,s)=>s.contribution-e.contribution).slice(0,t)}function It(n){let t=n.reduce((i,r)=>i+Math.max(0,r.share),0);if(n.length===0||t<=0)return[];let e=[],s=0;return n.forEach((i,r)=>{let o=Math.max(0,i.share)/t;e.push({from:s,to:s+o,baseIndex:r}),s+=o}),e.length>0&&(e[e.length-1].to=1),e}function Ht(n,t,e=.05){if(n.length===0)return{index:-1,next:-1,mix:0};let s=n.findIndex(p=>t<p.to);s===-1&&(s=n.length-1);let i=n[s],r=i.to-t;if(s<n.length-1&&r<e)return{index:s,next:s+1,mix:.5*(1-r/e)};let o=t-i.from;return s>0&&o<e?{index:s,next:s-1,mix:.5*(1-o/e)}:{index:s,next:-1,mix:0}}function Ne(n,t,e,s,i,r){let o=i-e,p=r-s,c=o*o+p*p;if(c===0)return Math.hypot(n-e,t-s);let h=((n-e)*o+(t-s)*p)/c;return h=Math.max(0,Math.min(1,h)),Math.hypot(n-(e+h*o),t-(s+h*p))}function jt(n,t,e=0){let s=[...n].sort((r,o)=>{let p=Nt(r.t,e);return Nt(o.t,e)-p}),i=new Map;return t.forEach((r,o)=>{let p=s[o];p&&i.set(p.index,r)}),i}function Nt(n,t){let e=x(n,0,t),s=x(n,1,t);return Math.hypot(e.x-s.x,e.y-s.y)}function ze(n,t=!0){return t?n>=2?"overexpressed":n>=.7?"stable":"underexpressed":"unmeasured"}function Dt(n,t){let e=0;return n.map((s,i)=>{let r=e+s/2;return e+=s,{offsetPercent:r*100,color:t(i)}})}function Ft(n,t){return Math.round(n*t)}function Bt(n){return(n.replace(/[^a-z]/gi,"").toUpperCase().slice(0,3)||"GEN").padEnd(3,"X")}function Vt(n){return`GEN-${String(n+1).padStart(2,"0")}`}function js(n,t,e){let s=e*Math.PI/180,i=t*Math.cos(s),r=t*Math.sin(s),o=(n+.3963377774*i+.2158037573*r)**3,p=(n-.1055613458*i-.0638541728*r)**3,c=(n-.0894841775*i-1.291485548*r)**3;return{r:4.0767416621*o-3.3077115913*p+.2309699292*c,g:-1.2684380046*o+2.6097574011*p-.3413193965*c,b:-.0041960863*o-.7034186147*p+1.707614701*c}}function Ge(n){let t=Math.max(0,Math.min(1,n)),e=t<=.0031308?12.92*t:1.055*t**(1/2.4)-.055;return Math.round(e*255)}function E(n,t,e,s){let i=js(n,t,e),r=Ge(i.r),o=Ge(i.g),p=Ge(i.b);return s===void 0?`rgb(${r} ${o} ${p})`:`rgba(${r}, ${o}, ${p}, ${Math.max(0,Math.min(1,s))})`}var $=[220,310,40,130],Ue=.74,Kt=.115;function ue(n,t=Ue,e=Kt){return E(t,e,$[n%$.length])}function qt(n,t=!1){let e=n.reduce((h,m)=>h+Math.max(0,m),0);if(n.length===0||e<=0)return K;let s=0,i=0;n.forEach((h,m)=>{let u=$[m%$.length]*Math.PI/180,g=Math.max(0,h)/e;s+=g*Math.cos(u),i+=g*Math.sin(u)});let r=(Math.atan2(i,s)*180/Math.PI+360)%360,o=Math.min(1,Math.hypot(s,i)),p=Kt*o**.7*(t?.4:1),c=(.5+.24*o)*(t?.9:1);return E(c,p,r)}var K=E(.88,.006,240);function Oe(n,t,e){let s=(t-n+540)%360-180;return(n+s*e+360)%360}var P=6;function Wt(n,t=P){let e=n.filter(i=>i>0).sort((i,r)=>i-r);if(e.length===0)return[];let s=[];for(let i=1;i<t;i++){let r=Math.floor(e.length*i/t);s.push(e[Math.min(r,e.length-1)])}return s}function Jt(n,t,e=0){if(n<=0)return 0;let s=1;for(let p of t)n>p&&s++;if(e<=0)return Math.min(s,P-1);let i=s/(P-1),r=n/e,o=.5*i+.5*r;return Math.max(1,Math.min(P-1,Math.round(o*(P-1))))}function Ie(n){let t=Math.max(0,Math.min(1,n)),e=.26+.48*t,s=.025+.095*t,i=Oe(232,168,t);return E(e,s,i)}var Yt="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAWgAAAAQCAQAAACR6i1GAAALZ0lEQVR4nO3a2XNc13EG8N9dZsdgsIoACZISZcmS5YfESaUqlf8+D3lKKilVxVbFFgWKWAfA7Nude2cmD3MwASnKJduypLjU9w04p08v3+nzdQPRys/ys/ztSPxjG/ATkUj0Y5vws3wfEv1cof9fSOSHTNR3Py0SS8QiKwtLyx/UzncZ9BMDdCQRi3kQnkgsFossw/f9npdKJFgoLCy+Y0piiURkZWlh8T3a9H3JPdTWcYyCvUsLhdV38HK9Iw4evguqkbKqhqpUYWJqZh4isz65+Jadf5lXSfBq8U0/UpFUWVVFpDCVmVuJRbxhShQcXEMtVlVXsTQ1loV1kaqGpoqFialCIrU0l8nF4ZyVzNR8oztVUhYpFBIVWypWJkamcpGSqrqq2NzETIaKqpKVzOyBprddT1WVwvmFSCLC6gFoS+q2tdQw1TcysVJVFsll5gqxkpLEQi4P1ylV0dRUVhgaGVuEYHtQp0rKKhILc0uRitRCJpNvbCypqojlZjLFN7xYX7nYKoCDOIDsTa8TpaB/LrOQqtmyJTE1Vki1NCSm+oYmViIxVm+AIhJLpeG3FQ0VK1MjU9kbkY0tRWpaDu0qy3Td6loEDNREsgexoaSirmRhaip3f+Xua/saY9FbFr2N11qIe2YQshUHP5ZWa0CXtezZkZjo6Fpgx46Vrv6m9sQa9mxb6Rrg0BM7cm2XbkKCUi2PPbUjc+3ORFXDXE/XSMm+Y3uWbl253eyp29GSGhuh6ZGmhY5rS7lYVcuBVrCvYyG175GWwp22zgN4pKEGLVGy45EduRttIxVNDYwNzULIKrYdOdLCwKW2ldSebbGJrp6xim27qjIdfbOQnPW+LTNtlzILJdv2lAx0TJCo27GnamYgk9pTM9Nxt7G4pOnQntTIrTujAJZF8IGKlvc0zdy4M1HS1LQwMHrwVkWqdh1qmLl1Z6hiz4lHSrquTVScOJDqOXdpLtewp2qoG3xaZ2PbgR1MzVXsaVroarvZADq15VDTzFDs0AeO1ExcimVyDYce2RYbaYtlFkg0HDrWlLl2rSuyZUddoa9vIla1rWJqECyKldXVLUxM5KjY9cxjdSNnzs0tNWyJTIzMSSXqDjzznpKBM0tTVb/2a0uf+0/jTej3fOzE0qlTuad+5ZHMS4WeXGQldeAXPnVo6pUzfdtaZi6sTDU895kTC6dig5DUsh3Pnai4cym34wP7ChcWJkYSDQeeOZQaKCuCpk8cyZ2KDYOmkh1HKnquDVFz4jOPzfzBwkzLM8e48koeamHFrhPv28ed2NJSzfsOpbrOzM3UHXvftqFTxQbQLSde2DZRkenINH3sMw2n/ssrJLadeGrLyJWxsueaxr6WG4SoVhx44amKO1/JTO060dRxpg/q3veZQ0NfKMxs+dALc//jywdATDQ987E9I18qDNUd+aUPlLU1dFV96onUnYpcV+SZ3zhw6j+83uipOfaJp1ZudaWO7CtciU2DPZQd+8yxvlN9+544UTeWGOuYaTn23IFEV8lCT4bErg99at/EH6xMpJ564cDMK1+aKDv2qV2Xfuc8RPnABx7Jfe2VDmqOfOIXmnqhVEaeeiJx5ZU7UrGqXUeeKOnJ9JS0/Mo/W8h9YRxahLI9z31oaalr7MATxzJTF9IH93vtzNTSQsWufRO5nkTdsY88V0jcehk0r6HxoZqmpZGWAwcKmRtlRCpaDh0rqZvpKGt64mNPzCU6XpmIrNS98BvbTv17APR7XnhqZu5M2673vRCpGugFQJdt2ffIPlIDPWNNx55INczc6ao79Nyunombjac1LftaJgYaEjR97J807bgKgG449FTTwMpA1YmWoanrDYDKdjzxvqotY1dGPvQvHvnKvwYANZz41GM9M+faGp77lZmhr8027Vtsy2MfOTAwdxmu6rEnKlIjsbonTpTU9F1JxZ75R0d2vH4L0J96YeXCuZXHDhVigzds3vfCMx0zhaqmprpYQ02qpGHPkffEKia6AR2pHU995NBY4dqlhhf+3rGxuoFzFSf+zpGXbgOgq574By9kPjfSCV499syWbUNnKsqe+aVEVXcN6Hv2VVVSVQ6Pdi6z+AY7jcRWYcC13HwP18ThS8KXKkmlYpFYSVlZEk6517nmyDU15VAjl2+1hIlS+FKJWKKipiYJe+6r3ZGP7Ip9udEdicNILlZS0xCpKW9Oj4OVKdKgfc1qSypKko2eNwd7KwuFudxcETj5mn2ubbw/P5EohSYpDg1o/EBTFGJUVpKKVRz7xJGS/95YmG68X/PNqZGZ7K3m+P70tZ57brxmluuWsBRykYZmtjCTvcXbE1UNW1a21OUqKiFfyebyrAJPz+QKuUwmlpmHTiEJeY6VlULfstZdVlFRqEglqna85z0TNxobfEUP4pPaceSJmSv1jZ/RG+tiqbL0PlepldzE0EDJwEim0PO5uYXfmRDcyPW8trLwWl+m7ZWJuTPdTUgWhm5cyk1dudW3sjLRNbU0c+tconCh82DPRFdb1a2evrlrc4W2voxg30BNSd9QpjDT1Zaaaxu8oakvNghsL9P2lczMa32FkbaaSNto0xnkZkYGUgwMTc1N9dWlesbmVqbunBkYuts88rmRtqq+mctQ74de2tbwMtTxpamOa1MDd4bKrkwMdUw3AMqN3NlSdatrpjDQlrgxCSumrnxlYuDcyMrQ7w0Vzsw3uWFl4sZrk0BvyHSdKylraxtaulVVcqdnZGHmK/9mz2tXDwCd6wd4tXUsNaQKfaMHxS1z7bduDb02lroSqZm40jW1kBkbqIoNjM3CxVsau3WlMA5ZK0yMDE2MZJg797k9F5t3cGGk485ML0R+rufKti191/pyS1eqEhdGa0Cvw34mkxq6NlCY+tzvMX3A0nJ3vnBlpatn4UyhJXcbWsIVCre+VNg1c+3WVNeNzK2ewtjXUteWLpwHsDLXdWqirKdtqqwIjcitWYBpR9lUYuTawNzAK4kruXMXm8ROfCXWdBGex4lzC1+bu9GV63qpjzudDaAzPZcSffRc6hjKfW0i0dc2tjR2IVMzc7fpKOb6zszUzHVCWzrwWzfKeiEhhYFzuZqpjpnEXN3U7YZBkwXyVTJwYWTqD2K7rjY0YOhUbsfEub6ViVPnVpsu4D71A68UmqYu9cJFSPWVddyaGyoZSHWdupMrvHYjNX9wvdYxq7ix0tOXmOlYuHG9hktAwrWpusxUYikxVJa5dWOsMNRWNhbru9IPdha6XlraNXGmbWbolbq2qZfukLkwVjHZsPWZC5+7k3mpE+y7UjXWMPRaW2blVEdsqAfRKlaxZdeWxEzP4EH9eiiRKDymhaWVkrLUUi5XbJhcTVNLTWFkqlBSsjQxlYmV1ZQxezC2i5U11MWyMOirqVjKTMzlIlVbtm2JZfqGpiJNLXULI/3NWGhNXpIwpCMKD9FKIbcUK0lRyDce1jTtOwjTj1tdI7FtdbGZoYlpoArxZqq6PitRVgo/nW8i8GbESmrqUnmoUzWphYmZeViTKmtoSGRGpuYSVbEizAbun9TEMpCbb5Nkk5HM3EKspKIikiukGmFStPZy4JsDwrU9tTALmluoaKlbGrrT31zmhx5WwvpEYWxkgi079m2LjHV0dc0JeWypyg0MzaRaDjQUOu4M34m5ckDDzFSBkpqm7TC2G5q8HZFoZcPt1oPwYsNdvSNJP4bc28fqgX3fl+41g13P1+dyxQayPw3v3yV/um1xYPeRhXzD+tdc9d26otBbJFZhz7f/QeuhnvuOJyVM7vMfMpJ/yV8K/1g4/viev95V+aZNb17MP/+avgtEf04EvstJb2v9rue8ve6vHe0fQv5EH/4P0D+divxt8termX8Lif8u8qdfwD/3yv5oEf2p/S/Hz/Kz/EXyvxF/bq+buqLKAAAAAElFTkSuQmCC";function Zt(n){let t=ue(n,.8,.13),e=ue(n,.66,.12);return`radial-gradient(circle at 38% 34%, rgba(255,255,255,.55) 0%, rgba(255,255,255,0) 34%), radial-gradient(circle at 50% 50%, ${t} 0%, ${t} 38%, ${e} 62%, transparent 76%)`}function fe(n,t=!1){return qt(n,t)}function Ds(n){let t=`molecule.genre_desc.${n}`,e=a(t);return e===t?"":e}var Fs={pure:fe([1,0,0,0]),blend:fe([.62,.3,.05,.03]),even:fe([.25,.25,.25,.25])};function Xt(n){return n.base_mix??[]}var Qt={overexpressed:{c:"#e0a23c",bg:"rgba(224,162,60,.10)",bd:"rgba(224,162,60,.42)"},stable:{c:"#4ad48a",bg:"rgba(74,212,138,.10)",bd:"rgba(74,212,138,.42)"},underexpressed:{c:"#5fa8e8",bg:"rgba(95,168,232,.10)",bd:"rgba(95,168,232,.42)"},unmeasured:{c:"#8b9099",bg:"rgba(139,144,153,.10)",bd:"rgba(139,144,153,.38)"}},Bs={overexpressed:"over",stable:"stable",underexpressed:"under",unmeasured:"unmeasured"},Vs=["overexpressed","stable","underexpressed","unmeasured"];function es(n){return a(`molecule.status_${n}`)}var R=34,ts=new Map;function Ks(n){let t=ts.get(n);if(t)return t;if(typeof document>"u")return null;let e=document.createElement("canvas");e.width=e.height=R;let s=e.getContext("2d");if(!s)return null;let i=s.createRadialGradient(R/2,R/2,0,R/2,R/2,R/2);return i.addColorStop(0,n),i.addColorStop(.45,n),i.addColorStop(1,"transparent"),s.fillStyle=i,s.beginPath(),s.arc(R/2,R/2,R/2,0,Math.PI*2),s.fill(),ts.set(n,e),e}function He(n,t,e,s,i,r){if(r<=.004)return;let o=Ks(i);if(!o)return;n.globalAlpha=Math.min(1,r);let p=s*4;n.drawImage(o,t-p/2,e-p/2,p,p)}var G=Gt(),qs=16,Ws=13,je=60;function ss(n,t){return!n||!t?n===t:n.rungIndex===t.rungIndex&&n.legKey===t.legKey}var De=class extends f{constructor(){super(...arguments);this.genres=[];this.bases=[];this.totalListens=0;this._hovered=null;this._pinned=null;this._hitTargets=[];this._popover=null;this._bases=[];this._ordered=[];this._orderedRank=new Map;this._pairs=new Map;this._bands=[];this._legColors=[];this._rungPaint=new Map;this._phase=0;this._raf=null;this._lastFrame=0;this._lastTargetsAt=0;this._reduceMotion=!1;this._pageHidden=!1;this._inView=!0;this._motionQuery=null;this._ctx=null;this._resizeObserver=null;this._intersectionObserver=null;this._onVisibility=()=>{this._pageHidden=document.visibilityState==="hidden",this._syncLoop()};this._onMotionPreference=e=>{this._reduceMotion=e.matches,this._syncLoop()};this._frame=e=>{if(this._raf=null,!this._spinning)return;let s=Math.min(.05,Math.max(0,e-this._lastFrame)/1e3);this._lastFrame=e,this._phase+=zt*s,e-this._lastTargetsAt>250&&(this._lastTargetsAt=e,this._refreshHitTargets()),this._draw(),this._raf=requestAnimationFrame(this._frame)};this._clearHover=()=>{this._hovered=null};this._onPointerMove=e=>{let s=this._toPlate(e);if(!s)return;let i=this._pick(s.x,s.y);i?this._setHover(i):this._clearHover()};this._onClick=e=>{let s=this._toPlate(e);if(!s)return;let i=this._pick(s.x,s.y);i&&this._togglePin(i)};this._onDocumentPointerDown=e=>{if(!this._popover)return;e.composedPath().some(r=>r instanceof HTMLElement&&r.dataset&&r.dataset.popover===this._popover)||(this._popover=null)};this._onPopoverKey=e=>{if(e.key!=="Escape"||!this._popover)return;let s=this._popover;this._popover=null,this.renderRoot.querySelector(`[data-popover="${s}"] > button`)?.focus()}}static{this.properties={genres:{attribute:!1},bases:{attribute:!1},totalListens:{attribute:!1},_hovered:{state:!0},_pinned:{state:!0},_hitTargets:{state:!0},_popover:{state:!0}}}get _active(){return this._hovered??this._pinned}get _spinning(){return!this._pageHidden&&this._inView&&!this._reduceMotion&&this._active===null}connectedCallback(){super.connectedCallback(),document.addEventListener("visibilitychange",this._onVisibility),document.addEventListener("pointerdown",this._onDocumentPointerDown),this._onVisibility(),typeof window.matchMedia=="function"&&(this._motionQuery=window.matchMedia("(prefers-reduced-motion: reduce)"),this._reduceMotion=this._motionQuery.matches,this._motionQuery.addEventListener?.("change",this._onMotionPreference)),this.hasUpdated&&this._attachObservers()}disconnectedCallback(){super.disconnectedCallback(),this._stopLoop(),this._resizeObserver?.disconnect(),this._resizeObserver=null,this._intersectionObserver?.disconnect(),this._intersectionObserver=null,document.removeEventListener("visibilitychange",this._onVisibility),document.removeEventListener("pointerdown",this._onDocumentPointerDown),this._motionQuery?.removeEventListener?.("change",this._onMotionPreference)}willUpdate(e){(e.has("genres")||e.has("bases")||!this.hasUpdated)&&this._derive()}firstUpdated(){this._ctx=this._canvas?.getContext("2d")??null,this._attachObservers(),this._refreshHitTargets()}updated(e){(e.has("_hovered")||e.has("_pinned"))&&this._refreshHitTargets(),(e.has("genres")||e.has("bases"))&&this._refreshHitTargets(),(e.has("_hovered")||e.has("_pinned")||e.has("genres")||e.has("bases"))&&(this._draw(),this._syncLoop())}_attachObservers(){let e=this._plate;e&&(typeof ResizeObserver<"u"&&!this._resizeObserver&&(this._resizeObserver=new ResizeObserver(()=>this._resizeCanvas()),this._resizeObserver.observe(e)),typeof IntersectionObserver<"u"&&!this._intersectionObserver&&(this._intersectionObserver=new IntersectionObserver(s=>{this._inView=s.some(i=>i.isIntersecting),this._syncLoop()}),this._intersectionObserver.observe(e)),this._resizeCanvas(),this._syncLoop())}get _canvas(){return this.renderRoot.querySelector("canvas")}get _plate(){return this.renderRoot.querySelector(".genome-plate")}_derive(){let e=Array.isArray(this.genres)?this.genres:[],s=Array.isArray(this.bases)?this.bases:[];this._bases=s;let i=Ut(e,s),r=Ot(i,Le),o=new Set(r.map(c=>c.key)),p=i.filter(c=>!o.has(c.key)).sort((c,h)=>h.share-c.share);this._ordered=[...r,...p],this._orderedRank=new Map(this._ordered.map((c,h)=>[c.key,h])),this._pairs=jt(G.rungs,this._ordered),this._bands=It(s),this._legColors=G.legs.map(c=>this._legColor(c.t)),this._rungPaint=new Map;for(let c of G.rungs){let h=this._pairs.get(c.index),m=h!==void 0&&o.has(h.key),u=h?fe(Xt(h),!m):K;this._rungPaint.set(c.index,{genre:h,color:u,isLit:m})}}_legColor(e){let s=this._bands;if(s.length===0)return K;let{index:i,next:r,mix:o}=Ht(s,e),p=$[s[i].baseIndex%$.length],c=r===-1?p:Oe(p,$[s[r].baseIndex%$.length],o);return E(.78,.075,c)}_draw(){let e=this._ctx,s=this._canvas;if(!e||!s)return;e.setTransform(1,0,0,1,0,0),e.clearRect(0,0,s.width,s.height);let i=s.width/540;e.setTransform(i,0,0,i,0,0),e.globalCompositeOperation="lighter";let r=this._phase,o=this._active;G.legs.forEach((p,c)=>{let{x:h,y:m,depth:u}=x(p.t,p.leg,r,p.dTheta,p.dRadius,p.dY),g=o?.legKey===p.leg;He(e,h,m,p.size*(.6+.5*u)*(g?1.2:1),this._legColors[c]??K,p.gain*(.1+.95*u)*(g?.9:.46))});for(let p of G.rungs){let c=this._rungPaint.get(p.index),h=c?.isLit??!1,m=c?.color??K,u=o?.rungIndex===p.index;for(let g of p.particles){let _=x(p.t,0,r,0,g.dRadius,g.dY),k=x(p.t,1,r,0,g.dRadius,g.dY),ie=_.x+(k.x-_.x)*g.f,ne=_.y+(k.y-_.y)*g.f,U=_.depth+(k.depth-_.depth)*g.f,W=g.gain*(.1+.95*U);h&&He(e,ie,ne,g.size*3.4,m,W*(u?.3:.15)),He(e,ie,ne,g.size*(.55+.5*U)*(u?1.3:h?1:.85),m,W*(h?.92:.3)*(u?1.7:1))}}e.globalCompositeOperation="source-over",e.globalAlpha=1}_resizeCanvas(){let e=this._canvas,s=this._plate;if(!e||!s)return;let i=Math.min(2,window.devicePixelRatio||1),r=Math.max(1,Math.round(s.clientWidth*i)),o=Math.round(r*700/540);(e.width!==r||e.height!==o)&&(e.width=r,e.height=o),this._draw()}_syncLoop(){let e=this.isConnected&&this._spinning&&typeof requestAnimationFrame=="function";e&&this._raf===null?(this._lastFrame=performance.now(),this._raf=requestAnimationFrame(this._frame)):e||this._stopLoop()}_stopLoop(){this._raf!==null&&cancelAnimationFrame(this._raf),this._raf=null}_setHover(e){ss(this._hovered,e)||(this._hovered=e)}_togglePin(e){this._pinned=ss(this._pinned,e)?null:e}_toPlate(e){let s=this._plate;if(!s)return null;let i=s.getBoundingClientRect();if(i.width===0)return null;let r=540/i.width;return{x:(e.clientX-i.left)*r,y:(e.clientY-i.top)*r}}_pick(e,s){let i=this._phase,r=null,o=Number.POSITIVE_INFINITY;for(let p of G.rungs){if(!this._pairs.has(p.index))continue;let c=x(p.t,0,i),h=x(p.t,1,i),m=Ne(e,s,c.x,c.y,h.x,h.y);m<o&&m<qs&&(o=m,r={rungIndex:p.index})}for(let p of[0,1])for(let c=0;c<je;c++){let h=x(c/je,p,i),m=x((c+1)/je,p,i),u=Ne(e,s,h.x,h.y,m.x,m.y);u<o&&u<Ws&&(o=u,r={legKey:p})}return r}_onHitKey(e,s){(e.key==="Enter"||e.key===" ")&&(e.preventDefault(),this._togglePin(s))}_refreshHitTargets(){let e=this._phase,s=[],i=this._bases.length?a("molecule.leg_aria",{count:this._bases.length}):a("molecule.leg_aria_empty");for(let r of[0,1]){let o=x(0,r,e),p=x(1,r,e);s.push({key:`leg-${r}`,kind:"leg",x1:o.x,y1:o.y,x2:p.x,y2:p.y,label:i,active:{legKey:r}})}for(let r of G.rungs){let o=this._pairs.get(r.index);if(!o)continue;let p=x(r.t,0,e),c=x(r.t,1,e);s.push({key:`rung-${r.index}`,kind:"rung",x1:p.x,y1:p.y,x2:c.x,y2:c.y,label:a("molecule.rung_aria",{label:o.label,percent:L(o.share),status:es(ze(o.ratio,o.baseline_known))}),active:{rungIndex:r.index}})}this._hitTargets=s}_togglePopover(e){this._popover=this._popover===e?null:e}_hudInfo(){let e=this._active;if(!e)return null;let s=this._bases;if(e.legKey!==void 0){let h=x(.5,e.legKey,this._phase),m=s.reduce((g,_)=>g+_.share,0),u=m>0?s.map(g=>g.share/m):[];return{code:"BKB",title:a("molecule.backbone_label"),desc:s.length?a("molecule.backbone_desc",{plays:D(this.totalListens??0)}):a("molecule.backbone_desc_empty"),mix:u,mixLabels:s.map(g=>g.label),mixKnown:u.length>0,status:null,anchor:{x:h.x,y:h.y}}}let i=G.rungs.find(h=>h.index===e.rungIndex),r=i?this._pairs.get(i.index):void 0;if(!i||!r)return null;let o=x(i.t,0,this._phase),p=x(i.t,1,this._phase),c=Xt(r);return{code:Vt(this._orderedRank.get(r.key)??0),title:r.label,desc:a("molecule.share_of_listening",{percent:L(r.share),plays:D(Ft(r.share,this.totalListens??0))}),mix:c,mixLabels:s.map(h=>h.label),mixKnown:c.length>0,status:ze(r.ratio,r.baseline_known),anchor:{x:(o.x+p.x)/2,y:(o.y+p.y)/2}}}_hudBarGradient(e){return`linear-gradient(90deg, ${Dt(e.mix,i=>ue(i,.7)).map(i=>`${i.color} ${i.offsetPercent.toFixed(1)}%`).join(",")})`}_renderHud(e,s){let i=e.status?Qt[e.status]:null;return l`<div
      class="genome-hud on"
      style="--hud-top-fr: ${s}"
      aria-hidden="true"
    >
      <div class="genome-hud__code">${e.code}</div>
      <div class="genome-hud__panel">
        <div class="genome-hud__title">${e.title}</div>
        <div class="genome-hud__desc">${e.desc}</div>
        <div class="genome-hud__bar">
          ${e.mixKnown?l`<div
                class="genome-hud__bar-fill"
                style="background: ${this._hudBarGradient(e)}"
              ></div>`:l`<div class="genome-hud__bar-fill genome-hud__bar-fill--neutral"></div>`}
        </div>
        ${e.mixKnown?l`<div class="genome-hud__mix">
              ${e.mix.map((r,o)=>l`<span>
                    <span class="genome-hud__dot" style="background: ${Zt(o)}"></span>
                    ${e.mixLabels[o]}
                  </span>
                  <b>${Math.round(r*100)}%</b>`)}
            </div>`:l`<div class="genome-hud__mix-unknown">${a("molecule.mix_unknown")}</div>`}
        ${e.status&&i?l`<div class="genome-hud__foot">
              <span
                class="genome-hud__status"
                style="color: ${i.c}; background: ${i.bg}; border-color: ${i.bd}"
                >${es(e.status)}</span
              >
            </div>`:d}
      </div>
    </div>`}_renderPopover(e,s,i){let r=this._popover===e;return l`<div class="popover-anchor" data-popover=${e}>
      <button
        type="button"
        class="genome-legend-trigger"
        aria-haspopup="dialog"
        aria-expanded=${r?"true":"false"}
        aria-controls="popover-${e}"
        @click=${()=>this._togglePopover(e)}
      >
        ${s}
      </button>
      ${r?l`<div
            id="popover-${e}"
            class="popover popover--${e}"
            role="dialog"
            aria-label=${s}
          >
            ${i}
          </div>`:d}
    </div>`}render(){let e=this._bases,s=this._hudInfo(),i=s?s.anchor:null,r=i?Math.max(.01,i.y/700-.06):0;return l`<section class="panel">
      <div>
        <h2 class="panel-title">${a("molecule.title")}</h2>
        <p class="panel-description">${a("molecule.subtitle")}</p>
      </div>
      <!-- container-type makes the layout respond to the CARD's width, not the viewport's -
           the page has a sidebar, so those are not the same number. -->
      <div class="genome-shell" @keydown=${this._onPopoverKey}>
        <div class="genome-stage">
          <div
            class="genome-plate"
            @pointermove=${this._onPointerMove}
            @pointerleave=${this._clearHover}
            @click=${this._onClick}
          >
            <canvas class="genome-plate__canvas"></canvas>
            <svg
              class="genome-plate__svg"
              viewBox="0 0 ${540} ${700}"
              role="group"
              aria-label=${a("molecule.svg_aria")}
            >
              ${i?v`<g class="genome-reticle">
                    <circle cx=${i.x} cy=${i.y} r="13" fill="none" stroke="#fff"
                      stroke-width="1.1" opacity=".85" />
                    <circle cx=${i.x} cy=${i.y} r="6" fill="none" stroke="#fff"
                      stroke-width="1.1" opacity=".95" />
                    <circle cx=${i.x} cy=${i.y} r="1.8" fill="#fff" />
                    <line class="genome-leader" x1=${i.x-13} y1=${i.y} x2="-12"
                      y2=${r*700+24} stroke="#fff" stroke-width="1"
                      opacity=".55" />
                  </g>`:d}
              ${this._hitTargets.map(o=>v`<line
                    class="genome-hit"
                    x1=${o.x1}
                    y1=${o.y1}
                    x2=${o.x2}
                    y2=${o.y2}
                    stroke="transparent"
                    stroke-width=${o.kind==="leg"?26:20}
                    stroke-linecap="round"
                    tabindex="0"
                    role="button"
                    aria-label=${o.label}
                    @focus=${()=>this._setHover(o.active)}
                    @blur=${this._clearHover}
                    @keydown=${p=>this._onHitKey(p,o.active)}
                  />`)}
            </svg>
          </div>

          <!-- The callout lives in the stage, not the plate: on a wide card it sits in its own
               lane beside the molecule, and only overlays the molecule when the card is too
               narrow to give it a lane of its own. -->
          ${s?this._renderHud(s,r):d}

          <div class="genome-panel">
            <h3 class="genome-panel__heading">${a("molecule.bases_heading")}</h3>
            <p class="genome-panel__sub">${a("molecule.bases_subtitle")}</p>
            ${e.length===0?l`<p class="genome-panel__empty">${a("molecule.no_bases")}</p>`:l`<div class="genome-panel__rows">
                  ${e.map((o,p)=>{let c=Ds(o.key);return l`<div class="genome-baserow">
                      <div class="genome-baserow__id">
                        <span class="genome-baserow__dot" style="background: ${Zt(p)}"></span>
                        <div>
                          <div class="genome-baserow__label">${o.label}</div>
                          <div class="genome-baserow__code">${Bt(o.key)}</div>
                        </div>
                      </div>
                      <div class="genome-baserow__share">${L(o.share)}</div>
                      ${c?l`<div class="genome-baserow__desc">${c}</div>`:d}
                    </div>`})}
                </div>`}
            <p class="genome-panel__foot">${a("molecule.backbone_explainer")}</p>

            <div class="genome-panel__actions">
              ${this._renderPopover("legend",a("molecule.legend_heading"),l`<div class="genome-legend">
                  ${Vs.map(o=>l`<p class="genome-legend__row">
                      <span
                        class="genome-legend__swatch"
                        style="background: ${Qt[o].c}"
                      ></span>
                      <span>${a(`molecule.legend_${Bs[o]}`)}</span>
                    </p>`)}
                  <p class="genome-legend__note">${a("molecule.legend_note")}</p>
                </div>`)}
              ${this._renderPopover("mix",a("molecule.mix_heading"),l`<div class="genome-legend">
                  <p class="genome-legend__lead">${a("molecule.mix_lead")}</p>
                  ${["pure","blend","even"].map(o=>l`<p class="genome-legend__row">
                      <span
                        class="genome-legend__swatch"
                        style="background: ${Fs[o]}"
                      ></span>
                      <span>${a(`molecule.mix_${o}`)}</span>
                    </p>`)}
                  <p class="genome-legend__note">${a("molecule.mix_note")}</p>
                </div>`)}
            </div>
          </div>
        </div>

        <p class="genome-hint">${a("molecule.hint")}</p>
      </div>
    </section>`}static{this.styles=[y,w,b`
      :host {
        display: block;
        --bar-mask: url("${ae(Yt)}");
      }
      .genome-shell {
        container-type: inline-size;
      }
      .genome-hint {
        margin-top: 8px;
        text-align: center;
        font-size: 11px;
        color: var(--genome-muted);
      }

      /* One dark panel spanning the card. The plate, the callout and the base-pair list all
         live inside it, so the space to the right of the molecule is used rather than left as
         an empty margin with content stranded outside the box. */
      .genome-stage {
        /* cqi, not vw: the plate should scale with the CARD, which is what the container
           query below establishes - the page has a sidebar, so vw would undersize it. */
        --stage-h: clamp(380px, 62cqi, 660px);
        /* The plate's aspect ratio is fixed, so its rendered width follows from the stage
           height - which is what lets the callout lanes be plain calc(). */
        --plate-w: calc(var(--stage-h) * 540 / 700);
        --stage-pad: 18px;
        --panel-w: clamp(170px, 20cqi, 230px);
        --lane-gap: 22px;
        position: relative;
        /* Three columns: a callout lane, the molecule, a callout lane. The molecule sits in
           the middle of the card rather than hard left, and the space on both sides is a
           place for information rather than margin. */
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        align-items: stretch;
        height: var(--stage-h);
        padding: var(--stage-pad);
        border-radius: 10px;
        /* The molecule is light on darkness, so the panel carries its own ground rather
           than inheriting the theme's. */
        background: #06070a;
      }
      .genome-plate {
        position: relative;
        grid-column: 2;
        height: 100%;
        aspect-ratio: 540 / 700;
      }
      .genome-plate__canvas,
      .genome-plate__svg {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
      }
      .genome-plate__svg {
        overflow: visible;
      }

      .genome-panel {
        grid-column: 3;
        /* Nearer the molecule than the card's edge: pinned to the far right it read as a
           separate sidebar rather than a legend belonging to the thing beside it. */
        justify-self: start;
        margin-left: var(--lane-gap);
        width: var(--panel-w);
        align-self: start;
        /* Never taller than the plate it floats on: with four base descriptions the panel
           outgrew the plate and its triggers ended up below the artwork. */
        max-height: calc(100% - 24px);
        display: flex;
        flex-direction: column;
        gap: 0;
        padding: 14px 15px 13px;
        background: rgba(255, 255, 255, 0.035);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
      }
      .genome-panel__actions {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      /* Bounding the ROWS rather than the panel keeps the heading, the explainer and both
         triggers visible at all times - the part that scrolls is the part that is a list. It
         takes whatever height the panel has left and scrolls beyond that, bounding itself
         against the plate rather than a guessed max-height. */
      .genome-panel__rows {
        flex: 1 1 auto;
        min-height: 0;
        overflow-y: auto;
        margin-top: 8px;
      }
      .genome-panel__heading {
        margin: 0;
        font-family: var(--genome-text);
        font-weight: 600;
        font-size: 11px;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        color: #8f939d;
      }
      .genome-panel__sub {
        margin-top: 2px;
        font-size: 11px;
        color: #71757e;
      }
      .genome-panel__empty,
      .genome-panel__foot {
        margin-top: 12px;
        font-size: 11px;
        line-height: 1.45;
        color: #71757e;
      }

      .genome-hit {
        cursor: pointer;
      }
      .genome-hit:focus {
        outline: none;
      }
      .genome-hit:focus-visible {
        outline: 2px solid #fff;
        outline-offset: 2px;
      }
      .genome-reticle {
        transition: opacity 0.12s ease;
        pointer-events: none;
      }

      .genome-hud {
        position: absolute;
        pointer-events: none;
        z-index: 8;
        width: clamp(190px, 22cqi, 290px);
        top: min(
          calc(var(--stage-pad) + var(--hud-top-fr) * var(--stage-h)),
          calc(100% - 230px)
        );
        /* The left lane, always. Choosing a side from the reticle looked appealing but is
           degenerate: a rung spans both strands, so its midpoint sits on the axis whichever
           rung it is, and the callout would have flipped on noise. A fixed side also means
           the panel never moves between two rungs, which matters more than symmetry. */
        right: calc(50% + var(--plate-w) / 2 + var(--lane-gap));
      }
      /* The code tab sits at the panel's top-right now that the callout is in the left lane,
         so it points back toward the molecule. */
      .genome-hud__code {
        display: block;
        width: fit-content;
        margin-left: auto;
        margin-bottom: -1px;
        padding: 4px 9px;
        background: rgba(12, 14, 18, 0.94);
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-bottom: 0;
        border-radius: 4px 4px 0 0;
        font:
          600 10px/1 ui-monospace,
          SFMono-Regular,
          Menlo,
          monospace;
        letter-spacing: 0.16em;
        color: #c9cdd6;
      }
      .genome-hud__panel {
        padding: 12px 13px 11px;
        background: rgba(10, 12, 15, 0.94);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 0 4px 4px 4px;
      }
      .genome-hud__title {
        font: 600 12.5px/1.25 var(--genome-display);
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #fff;
      }
      .genome-hud__desc {
        font-family: var(--genome-text);
        font-size: 11px;
        color: #8f939d;
        margin-top: 3px;
        line-height: 1.35;
      }
      .genome-hud__bar {
        display: flex;
        /* Taller than a plain progress bar needs to be: it is masked by the speck texture,
           and specks need room to read as specks. */
        height: 15px;
        margin: 9px 0 2px;
      }
      .genome-hud__bar-fill {
        flex: 1;
        mask-image: var(--bar-mask);
        -webkit-mask-image: var(--bar-mask);
        /* auto width, not 100%: stretching the strip to the bar's width squashes every
           bubble into a tall oval. Tiling keeps them round at any bar width. */
        mask-size: auto 100%;
        -webkit-mask-size: auto 100%;
        mask-repeat: repeat-x;
        -webkit-mask-repeat: repeat-x;
      }
      .genome-hud__bar-fill--neutral {
        background: hsl(220 6% 40%);
      }
      .genome-hud__mix {
        margin-top: 10px;
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 3px 10px;
        font-size: 10.5px;
        color: #b9bcc6;
      }
      .genome-hud__mix b {
        color: #fff;
        font-weight: 600;
      }
      .genome-hud__mix-unknown {
        margin-top: 10px;
        font-size: 10.5px;
        color: #b9bcc6;
        font-style: italic;
      }
      .genome-hud__dot {
        display: inline-block;
        width: 11px;
        height: 11px;
        margin-right: 5px;
        vertical-align: -1px;
      }
      .genome-hud__foot {
        display: flex;
        justify-content: flex-end;
        margin-top: 11px;
      }
      .genome-hud__status {
        padding: 5px 11px;
        border-radius: 4px;
        font:
          600 10px/1 ui-monospace,
          Menlo,
          monospace;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        border: 1px solid transparent;
      }

      .genome-baserow {
        /* A grid rather than a flex row, so the description can span the full width
           underneath instead of sharing a line with the share figure. */
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 2px 8px;
        padding: 8px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.07);
      }
      .genome-baserow:last-of-type {
        border-bottom: 0;
      }
      .genome-baserow__id {
        display: flex;
        align-items: center;
        gap: 9px;
        min-width: 0;
      }
      .genome-baserow__id > div {
        min-width: 0;
      }
      .genome-baserow__label {
        font-size: 12.5px;
        color: #e7e9ee;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .genome-baserow__share {
        font-size: 12.5px;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        color: #fff;
      }
      .genome-baserow__dot {
        display: inline-block;
        width: 15px;
        height: 15px;
        flex-shrink: 0;
      }
      .genome-baserow__desc {
        grid-column: 1 / -1;
        /* Aligned under the label, not under the dot: the dot belongs to the row, the
           description belongs to the name. */
        padding-left: 24px;
        font-size: 11px;
        line-height: 1.45;
        letter-spacing: 0.01em;
        color: #757982;
      }
      .genome-baserow__code {
        font:
          600 9px/1 ui-monospace,
          Menlo,
          monospace;
        letter-spacing: 0.14em;
        color: #71757e;
        text-transform: uppercase;
        margin-top: 2px;
      }

      /* ---- the two explainers: a trigger and a small popover above it ---------------- */
      /* The popovers hang off the actions row rather than their own trigger, so both open
         to the same edge and stay inside the card whichever trigger opened them. */
      .genome-panel__actions {
        position: relative;
      }
      .genome-legend-trigger {
        margin-top: 10px;
        padding: 0 0 1px;
        font: 600 9.5px/1 var(--genome-mono);
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #8f939d;
        border: 0;
        border-bottom: 1px dotted rgba(255, 255, 255, 0.3);
        cursor: pointer;
        background: none;
      }
      .genome-legend-trigger:hover,
      .genome-legend-trigger[aria-expanded="true"] {
        color: #c3c7d0;
      }
      .genome-legend-trigger:focus-visible {
        outline: 1px solid var(--genome-accent);
        outline-offset: 3px;
      }
      .popover {
        position: absolute;
        bottom: calc(100% + 8px);
        /* Wide: the panel sits right of the molecule, so open leftward, over the plate. */
        right: 0;
        z-index: 20;
        width: 18rem;
        padding: 16px;
        text-align: left;
        background: #0c0f15;
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 6px;
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.55);
      }
      .popover--mix {
        width: 20rem;
      }
      .genome-legend {
        display: flex;
        flex-direction: column;
        gap: 9px;
      }
      .genome-legend__row {
        display: grid;
        grid-template-columns: 9px 1fr;
        gap: 9px;
        align-items: start;
        font-family: var(--genome-text);
        font-size: 11.5px;
        line-height: 1.4;
        color: #c3c7d0;
      }
      .genome-legend__swatch {
        width: 9px;
        height: 9px;
        border-radius: 2px;
        margin-top: 3px;
      }
      .genome-legend__note {
        font-family: var(--genome-text);
        font-size: 10.5px;
        line-height: 1.4;
        color: #767b85;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        padding-top: 8px;
      }
      .genome-legend__lead {
        font-family: var(--genome-text);
        font-size: 11.5px;
        line-height: 1.5;
        color: hsl(210 12% 74%);
        margin-bottom: 2px;
      }

      /* Narrow: no room for a lane either side. One column, and the callout stops floating
         entirely - it becomes a block under the molecule. Overlaying it on a small plate hid
         the thing it was describing. The reticle still marks the spot. */
      @container (max-width: 860px) {
        .genome-stage {
          --stage-h: auto;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 18px;
          height: auto;
        }
        .genome-plate {
          order: 1;
          width: 100%;
          max-width: 420px;
          height: auto;
        }
        .genome-hud {
          order: 2;
          position: static;
          width: 100%;
          max-width: 420px;
          left: auto;
          right: auto;
        }
        .genome-hud__code {
          margin-left: 0;
        }
        .genome-panel {
          order: 3;
          width: 100%;
          max-width: 420px;
          max-height: none;
          margin-left: 0;
          justify-self: stretch;
        }
        .genome-leader {
          display: none;
        }
        /* Narrow: the panel is the full width of the stage, so the popover takes that width. */
        .popover,
        .popover--mix {
          left: 0;
          right: 0;
          width: auto;
        }
      }
    `]}};customElements.get("lg-molecule")||customElements.define("lg-molecule",De);var Js=.032,se=64,os=92,Ys=1.75,Zs=17,Fe=10,is=os-10,ns=46,Xs=2,rs=9*Math.PI/180;function Qs(){let n=11,t=()=>(n=Math.imul(n,1664525)+1013904223>>>0,n/4294967296),e=[];for(let s=0;s<ns;s++)for(let i of[0,1])for(let r=0;r<Xs;r++)e.push({t:s/ns,leg:i,dR:(t()-.5)*3.2,dY:(t()-.5)*2.4,size:.9+t()*1.5,gain:.45+t()*.75});return e}var ei=Qs(),ti=typeof window<"u"&&typeof window.matchMedia=="function"?window.matchMedia("(prefers-reduced-motion: reduce)"):null,Be=class extends f{constructor(){super(...arguments);this.hue=195;this.intensity=.6;this._ctx=null;this._raf=null;this._last=0;this._phase=0;this._frame=e=>{let s=Math.min(.05,(e-this._last)/1e3);this._last=e,!document.hidden&&!ti?.matches&&(this._phase+=Js*s),this._draw(),this._raf=requestAnimationFrame(this._frame)}}static{this.properties={hue:{type:Number},intensity:{type:Number}}}static{this.styles=b`
    :host {
      /* 64 x 92 internally, so this keeps the aspect exactly rather than squashing the
         helix a fraction narrower than the one in the plate. */
      display: block;
      width: 44px;
      height: 63px;
      flex: 0 0 auto;
      opacity: 0.9;
      pointer-events: none;
    }
    canvas {
      display: block;
      width: 100%;
      height: 100%;
    }
  `}render(){return l`<canvas role="presentation" aria-hidden="true"></canvas>`}firstUpdated(){let e=this._canvas;e&&(this._ctx=e.getContext("2d")),this._resize(),this._start()}connectedCallback(){super.connectedCallback(),this._ctx&&this._start()}disconnectedCallback(){super.disconnectedCallback(),this._raf!==null&&cancelAnimationFrame(this._raf),this._raf=null}updated(e){(e.has("hue")||e.has("intensity"))&&this._draw()}get _canvas(){return this.renderRoot.querySelector("canvas")}_start(){this._raf!==null||typeof requestAnimationFrame!="function"||(this._last=performance.now(),this._raf=requestAnimationFrame(this._frame))}_resize(){let e=this._canvas;if(!e)return;let s=Math.min(2,window.devicePixelRatio||1);e.width=Math.round(se*s),e.height=Math.round(os*s),this._draw()}_draw(){let e=this._canvas,s=this._ctx;if(!s||!e)return;let i=e.width/se;s.setTransform(1,0,0,1,0,0),s.clearRect(0,0,e.width,e.height),s.setTransform(i,0,0,i,0,0),s.globalCompositeOperation="lighter";for(let r of ei){let o=this._phase+2*Math.PI*Ys*r.t+(r.leg?Math.PI:0),p=Zs+r.dR,c=se/2+p*Math.cos(o),h=Fe+r.t*(is-Fe)+r.dY,m=(Fe+is)/2,u=Math.cos(rs),g=Math.sin(rs),_=c-se/2,k=h-m,ie=se/2+_*u-k*g,ne=m+_*g+k*u,U=(Math.sin(o)+1)/2,W=r.gain*(.12+.85*U)*(.62+.38*this.intensity);if(W<=.01)continue;let ys=Ue-.1+.08*U,xs=.05+.075*U;s.fillStyle=E(ys,xs,this.hue,Math.min(1,W)),s.beginPath(),s.arc(ie,ne,r.size*(.6+.6*U),0,Math.PI*2),s.fill()}s.globalCompositeOperation="source-over"}};customElements.get("lg-gene-glyph")||customElements.define("lg-gene-glyph",Be);function as(n){return typeof n=="number"&&Number.isFinite(n)?n.toFixed(1):"\u2014"}function si(n,t,e){return[Math.min(1,n.index),Math.min(1,t.known_share),Math.min(1,(e.effective_genres??0)/12)]}var ii=()=>v`<svg class="info-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>`,Ve=class extends f{constructor(){super(...arguments);this._open=null}static{this.properties={obscurity:{attribute:!1},era:{attribute:!1},loyalty:{attribute:!1},_open:{state:!0}}}static{this.styles=[y,w,b`
      :host {
        display: grid;
        grid-template-columns: 1fr;
        grid-auto-rows: max-content;
        align-content: start;
        gap: 12px;
      }
      /* Compact: these are three small readings, not three panels. */
      .panel {
        gap: 0;
        padding: 13px 15px;
        /* rounded-lg on the Vue Card */
        border-radius: 10px;
      }
      /* The open tile has to sit above its later siblings: each panel's backdrop-filter is its
         own stacking context, so a popover would otherwise slide under the next tile. */
      .panel.open {
        z-index: 2;
      }
      .panel.low .tile {
        opacity: 0.6;
      }
      .tile {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      /* Text left, glyph after. The figure is what the tile is for, so it starts at the
         same edge as every other tile's; the glyph fills the space that was empty. */
      .body {
        display: flex;
        flex-direction: column;
        gap: 2px;
        /* Only as wide as its text, so the leftover width is a real gap the glyph can sit in
           the middle of. */
        flex: 0 1 auto;
        min-width: 0;
        text-align: left;
        order: 0;
      }
      /* The glyph is first in the DOM (it is decoration, and screen readers skip it), so
         the visual order has to be stated. Auto margins on BOTH sides: it centres itself in
         whatever space the text has not taken, rather than hugging either edge. */
      lg-gene-glyph {
        order: 1;
        margin-inline: auto;
        width: 34px;
        height: 49px;
      }
      .label {
        display: flex;
        align-items: center;
        gap: 6px;
      }
      /* The eclecticism tile's caption is the longest on the row; let it wrap rather than
         squeeze the glyph's lane down to nothing. */
      .body .code {
        white-space: normal;
        line-height: 1.45;
        max-width: 22ch;
      }
      .figure {
        font-size: 1.35rem;
        line-height: 1.15;
      }
      .info {
        display: inline-flex;
        padding: 0;
        margin: 0;
        color: var(--genome-muted);
        background: none;
        border: 0;
        border-radius: 50%;
        cursor: help;
      }
      .info:focus-visible {
        outline: 1px solid var(--genome-accent);
        outline-offset: 2px;
      }
      .info-icon {
        width: 14px;
        height: 14px;
      }
      /* Anchored to the tile rather than the icon so it can never run off a phone screen. */
      .tip {
        position: absolute;
        top: calc(100% + 6px);
        left: 12px;
        right: 12px;
        max-width: 320px;
        padding: 8px 11px;
        font: 400 12px/1.45 var(--genome-text);
        letter-spacing: 0.01em;
        color: hsl(210 14% 84%);
        background: #0c1119;
        border: 1px solid var(--genome-panel-border);
        border-radius: 6px;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5);
      }
    `]}render(){if(!this.obscurity||!this.era||!this.loyalty)return d;let e=si(this.obscurity,this.era,this.loyalty),s=this.obscurity.known_share<.5,i=this.loyalty.baseline_effective_genres??0;return l`
      ${this._tile("obscurity",$[0],e[0],a("obscurity"),a("obscurity_tooltip"),L(this.obscurity.index),s?a("low_confidence"):null,s)}
      ${this._tile("era",$[3],e[1],a("era_center"),a("era_center_tooltip"),wt(this.era.center_of_mass),`\xB1 ${Math.round(this.era.spread)} ${a("years")}`)}
      ${this._tile("eclecticism",$[1],e[2],a("eclecticism"),a("eclecticism_tooltip"),as(this.loyalty.effective_genres),i>0?a("eclecticism_vs_average",{baseline:as(i)}):a("eclecticism_no_baseline"))}
    `}_tile(e,s,i,r,o,p,c,h=!1){let m=this._open===e,u=`tip-${e}`,g=()=>this._open=e,_=()=>{this._open===e&&(this._open=null)};return l`<div
      class="panel ${m?"open":""} ${h?"low":""}"
      @mouseleave=${_}
    >
      <div class="tile">
        <lg-gene-glyph .hue=${s} .intensity=${i}></lg-gene-glyph>
        <div class="body">
          <div class="label">
            <span class="code">${r}</span>
            <button
              class="info"
              aria-label=${o}
              aria-describedby=${m?u:d}
              @mouseenter=${g}
              @focus=${g}
              @blur=${_}
              @click=${()=>this._open=m?null:e}
              @keydown=${k=>k.key==="Escape"&&_()}
            >
              ${ii()}
            </button>
          </div>
          <div class="figure">${p}</div>
          ${c?l`<div class="code">${c}</div>`:d}
        </div>
      </div>
      ${m?l`<div class="tip" id=${u} role="tooltip">${o}</div>`:d}
    </div>`}};customElements.get("lg-stat-tiles")||customElements.define("lg-stat-tiles",Ve);function ls(n){return n.toString().padStart(2,"0")}var q=["artists","tracks"],Ke=class extends f{constructor(){super(...arguments);this.topArtists=[];this.topTracks=[];this._tab="artists"}static{this.properties={topArtists:{attribute:!1},topTracks:{attribute:!1},_tab:{state:!0}}}static{this.styles=[y,w,b`
      :host {
        display: block;
        min-width: 0;
      }
      .panel {
        height: 100%;
        min-height: 0;
        border-radius: 10px;
      }
      .tabs {
        display: grid;
        grid-template-columns: 1fr 1fr;
        width: 100%;
      }
      .content {
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      /* The scroller is absolutely positioned, and that is the whole trick.
         Both cards share a grid row, so the row is as tall as its tallest content - which meant
         twenty list rows dictated the height and stretched the three little stat cards to match,
         the exact opposite of what was wanted. Absolutely-positioned content contributes no
         intrinsic height, so the row is sized by the stat column alone and the list scrolls
         inside whatever height that leaves. min-height:0 on each ancestor keeps the flex chain
         from refusing to shrink. */
      .pane {
        position: relative;
        flex: 1 1 auto;
        margin: 0;
        /* A floor, not a height. The three compact tiles alone left room for four rows of a
           list of twenty, which is a scrollbar pretending to be a list. */
        min-height: 290px;
      }
      .pane:focus-visible {
        outline: 1px solid var(--genome-accent);
        outline-offset: 2px;
        border-radius: 6px;
      }
      /* Below the two-column breakpoint the cards stack, so there is no row to match and an
         absolutely-positioned list would collapse to nothing. */
      @media (max-width: 899px) {
        .pane {
          min-height: 340px;
        }
      }
      ol {
        position: absolute;
        inset: 0;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 1px;
        list-style: none;
        margin: 0;
        padding: 0;
        scrollbar-width: thin;
        scrollbar-color: hsl(200 40% 60% / 0.25) transparent;
      }
      li {
        display: flex;
        align-items: baseline;
        gap: 10px;
        padding: 5px 6px;
        border-radius: 6px;
        transition: background-color 120ms ease;
      }
      li:hover {
        background: hsl(205 55% 65% / 0.05);
      }
      .index {
        flex: 0 0 auto;
        font: 600 9.5px/1 var(--genome-mono);
        letter-spacing: 0.12em;
        color: var(--genome-tick);
        width: 2ch;
      }
      .body {
        display: flex;
        flex-direction: column;
        gap: 1px;
        min-width: 0;
      }
      .name {
        font-family: var(--genome-text);
        font-size: 12.5px;
        color: hsl(210 14% 84%);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .meta {
        font: 600 9px/1.3 var(--genome-mono);
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: hsl(215 8% 44%);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    `]}render(){return l`<section class="panel">
      <h2 class="panel-title">${a("top_lists")}</h2>
      <div class="content">
        <div class="tabs" role="tablist" @keydown=${this._onKey}>
          ${q.map(e=>l`<button
              class="tab"
              role="tab"
              id="tab-${e}"
              aria-controls="pane-${e}"
              aria-selected=${this._tab===e?"true":"false"}
              tabindex=${this._tab===e?0:-1}
              @click=${()=>this._tab=e}
            >
              ${a(e==="artists"?"top_artists":"top_tracks")}
            </button>`)}
        </div>
        <div
          class="pane"
          role="tabpanel"
          id="pane-${this._tab}"
          aria-labelledby="tab-${this._tab}"
          tabindex="0"
        >
          ${this._tab==="artists"?this._artists():this._tracks()}
        </div>
      </div>
    </section>`}_artists(){return l`<ol>
      ${(this.topArtists??[]).map((e,s)=>l`<li>
          <span class="index">${ls(s+1)}</span>
          <span class="body">
            <span class="name">${e.name}</span>
            <span class="meta"
              >${a("plays",{count:e.plays})}${e.ratio_vs_average?l` · ${a("vs_average",{ratio:de(e.ratio_vs_average)})}`:d}</span
            >
          </span>
        </li>`)}
    </ol>`}_tracks(){return l`<ol>
      ${(this.topTracks??[]).map((e,s)=>l`<li>
          <span class="index">${ls(s+1)}</span>
          <span class="body">
            <span class="name">${e.name}</span>
            <span class="meta">${e.artist} · ${a("plays",{count:e.plays})}</span>
          </span>
        </li>`)}
    </ol>`}_onKey(e){if(!["ArrowLeft","ArrowRight","Home","End"].includes(e.key))return;e.preventDefault();let s=q.indexOf(this._tab),i=e.key==="Home"?0:e.key==="End"?q.length-1:(s+(e.key==="ArrowRight"?1:-1)+q.length)%q.length;this._tab=q[i],this.updateComplete.then(()=>this.renderRoot.querySelector(`#tab-${this._tab}`)?.focus())}};customElements.get("lg-top-lists")||customElements.define("lg-top-lists",Ke);var M=16,qe=22,_e=4,ni=[0,6,12,18],ri=qe+24*M+4,oi=_e+7*M+16,ai=["mon","tue","wed","thu","fri","sat","sun"];function li(n){let t=Wt(n.map(s=>s.share)),e=xt(n);return n.map(s=>({...s,fill:Ie(Jt(s.share,t,e)/(P-1))}))}function pi(){return Array.from({length:P},(n,t)=>Ie(t/(P-1)))}var We=class extends f{constructor(){super(...arguments);this.rhythm=[]}static{this.properties={rhythm:{attribute:!1}}}static{this.styles=[y,w,b`
      :host {
        display: block;
        min-width: 0;
      }
      .panel {
        border-radius: 10px;
      }
      /* The grid keeps a legible minimum size and scrolls inside the card on a phone,
         rather than shrinking its cells to specks. */
      .scroll {
        overflow-x: auto;
      }
      svg {
        display: block;
        width: 100%;
        height: auto;
        min-width: 480px;
      }
      text {
        fill: var(--genome-muted);
        font: 9px var(--genome-text);
      }
      .legend {
        display: flex;
        align-items: center;
        gap: 5px;
      }
      .swatch {
        width: 15px;
        height: 9px;
        border-radius: 2px;
      }
    `]}render(){let e=ai.map(i=>a(`weekday_${i}`)),s=li(this.rhythm??[]);return l`<section class="panel">
      <h2 class="panel-title">${a("rhythm")}</h2>
      <div>
        <div class="scroll">
          <svg viewBox="0 0 ${ri} ${oi}" role="img" aria-label=${a("rhythm")}>
            ${e.map((i,r)=>v`<text x="0" y=${_e+r*M+M*.7}>${i}</text>`)}
            ${s.map(i=>v`<rect
                x=${qe+i.hour*M}
                y=${_e+i.weekday*M}
                width=${M-1}
                height=${M-1}
                rx="1.5"
                fill=${i.fill}
              ><title>${e[i.weekday]} ${i.hour}:00 · ${L(i.share)}</title></rect>`)}
            ${ni.map(i=>v`<text
                x=${qe+i*M+M/2}
                y=${_e+7*M+10}
                text-anchor="middle"
              >${i}</text>`)}
          </svg>
        </div>
        <!-- The steps are ranked rather than linear, so a reader has no way to infer the scale
             from the cells alone. The legend is what makes it honest. -->
        <div class="legend" style="margin-top:12px">
          <span class="code">${a("rhythm_quieter")}</span>
          ${pi().map(i=>l`<span class="swatch" style="background:${i}" aria-hidden="true"></span>`)}
          <span class="code">${a("rhythm_busier")}</span>
        </div>
      </div>
    </section>`}};customElements.get("lg-rhythm")||customElements.define("lg-rhythm",We);function ps(n){if(!n)return 220;let t=0;for(let e=0;e<n.length;e++)t=Math.imul(t,31)+n.charCodeAt(e)>>>0;return $[t%$.length]}function cs(n){let t=ps(n),e=E(.8,n?.13:.02,t),s=E(.64,n?.12:.02,t);return`radial-gradient(circle at 38% 34%, rgba(255,255,255,.5) 0%, rgba(255,255,255,0) 34%), radial-gradient(circle at 50% 50%, ${e} 0%, ${e} 38%, ${s} 62%, transparent 76%)`}function ds(n){return E(.72,n?.1:.02,ps(n))}function hs(n){return Number.isFinite(n)?Math.round(Math.max(0,Math.min(1,n))*100):0}function us(n,t){let e=s=>s?n.players.find(i=>i.entity_id===s&&i.available):void 0;return e(t)?.entity_id??e(n.last_used)?.entity_id??n.players.find(s=>s.available)?.entity_id??null}function Je(n,t,e){return`${n}\0${t}\0${e}`}var ci=2e3,di=4e3,ms="listening-genome.speaker",Ye=null;function hi(){if(Ye)return Ye;try{return sessionStorage.getItem(ms)}catch{return null}}function ui(n){Ye=n;try{sessionStorage.setItem(ms,n)}catch{}}var Ze=class extends f{constructor(){super(...arguments);this.isAdmin=!1;this._data=null;this._loadError=!1;this._refreshing=!1;this._refreshError="";this._speakers=null;this._speaker=null;this._rows={};this._confirmTimers=new Map}static{this.properties={api:{attribute:!1},isAdmin:{type:Boolean},_data:{state:!0},_loadError:{state:!0},_refreshing:{state:!0},_refreshError:{state:!0},_speakers:{state:!0},_speaker:{state:!0},_rows:{state:!0}}}static{this.styles=[y,w,b`
      :host {
        display: block;
        min-width: 0;
      }
      .panel {
        gap: 14px;
      }
      .header-actions {
        display: flex;
        align-items: center;
        gap: 4px;
        margin: -6px -6px 0 0;
      }
      .lead,
      .empty {
        font-size: 11.5px;
        line-height: 1.5;
        color: hsl(215 8% 50%);
      }
      .empty {
        color: hsl(215 8% 52%);
      }
      .speaker-row {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
      }
      .speaker-row label {
        flex: none;
      }
      .speaker-row select {
        flex: 1 1 auto;
        min-width: 0;
        max-width: 100%;
        font-size: 12.5px;
      }
      section {
        display: flex;
        flex-direction: column;
        gap: 7px;
      }
      .label {
        margin: 0;
        padding-bottom: 5px;
        border-bottom: 1px solid var(--genome-panel-border);
      }
      .link {
        color: var(--genome-accent);
        text-decoration: none;
        border-bottom: 1px solid hsl(190 85% 62% / 0.35);
      }
      .link:hover {
        border-bottom-color: var(--genome-accent);
      }
      .list {
        display: flex;
        flex-direction: column;
        gap: 2px;
        /* long enough to be worth scrolling, short enough not to outgrow the heatmap */
        max-height: 300px;
        overflow-y: auto;
      }
      .strand {
        display: flex;
        align-items: center;
        gap: 9px;
        padding: 5px 4px 5px 6px;
        border-radius: 6px;
        transition: background-color 120ms ease;
      }
      .strand:hover {
        background: hsl(205 55% 65% / 0.05);
      }
      .mark {
        width: 11px;
        height: 11px;
        flex: 0 0 auto;
        border-radius: 50%;
      }
      .body {
        display: flex;
        flex-direction: column;
        gap: 1px;
        min-width: 0;
        flex: 1 1 auto;
      }
      .name,
      .meta,
      .song,
      .feedback {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .name {
        font-size: 12.5px;
        color: hsl(210 14% 84%);
      }
      .meta {
        font: 600 9px/1.3 var(--genome-mono);
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: hsl(215 8% 50%);
      }
      .song {
        font-size: 11.5px;
        color: hsl(210 10% 66%);
      }
      .feedback {
        font-size: 11px;
        color: var(--genome-accent);
      }
      .feedback.error {
        color: hsl(0 80% 72%);
        white-space: normal;
      }
      /* the match is a bar, not a number: Last.fm's figure is ordinal in practice */
      .score {
        flex: 0 0 34px;
        height: 3px;
        border-radius: 2px;
        background: hsl(215 40% 60% / 0.12);
        overflow: hidden;
      }
      .bar {
        display: block;
        height: 100%;
        border-radius: 2px;
      }
      .play {
        flex: none;
        width: 30px;
        height: 30px;
        border-color: hsl(190 85% 62% / 0.25);
        color: var(--genome-accent);
      }
      .play .icon {
        width: 13px;
        height: 13px;
      }
      .play-spacer {
        flex: none;
        width: 30px;
      }
      .empty.error {
        color: hsl(0 80% 72%);
      }
    `]}updated(e){e.has("api")&&this.api&&this._loadedFor!==this.api&&(this._loadedFor=this.api,this._load(),this._loadSpeakers())}disconnectedCallback(){super.disconnectedCallback(),clearTimeout(this._poll),this._poll=void 0;for(let e of this._confirmTimers.values())clearTimeout(e);this._confirmTimers.clear()}connectedCallback(){super.connectedCallback(),this._refreshing&&!this._poll&&this._schedulePoll()}async _load(){if(this.api)try{this._data=await this.api.discovery(),this._loadError=!1}catch{this._loadError=!0}}async _loadSpeakers(){if(this.api)try{let e=await this.api.players();this._speakers=e,this._speaker=us(e,hi())}catch{this._speakers={players:[],last_used:null},this._speaker=null}}async _refresh(){if(!(!this.api||this._refreshing)){this._refreshing=!0,this._refreshError="";try{await this.api.discoveryRefresh()}catch(e){if(e?.code!=="already_running"){this._refreshError=A(e),this._refreshing=!1;return}}this._schedulePoll()}}_schedulePoll(){clearTimeout(this._poll),this._poll=setTimeout(()=>void this._pollJobs(),ci)}async _pollJobs(){if(this._poll=void 0,!this.api||!this.isConnected)return;let e=null;try{e=await this.api.jobs()}catch{e=null}if(e&&e.discovery?.state!=="running"){this._refreshing=!1,e.discovery?.state==="error"&&(this._refreshError=e.discovery.message),await this._load();return}this._schedulePoll()}_speakerName(e){return this._speakers?.players.find(s=>s.entity_id===e)?.name??e??""}_chooseSpeaker(e){let s=e.target.value;this._speaker=s||null,s&&ui(s)}_setRow(e,s){let i={...this._rows};s?i[e]=s:delete i[e],this._rows=i}async _play(e,s,i){let r=this._speaker;if(!this.api||!r)return;let o=this._speakerName(r);clearTimeout(this._confirmTimers.get(e)),this._setRow(e,{status:"starting"});try{await this.api.play(r,s,i),this._setRow(e,{status:"playing",speaker:o}),this._confirmTimers.set(e,setTimeout(()=>{this._confirmTimers.delete(e),this._rows[e]?.status==="playing"&&this._setRow(e,null)},di))}catch(p){this._setRow(e,{status:"error",message:A(p)})}}render(){return l`<div class="panel">
      <div class="panel-header">
        <h2 class="panel-title">${a("discovery.title")}</h2>
        ${this.isAdmin?l`<div class="header-actions">
              <button
                class="icon-btn"
                ?disabled=${this._refreshing}
                aria-label=${a("discovery.refresh")}
                title=${a("discovery.refresh")}
                @click=${this._refresh}
              >
                ${V(this._refreshing?"icon spin":"icon")}
              </button>
            </div>`:d}
      </div>
      <p class="lead">${a("discovery.lead")}</p>
      ${this._speakerMenu()}
      ${this._refreshing?l`<p class="empty" role="status">${a("panel.discovery.refreshing")}</p>`:d}
      ${this._refreshError?l`<p class="empty error" role="alert">
            ${a("panel.discovery.refresh_failed",{error:this._refreshError})}
          </p>`:d}
      ${this._suggested()} ${this._cold()}
      ${this._loadError?l`<p class="empty error">${a("discovery.error")}</p>`:d}
    </div>`}_speakerMenu(){let e=this._speakers;if(!e)return d;let s="lg-speaker";return l`<div class="speaker-row">
      <label class="code" for=${s}>${a("panel.discovery.speaker_label")}</label>
      <select id=${s} .value=${this._speaker??""} @change=${this._chooseSpeaker}
        ?disabled=${!e.players.some(i=>i.available)}>
        ${e.players.length===0?l`<option value="">${a("panel.discovery.no_speakers")}</option>`:e.players.map(i=>l`<option
                value=${i.entity_id}
                ?disabled=${!i.available}
                ?selected=${i.entity_id===this._speaker}
              >
                ${i.available?i.name:a("panel.discovery.speaker_unavailable",{name:i.name})}
              </option>`)}
      </select>
    </div>`}_suggested(){let e=this._data,s;return e?e.suggested_state==="unavailable"?s=l`<p class="empty">${a("panel.discovery.no_lastfm_where")}</p>`:e.suggested_state==="pending"?s=l`<p class="empty">${a("discovery.pending")}</p>`:e.suggested.length===0?s=l`<p class="empty">${a("discovery.no_suggestions")}</p>`:s=l`<ul class="list">
        ${e.suggested.map(i=>this._row(Je("suggested",i.artist_name,i.song??""),i.artist_name,i.song??null,i.genre_key,a("discovery.because",{seed:i.seed_artist}),l`<span class="score" title=${a("discovery.match_title")}>
              <span
                class="bar"
                style="width:${hs(i.match)}%;background:${ds(i.genre_key)}"
              ></span>
            </span>`))}
      </ul>`:s=d,l`<section>
      <h3 class="code label">${a("discovery.suggested_heading")}</h3>
      ${s}
    </section>`}_cold(){let e=this._data,s;return e?e.in_library.length===0?s=l`<p class="empty">${a("discovery.no_cold")}</p>`:s=l`<ul class="list">
        ${e.in_library.map(i=>{let r=i.plays===0?a("discovery.never_played"):a("discovery.n_plays",{plays:i.plays});return this._row(Je("cold",i.artist_name,i.song??""),i.artist_name,i.song??null,i.genre_key,i.genre_label?`${r} \xB7 ${i.genre_label}`:r,d)})}
      </ul>`:s=d,l`<section>
      <h3 class="code label">${a("discovery.cold_heading")}</h3>
      ${s}
    </section>`}_row(e,s,i,r,o,p){let c=this._rows[e];return l`<li class="strand">
      <span class="mark" style="background:${cs(r)}" aria-hidden="true"></span>
      <span class="body">
        <span class="name">${s}</span>
        <span class="meta">${o}</span>
        ${i?l`<span class="song">${a("panel.discovery.try",{song:i})}</span>`:d}
        <span role="status" aria-live="polite">${this._feedback(c)}</span>
      </span>
      ${p} ${i?this._playButton(e,s,i,c):l`<span class="play-spacer"></span>`}
    </li>`}_feedback(e){return e?e.status==="starting"?l`<span class="feedback">${a("panel.discovery.starting")}</span>`:e.status==="playing"?l`<span class="feedback"
        >${a("panel.discovery.playing_on",{speaker:e.speaker})}</span
      >`:l`<span class="feedback error">${e.message}</span>`:d}_playButton(e,s,i,r){let o=this._speaker,p=r?.status==="starting",c=o?a("panel.discovery.play_aria",{song:i,artist:s,speaker:this._speakerName(o)}):a("panel.discovery.no_speaker_title");return l`<button
      class="icon-btn play"
      aria-label=${c}
      title=${c}
      aria-busy=${p?"true":"false"}
      ?disabled=${!o||p}
      @click=${()=>this._play(e,s,i)}
    >
      ${p?z():At()}
    </button>`}};customElements.get("lg-discovery")||customElements.define("lg-discovery",Ze);var Xe=class extends f{constructor(){super(...arguments);this.loading=!1;this.canRebuild=!1}static{this.properties={loading:{type:Boolean},canRebuild:{type:Boolean}}}static{this.styles=[y,w,b`
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
    `]}render(){return l`<section class="panel">
      <div class="header">
        <div class="media">${he()}</div>
        <h2>${a("empty_title")}</h2>
        <p class="body">${a("empty_body")}</p>
      </div>
      <div class="actions">
        <button class="btn primary" @click=${this._navigate}>${a("empty_cta")}</button>
        ${this.canRebuild?l`<button class="btn" ?disabled=${this.loading} @click=${this._rebuild}>
              ${V(this.loading?"icon spin":"icon")} ${a("rebuild")}
            </button>`:d}
      </div>
    </section>`}_navigate(){this.dispatchEvent(new CustomEvent("navigate",{detail:"/import"}))}_rebuild(){this.dispatchEvent(new CustomEvent("rebuild"))}};customElements.get("lg-empty-state")||customElements.define("lg-empty-state",Xe);var Qe=class extends f{constructor(){super(...arguments);this.isAdmin=!1;this.narrow=!1;this._genome=null;this._loading=!1;this._error=null;this._unresolved=null;this._dialogOpen=!1}static{this.properties={api:{attribute:!1},isAdmin:{type:Boolean},narrow:{type:Boolean},_genome:{state:!0},_loading:{state:!0},_error:{state:!0},_unresolved:{state:!0},_dialogOpen:{state:!0}}}static{this.styles=[y,w,b`
      :host {
        display: block;
      }
      .page {
        display: flex;
        flex-direction: column;
        gap: 24px;
        max-width: 1600px;
        margin: 0 auto;
        padding: 24px;
      }
      :host([narrow]) .page {
        padding: 16px;
        padding-top: 60px;
      }
      header {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }
      h1 {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        margin: 0;
        font-size: 24px;
        text-transform: uppercase;
      }
      h1 .icon {
        width: 20px;
        height: 20px;
        color: var(--genome-accent);
      }
      .subtitle {
        margin-top: 4px;
        font-size: 14px;
        color: var(--genome-muted);
      }
      .actions {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .rule {
        height: 1px;
        margin-top: -12px;
        background: linear-gradient(
          90deg,
          var(--genome-tick),
          rgba(255, 255, 255, 0.05) 42%,
          transparent 78%
        );
      }
      .notice {
        flex-direction: row;
        align-items: flex-start;
        gap: 12px;
        padding: 14px 16px;
      }
      .notice-title {
        margin: 0 0 4px;
        font: 400 13px var(--genome-display);
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }
      .notice-body {
        font-size: 14px;
        color: hsl(215 10% 70%);
      }
      .link {
        padding: 0;
        margin-left: 4px;
        font: inherit;
        font-size: 12px;
        color: var(--genome-accent);
        background: none;
        border: 0;
        cursor: pointer;
        text-decoration: underline;
      }
      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      /* the three figures stack in one narrow column and the top-twenty list fills a card
         beside them, sized to that column rather than to its own content */
      .columns {
        display: grid;
        grid-template-columns: 1fr;
        align-items: stretch;
        gap: 16px;
      }
      @media (min-width: 900px) {
        .columns {
          grid-template-columns: minmax(230px, 0.85fr) 1.15fr;
        }
      }
      .lower {
        display: grid;
        gap: 24px;
        align-items: start;
      }
      @media (min-width: 1024px) {
        .lower {
          grid-template-columns: 1fr 380px;
        }
      }
      .footer {
        font-size: 12px;
        color: var(--genome-muted);
      }
      .skeleton {
        border-radius: var(--genome-radius);
        background: linear-gradient(
          90deg,
          rgba(255, 255, 255, 0.03),
          rgba(255, 255, 255, 0.07),
          rgba(255, 255, 255, 0.03)
        );
        background-size: 200% 100%;
        animation: shimmer 1.6s linear infinite;
      }
      @keyframes shimmer {
        from {
          background-position: 200% 0;
        }
        to {
          background-position: -200% 0;
        }
      }
      dialog {
        width: min(440px, calc(100vw - 32px));
        max-height: 80vh;
        padding: 20px;
        color: var(--genome-fg);
        background: #0c1119;
        border: 1px solid var(--genome-panel-border);
        border-radius: var(--genome-radius);
      }
      dialog::backdrop {
        background: rgba(0, 0, 0, 0.6);
      }
      .unresolved {
        display: flex;
        flex-direction: column;
        max-height: 46vh;
        overflow-y: auto;
        margin: 8px 0;
      }
      .unresolved li {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
        padding: 7px 2px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        font-size: 13px;
      }
      .dialog-actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-top: 12px;
      }
    `]}connectedCallback(){super.connectedCallback(),this.toggleAttribute("narrow",this.narrow),this._load()}updated(e){e.has("narrow")&&this.toggleAttribute("narrow",this.narrow)}async _load(){this._loading=!0,this._error=null;try{this._genome=await this.api.getGenome()}catch(e){this._genome=null,this._error=A(e)}finally{this._loading=!1}}async _rebuild(){this._loading=!0,this._error=null;try{this._genome=(await this.api.rebuild()).genome}catch(e){this._error=`${a("rebuild_error")} ${A(e)}`}finally{this._loading=!1}}async _openUnresolved(){this._dialogOpen=!0,this._unresolved=null,await this.updateComplete,this.renderRoot.querySelector("dialog")?.showModal();try{this._unresolved=await this.api.unresolvedArtists(100)}catch{this._unresolved=[]}}_closeDialog(){this.renderRoot.querySelector("dialog")?.close(),this._dialogOpen=!1}async _retry(){await this.api.retryArtists(),this._closeDialog(),await this._load()}async _dismiss(){await this.api.dismissUnresolved(),this._closeDialog(),await this._load()}_navigate(e){this.dispatchEvent(new CustomEvent("navigate",{detail:e}))}render(){return l`<div class="page">
      <header>
        <div>
          <h1>${he()}${a("title")}</h1>
          <p class="subtitle">${a("subtitle")}</p>
        </div>
        <div class="actions">
          <button
            class="icon-btn"
            aria-label=${a("open_settings")}
            title=${a("open_settings")}
            @click=${()=>this._navigate("/import")}
          >
            ${St()}
          </button>
          ${this.isAdmin?l`<button class="btn" ?disabled=${this._loading} @click=${this._rebuild}>
                ${V(this._loading?"icon spin":"icon")} ${a("rebuild")}
              </button>`:d}
        </div>
      </header>
      <div class="rule" aria-hidden="true"></div>
      ${this._body()}
    </div>`}_body(){let e=this._genome;return this._loading&&!e?l`<div class="skeleton" style="height:420px"></div>
        <div class="skeleton" style="height:110px"></div>
        <div class="skeleton" style="height:280px"></div>`:!e||e.stats.total_listens===0?l`<lg-empty-state
          .loading=${this._loading}
          .canRebuild=${this.isAdmin}
          @rebuild=${this._rebuild}
          @navigate=${s=>this._navigate(s.detail)}
        ></lg-empty-state>
        ${this._error&&e?l`<p class="error small">${this._error}</p>`:d}`:l`
      ${this._error?l`<p class="error small">${this._error}</p>`:d}
      ${this._notices(e)}
      <lg-molecule
        .genres=${e.genres}
        .bases=${e.bases}
        .totalListens=${e.stats.total_listens}
      ></lg-molecule>
      ${e.divergence.top_over.length?l`<div class="chips">
            ${e.divergence.top_over.map(s=>l`<span class="chip"
                  >${s.label} ${a("vs_average",{ratio:de(s.ratio)})}</span
                >`)}
          </div>`:d}
      <div class="columns">
        <lg-stat-tiles
          .obscurity=${e.obscurity}
          .era=${e.era}
          .loyalty=${e.loyalty}
        ></lg-stat-tiles>
        <lg-top-lists
          .topArtists=${e.top_artists}
          .topTracks=${e.top_tracks}
        ></lg-top-lists>
      </div>
      <div class="lower">
        <lg-rhythm .rhythm=${e.rhythm}></lg-rhythm>
        <lg-discovery .api=${this.api} .isAdmin=${this.isAdmin}></lg-discovery>
      </div>
      <p class="footer">
        ${a("stats_footer",{listens:D(e.stats.total_listens),artists:D(e.stats.distinct_artists),tracks:D(e.stats.distinct_tracks)})}
        ${e.stale?l` · ${a("stale_notice")}`:d}
      </p>
    `}_notices(e){return Ce(e.stats)?l`<div class="panel notice" role="status">
        ${z()}
        <div>
          <p class="notice-title">${a("enriching_title")}</p>
          <p class="notice-body">
            ${a("enriching_body",{pending:e.stats.artists_pending,resolved:e.stats.artists_resolved})}
          </p>
        </div>
      </div>`:$t(e.stats)?l`<div class="panel notice" role="status">
        ${Mt()}
        <div>
          <p class="notice-title">${a("unresolved_title")}</p>
          <p class="notice-body">
            ${a("unresolved_body",{failed:e.stats.artists_failed})}
            <button class="link" @click=${this._openUnresolved}>${a("unresolved_show")}</button>
          </p>
        </div>
      </div>
      ${this._dialogOpen?this._dialog():d}`:d}_dialog(){return l`<dialog @close=${()=>this._dialogOpen=!1}>
      <p class="notice-title">${a("unresolved_title")}</p>
      <p class="small muted">${a("unresolved_dialog_hint")}</p>
      <p class="small" style="margin-top:8px">${a("unresolved_what_to_do")}</p>
      ${this._unresolved===null?l`<p class="small muted">${a("loading")}</p>`:l`<ul class="unresolved">
            ${this._unresolved.map(e=>l`<li><span>${e.artist_name}</span><span class="code"
                  >${mi(e.resolved_at)}</span
                ></li>`)}
          </ul>`}
      <div class="dialog-actions">
        <span class="small muted">${a("unresolved_dismiss_hint")}</span>
        <span class="actions">
          ${this.isAdmin?l`<button class="btn" @click=${this._dismiss}>${a("unresolved_dismiss")}</button>
                <button class="btn primary" @click=${this._retry}>${a("unresolved_retry")}</button>`:d}
          <button class="btn" @click=${this._closeDialog}>Close</button>
        </span>
      </div>
    </dialog>`}};function mi(n){if(!n)return"";let t=Math.max(0,Math.round((Date.now()/1e3-n)/3600));return t<1?a("attempted_recently"):t<48?a("attempted_hours",{hours:t}):a("attempted_days",{days:Math.round(t/24)})}customElements.get("lg-genome-view")||customElements.define("lg-genome-view",Qe);var gs=["rebuild","enrichment","lastfm_import","apple_import","duplicates","discovery"];function be(n,t){if(!n)return"";let e=Math.max(0,t-n);if(e<45)return a("settings.time_just_now");let s=Math.round(e/60);if(s<=1)return a("settings.time_minute_ago");if(s<60)return a("settings.time_minutes_ago",{count:s});let i=Math.round(s/60);if(i<=1)return a("settings.time_hour_ago");if(i<24)return a("settings.time_hours_ago",{count:i});let r=Math.round(i/24);return r<=1?a("settings.time_day_ago"):a("settings.time_days_ago",{count:r})}function fs(n){let t=a(`panel.job.${n}`);return t===`panel.job.${n}`?n.replace(/_/g," "):t}function _s(n){let t=a(`panel.state.${n}`);return t===`panel.state.${n}`?n:t}function bs(n){let t=n,e=gs.filter(i=>t[i]).map(i=>({...t[i],job:i})),s=Object.keys(t).filter(i=>!gs.includes(i)).map(i=>({...t[i],job:i}));return[...e,...s]}function et(n){return!!n&&Object.values(n).some(t=>t.state==="running")}function vs(n,t){if(n.state==="running"){let s=be(n.started_at,t),i=n.message||a("panel.job_working");return s?a("panel.job_started",{message:i,when:s}):i}if(n.state==="idle"&&!n.message)return a("panel.job_never");let e=be(n.finished_at??n.started_at,t);return n.message?e?a("settings.job_result_when",{message:n.message,when:e}):n.message:e}var gi=2e3,fi=3e4,tt=class extends f{constructor(){super(...arguments);this.isAdmin=!1;this.narrow=!1;this._jobs=null;this._jobsError="";this._live=null;this._liveError="";this._now=Math.floor(Date.now()/1e3);this._lastfmBusy=!1;this._lastfmNote=null;this._lastfmUnset=!1;this._uploading=!1;this._appleFile="";this._appleNote=null}static{this.properties={api:{attribute:!1},isAdmin:{type:Boolean},narrow:{type:Boolean},_jobs:{state:!0},_jobsError:{state:!0},_live:{state:!0},_liveError:{state:!0},_now:{state:!0},_lastfmBusy:{state:!0},_lastfmNote:{state:!0},_lastfmUnset:{state:!0},_uploading:{state:!0},_appleFile:{state:!0},_appleNote:{state:!0}}}static{this.styles=[y,w,b`
      :host {
        display: block;
      }
      .page {
        max-width: 1000px;
        margin: 0 auto;
        padding: 24px 24px 48px;
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      :host([narrow]) .page {
        padding: 64px 16px 32px;
      }
      header {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .back {
        align-self: flex-start;
      }
      h1 {
        margin: 0;
        font-size: 20px;
      }
      .subtitle {
        font-size: 13px;
        color: var(--genome-muted);
      }
      .cards {
        display: grid;
        gap: 20px;
      }
      @media (min-width: 820px) {
        .cards {
          grid-template-columns: 1fr 1fr;
        }
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;
      }
      .file-name {
        font-size: 12px;
        color: var(--genome-muted);
        overflow-wrap: anywhere;
      }
      .note {
        font-size: 12.5px;
        line-height: 1.5;
        color: hsl(210 10% 70%);
      }
      .note.error {
        color: hsl(0 80% 72%);
      }
      .hint {
        font-size: 12px;
        line-height: 1.5;
        color: hsl(215 8% 55%);
      }
      .path {
        color: hsl(210 14% 80%);
      }
      input[type="file"] {
        display: none;
      }
      .jobs {
        display: flex;
        flex-direction: column;
      }
      .job {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 6px 12px;
        padding: 12px 0;
        border-top: 1px solid hsl(200 65% 70% / 0.12);
      }
      .job:first-child {
        border-top: 0;
        padding-top: 0;
      }
      .job-name {
        font-size: 13.5px;
        color: hsl(210 14% 86%);
      }
      .job .progress {
        grid-column: 1 / -1;
      }
      .job-detail {
        grid-column: 1 / -1;
        font-size: 12px;
        line-height: 1.5;
        color: hsl(215 8% 58%);
        overflow-wrap: anywhere;
      }
      .job-detail.error {
        color: hsl(0 80% 72%);
      }
      .state {
        justify-self: end;
        align-self: center;
      }
      .state.running {
        color: var(--genome-accent);
        border-color: hsl(190 85% 62% / 0.45);
      }
      .state.ok {
        color: hsl(150 50% 66%);
      }
      .state.error {
        color: hsl(0 80% 72%);
        border-color: hsl(0 80% 72% / 0.45);
      }
      .state.interrupted {
        color: hsl(40 85% 66%);
      }
      .live {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px 14px;
        font-size: 12.5px;
        color: hsl(215 8% 62%);
      }
      .dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        margin-right: 6px;
        border-radius: 50%;
        background: hsl(0 70% 62%);
      }
      .dot.on {
        background: hsl(150 60% 55%);
        box-shadow: 0 0 6px hsl(150 60% 55% / 0.7);
      }
      .live-state {
        display: inline-flex;
        align-items: center;
        color: hsl(210 14% 84%);
      }
      .live .error {
        flex-basis: 100%;
      }
    `]}updated(e){e.has("narrow")&&this.toggleAttribute("narrow",this.narrow),e.has("api")&&this.api&&this._loadedFor!==this.api&&(this._loadedFor=this.api,this._refreshJobs(),this._refreshLive(),this._checkLastfm())}connectedCallback(){super.connectedCallback(),this._clock=setInterval(()=>this._now=Math.floor(Date.now()/1e3),fi),this._loadedFor&&et(this._jobs)&&this._schedulePoll()}disconnectedCallback(){super.disconnectedCallback(),clearTimeout(this._poll),this._poll=void 0,clearInterval(this._clock)}_schedulePoll(){this._poll||!this.isConnected||(this._poll=setTimeout(()=>{this._poll=void 0,this._refreshJobs(),this._refreshLive()},gi))}async _refreshJobs(){if(this.api){try{this._jobs=await this.api.jobs(),this._jobsError=""}catch(e){this._jobsError=A(e)}this._now=Math.floor(Date.now()/1e3),(et(this._jobs)||this._uploading)&&this._schedulePoll()}}async _refreshLive(){if(this.api)try{this._live=await this.api.live(),this._liveError=""}catch(e){this._liveError=A(e)}}async _checkLastfm(){if(this.api)try{this._lastfmUnset=(await this.api.discovery()).suggested_state==="unavailable"}catch{this._lastfmUnset=!1}}_applyJob(e,s){let i=s;this._jobs&&i&&typeof i=="object"&&"state"in i&&(this._jobs={...this._jobs,[e]:{...i,job:e}}),this._schedulePoll()}async _importLastfm(){if(!(!this.api||this._lastfmBusy)){this._lastfmBusy=!0,this._lastfmNote=null;try{let e=await this.api.importLastfm();this._lastfmUnset=!1,this._lastfmNote={kind:"info",text:a("panel.import.lastfm_started")},this._applyJob("lastfm_import",e)}catch(e){let s=e?.code;s==="not_configured"?(this._lastfmUnset=!0,this._lastfmNote={kind:"error",text:A(e),hint:a("panel.import.lastfm_where")}):(this._lastfmNote={kind:"error",text:A(e)},s==="already_running"&&this._schedulePoll())}finally{this._lastfmBusy=!1}}}_pickFile(){this.renderRoot.querySelector("#apple-file")?.click()}async _onFile(e){let s=e.target,i=s.files?.[0];if(s.value="",!(!i||!this.api)){this._uploading=!0,this._appleFile=i.name,this._appleNote=null;try{await this.api.importApple(i),this._appleNote={kind:"info",text:a("panel.import.apple_started",{file:i.name})}}catch(r){this._appleNote={kind:"error",text:A(r)}}finally{this._uploading=!1,this._refreshJobs()}}}_back(){this.dispatchEvent(new CustomEvent("navigate",{detail:""}))}render(){let e=this._jobs,s=e?.lastfm_import?.state==="running",i=e?.apple_import?.state==="running";return l`<div class="page">
      <header>
        <button class="btn back" @click=${this._back}>${Et()} ${a("panel.import.back")}</button>
        <h1>${a("panel.import.title")}</h1>
        <p class="subtitle">${a("panel.import.subtitle")}</p>
      </header>
      ${this.isAdmin?d:l`<p class="hint" role="note">${a("panel.import.admin_only")}</p>`}
      <div class="cards">
        ${this._appleCard(i)} ${this._lastfmCard(s)}
      </div>
      ${this._statusCard()}
    </div>`}_appleCard(e){return l`<section class="panel" aria-labelledby="apple-title">
      <div>
        <h2 class="panel-title" id="apple-title">${a("settings.import_apple")}</h2>
        <p class="panel-description">${a("settings.import_apple_hint")}</p>
      </div>
      ${this.isAdmin?l`<input
              id="apple-file"
              type="file"
              accept=".csv,text/csv"
              aria-label=${a("panel.import.apple_choose")}
              @change=${this._onFile}
            />
            <div class="actions">
              <button
                class="btn primary"
                ?disabled=${this._uploading||e}
                @click=${this._pickFile}
              >
                ${this._uploading?z():Tt()} ${a("panel.import.apple_choose")}
              </button>
              <span class="file-name">${this._appleFile||a("settings.no_file_chosen")}</span>
            </div>`:d}
      ${this._uploading?l`<div class="progress indeterminate" role="progressbar"
              aria-label=${a("panel.import.apple_uploading",{file:this._appleFile})}>
              <span></span>
            </div>
            <p class="note" role="status">
              ${a("panel.import.apple_uploading",{file:this._appleFile})}
            </p>`:this._note(this._appleNote)}
    </section>`}_lastfmCard(e){let s=this._lastfmNote;return l`<section class="panel" aria-labelledby="lastfm-title">
      <div>
        <h2 class="panel-title" id="lastfm-title">${a("panel.import.lastfm_title")}</h2>
        <p class="panel-description">${a("panel.import.lastfm_hint")}</p>
      </div>
      ${this.isAdmin?l`<div class="actions">
            <button
              class="btn primary"
              ?disabled=${this._lastfmBusy||e}
              @click=${this._importLastfm}
            >
              ${this._lastfmBusy||e?z():d}
              ${a("panel.import.lastfm_import_now")}
            </button>
          </div>`:d}
      ${s?this._note(s):this._lastfmUnset?l`<p class="hint">
              ${a("panel.import.lastfm_unset")}
              <span class="path">${a("panel.import.lastfm_where")}</span>
            </p>`:d}
    </section>`}_note(e){return e?l`<p class="note ${e.kind==="error"?"error":""}"
        role=${e.kind==="error"?"alert":"status"}>${e.text}</p>
      ${e.hint?l`<p class="hint path">${e.hint}</p>`:d}`:d}_statusCard(){let e=this._jobs;return l`<section class="panel" aria-labelledby="status-title">
      <div>
        <h2 class="panel-title" id="status-title">${a("panel.import.status_title")}</h2>
        <p class="panel-description">${a("panel.import.status_description")}</p>
      </div>
      ${this._jobsError?l`<p class="note error" role="alert">
            ${a("panel.import.status_error",{error:this._jobsError})}
          </p>`:d}
      ${e?l`<ul class="jobs">
            ${bs(e).map(s=>this._jobRow(s))}
          </ul>`:this._jobsError?d:l`<p class="hint">${a("loading")}</p>`}
      ${this._liveLine()}
    </section>`}_jobRow(e){let s=e.state==="running",i=fs(e.job),r=s?e.progress==null?l`<div class="progress indeterminate" role="progressbar"
            aria-label=${a("panel.progress_aria",{job:i})}><span></span></div>`:l`<div
            class="progress"
            role="progressbar"
            aria-label=${a("panel.progress_aria",{job:i})}
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow=${Math.round(e.progress)}
          >
            <span style="width:${Math.max(0,Math.min(100,e.progress))}%"></span>
          </div>`:d;return l`<li class="job">
      <span class="job-name">${i}</span>
      <span class="chip state ${e.state}">
        ${s?z():d}${_s(e.state)}
        ${s&&e.progress!=null?l` · ${Math.round(e.progress)}%`:d}
      </span>
      ${r}
      <p class="job-detail ${e.state==="error"?"error":""}">${vs(e,this._now)}</p>
    </li>`}_liveLine(){let e=this._live;return l`<div>
      <h3 class="code" style="margin:4px 0 8px">${a("panel.import.live_title")}</h3>
      ${this._liveError?l`<p class="note error">${a("panel.import.live_error",{error:this._liveError})}</p>`:e?l`<div class="live" role="status">
              <span class="live-state"
                ><span class="dot ${e.connected?"on":""}" aria-hidden="true"></span
                >${e.connected?a("panel.import.live_connected"):a("panel.import.live_disconnected")}</span
              >
              ${e.server_version?l`<span>${a("panel.import.live_version",{version:e.server_version})}</span>`:d}
              <span>${a("panel.import.live_plays",{count:e.plays_captured})}</span>
              <span
                >${e.last_play?e.last_play_at?a("panel.import.live_last_play_when",{play:e.last_play,when:be(e.last_play_at,this._now)}):a("panel.import.live_last_play",{play:e.last_play}):a("panel.import.live_no_play")}</span
              >
              ${e.last_error?l`<span class="error"
                    >${a("panel.import.live_last_error",{error:e.last_error})}</span
                  >`:d}
            </div>`:l`<p class="hint">${a("loading")}</p>`}
    </div>`}};customElements.get("lg-import-view")||customElements.define("lg-import-view",tt);var st=class extends f{constructor(){super(...arguments);this.narrow=!1;this._navigate=e=>{let s=this.route?.prefix??"/listening-genome";history.pushState(null,"",`${s}${e}`),window.dispatchEvent(new CustomEvent("location-changed",{detail:{replace:!1}}))}}static{this.properties={hass:{attribute:!1},narrow:{type:Boolean},route:{attribute:!1},panel:{attribute:!1}}}static{this.styles=[y,b`
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
    `]}connectedCallback(){super.connectedCallback(),yt(this.panel?.config?.static_base??"/listening_genome_static")}get api(){if(this.hass)return this._apiFor!==this.hass&&((!this._api||!this._apiFor)&&(this._api=new ce(this.hass)),this._apiFor=this.hass),this._api}_toggleMenu(){this.dispatchEvent(new CustomEvent("hass-toggle-menu",{bubbles:!0,composed:!0}))}render(){let e=this.api;if(!e)return d;let s=(this.route?.path??"").startsWith("/import");return l`
      ${this.narrow?l`<button class="menu" aria-label="Menu" @click=${this._toggleMenu}>
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
              <path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z" />
            </svg>
          </button>`:d}
      ${s?l`<lg-import-view
            .api=${e}
            .isAdmin=${this.hass?.user?.is_admin??!1}
            .narrow=${this.narrow}
            @navigate=${i=>this._navigate(i.detail)}
          ></lg-import-view>`:l`<lg-genome-view
            .api=${e}
            .isAdmin=${this.hass?.user?.is_admin??!1}
            .narrow=${this.narrow}
            @navigate=${i=>this._navigate(i.detail)}
          ></lg-genome-view>`}
    `}};customElements.get("listening-genome-panel")||customElements.define("listening-genome-panel",st);export{st as ListeningGenomePanel};
/*! Bundled license information:

@lit/reactive-element/css-tag.js:
  (**
   * @license
   * Copyright 2019 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/reactive-element.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/lit-html.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-element/lit-element.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/is-server.js:
  (**
   * @license
   * Copyright 2022 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)
*/
