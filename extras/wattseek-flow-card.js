/* WattSeek Flow Card v1.2 — animated energy flow for WattSeek hybrid inverters */
class WattseekFlowCard extends HTMLElement {
  static getStubConfig() { return { prefix: "sensor.koridor_invertor" }; }
  setConfig(c) {
    const p = c.prefix || "sensor.koridor_invertor";
    const b = p.replace(/^sensor\./, "binary_sensor.");
    this._c = Object.assign({
      title: "Енергосистема",
      pv: p + "_pv_power", grid: p + "_grid_power", load: p + "_load_power",
      batt: p + "_battery_power", soc: p + "_battery_soc", bv: p + "_battery_voltage",
      gv: p + "_grid_voltage", ov: p + "_output_voltage", pct: p + "_output_percentage",
      online: b + "_inverter_online", gridok: b + "_grid_connected",
      problem: b + "_problem", status: p + "_status",
      faults: p + "_faults", alarms: p + "_alarms", stage: p + "_charging_stage",
      pv_today: p + "_pv_energy_today", grid_today: p + "_grid_import_today", out_today: p + "_output_energy_today",
      capacity_kwh: 5, battery_invert: false
    }, c);
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._built = false;
  }
  getCardSize() { return 7; }
  getGridOptions() { return { columns: 12, rows: 8, min_rows: 6 }; }
  _n(id) { const s = this._h && this._h.states[id]; const v = s ? parseFloat(s.state) : NaN; return isNaN(v) ? 0 : v; }
  _s(id) { const s = this._h && this._h.states[id]; return s ? s.state : "unavailable"; }
  _w(v) { const a = Math.abs(v); return a >= 1000 ? (a / 1000).toFixed(2) + " кВт" : Math.round(a) + " Вт"; }
  _build() {
    const r = this.shadowRoot;
    r.innerHTML = `
<style>
:host{display:block}
ha-card{overflow:hidden;position:relative;padding:16px 16px 12px;color:var(--primary-text-color);
 background:radial-gradient(120% 90% at 50% 0%,rgba(56,189,248,.10),transparent 60%),
 radial-gradient(90% 70% at 50% 110%,rgba(52,211,153,.10),transparent 60%),var(--ha-card-background,var(--card-background-color));}
.hd{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px}
.tt{font-size:18px;font-weight:600;letter-spacing:.2px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{font-size:11px;font-weight:600;padding:4px 9px;border-radius:999px;display:flex;align-items:center;gap:5px;
 background:rgba(127,127,127,.14);color:var(--secondary-text-color)}
.chip i{width:7px;height:7px;border-radius:50%;background:currentColor;display:inline-block}
.chip.ok{color:#34d399;background:rgba(52,211,153,.13)} .chip.bad{color:#f87171;background:rgba(248,113,113,.13)}
.chip.bad i{animation:bl 1.2s infinite}
@keyframes bl{50%{opacity:.25}}
svg{width:100%;height:auto;display:block}
.ln{fill:none;stroke:rgba(127,127,127,.22);stroke-width:2.5;stroke-linecap:round}
.ln.on{stroke-width:3}
.nd{cursor:pointer}
.nd circle.bg{fill:var(--ha-card-background,var(--card-background-color));stroke-width:3}
.nd text{fill:var(--primary-text-color);text-anchor:middle;font-family:inherit}
.v{font-size:15px;font-weight:700} .l{font-size:11px;fill:var(--secondary-text-color)!important;font-weight:500}
.sub{font-size:10.5px;fill:var(--secondary-text-color)!important}
.dot{filter:drop-shadow(0 0 4px currentColor)}
#inv{cursor:pointer}
.scrt{fill:#34d399;font-size:9px;font-weight:700;text-anchor:middle;font-family:ui-monospace,monospace;letter-spacing:.4px}
.scrs{fill:#a7f3d0;font-size:8.5px;text-anchor:middle;font-family:ui-monospace,monospace}
.ledl{fill:#4b5563;font-size:4.2px;text-anchor:middle;font-family:inherit;font-weight:700}
.ft{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:6px}
.st{border-radius:12px;padding:8px 10px;background:rgba(127,127,127,.08)}
.st b{display:block;font-size:15px} .st span{font-size:11px;color:var(--secondary-text-color)}
.dim{opacity:.45}
.blink{animation:ledb 1s steps(1) infinite}
@keyframes ledb{50%{opacity:.12}}
</style>
<ha-card>
 <div class="hd"><div class="tt"></div><div class="chips"><div class="chip" id="cOn"><i></i><span></span></div><div class="chip" id="cGr"><i></i><span></span></div></div></div>
 <svg viewBox="0 0 400 330">
  <defs>
   <linearGradient id="gInv" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#eef0f3"/><stop offset=".55" stop-color="#c9ced6"/><stop offset="1" stop-color="#9aa1ac"/></linearGradient>
  </defs>
  <path id="pPv" class="ln" d="M200 92 L200 121"/>
  <path id="pGr" class="ln" d="M92 165 L166 165"/>
  <path id="pLd" class="ln" d="M234 165 L308 165"/>
  <path id="pBt" class="ln" d="M200 209 L200 238"/>
  <g id="dots"></g>
  <g id="inv" data-e="status">
   <rect x="168" y="124" width="68" height="88" rx="11" fill="rgba(0,0,0,.28)"/>
   <rect x="166" y="121" width="68" height="88" rx="11" fill="url(#gInv)" stroke="rgba(255,255,255,.4)" stroke-width="1"/>
   <rect id="scr" x="175" y="131" width="50" height="31" rx="5" fill="#0b1220" stroke="#34d399" stroke-width="1.5"/>
   <text id="iMode" class="scrt" x="200" y="145">—</text>
   <text id="iPct" class="scrs" x="200" y="156"></text>
   <circle id="lAc" cx="181" cy="171" r="2.8"/><circle id="lInv" cx="194" cy="171" r="2.8"/>
   <circle id="lChg" cx="207" cy="171" r="2.8"/><circle id="lFlt" cx="220" cy="171" r="2.8"/>
   <text class="ledl" x="181" y="180">AC</text><text class="ledl" x="194" y="180">INV</text>
   <text class="ledl" x="207" y="180">CHG</text><text class="ledl" x="220" y="180">FLT</text>
   <path d="M177 189 H223 M177 195 H223 M177 201 H223" stroke="rgba(0,0,0,.22)" stroke-width="2" stroke-linecap="round"/>
  </g>
  <g class="nd" id="nPv" data-e="pv" transform="translate(200,52)">
   <circle class="bg" r="40" stroke="#fbbf24"/>
   <path transform="translate(-12,-30) scale(1)" fill="#fbbf24" d="M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0-5 1.4 3h-2.8L12 2zm0 20-1.4-3h2.8L12 22zM2 12l3-1.4v2.8L2 12zm20 0-3 1.4v-2.8L22 12zM4.9 4.9l3.1 1.1-2 2-1.1-3.1zm14.2 14.2-3.1-1.1 2-2 1.1 3.1zM4.9 19.1 6 16l2 2-3.1 1.1zM19.1 4.9 18 8l-2-2 3.1-1.1z"/>
   <text class="v" y="12" id="tPv"></text><text class="l" y="26">Сонце</text>
  </g>
  <g class="nd" id="nGr" data-e="grid" transform="translate(52,165)">
   <circle class="bg" r="40" stroke="#60a5fa"/>
   <path transform="translate(-12,-32)" fill="#60a5fa" d="M8.3 2 6 22h2.1l.7-3h6.4l.7 3H18L15.7 2H8.3zm1.6 2h4.2l.5 4H9.4l.5-4zm-.7 6h5.6l.6 4H8.6l.6-4zm-.9 6h7.4l.4 1H8.9l.4-1z"/>
   <text class="v" y="10" id="tGr"></text><text class="l" y="24">Мережа</text>
  </g>
  <g class="nd" id="nLd" data-e="load" transform="translate(348,165)">
   <circle class="bg" r="40" stroke="#a78bfa"/>
   <path transform="translate(-12,-32)" fill="#a78bfa" d="M12 3 2 12h3v8h5v-6h4v6h5v-8h3L12 3z"/>
   <text class="v" y="10" id="tLd"></text><text class="l" y="24">Дім</text>
  </g>
  <g class="nd" id="nBt" data-e="soc" transform="translate(200,278)">
   <circle class="bg" r="40" stroke="rgba(127,127,127,.25)"/>
   <circle id="ring" r="40" fill="none" stroke="#34d399" stroke-width="5" stroke-linecap="round" transform="rotate(-90)" stroke-dasharray="251.3" stroke-dashoffset="251.3" style="transition:stroke-dashoffset 1s,stroke .5s"/>
   <text class="v" y="-6" id="tSoc"></text><text class="sub" y="9" id="tBt"></text><text class="l" y="23" id="tBl">Батарея</text>
  </g>
  <text class="sub" x="52" y="222" text-anchor="middle" id="tGv"></text>
  <text class="sub" x="348" y="222" text-anchor="middle" id="tOv"></text>
 </svg>
 <div class="ft">
  <div class="st" data-e="pv_today"><b id="fPv"></b><span>☀️ Сонце сьогодні</span></div>
  <div class="st" data-e="grid_today"><b id="fGr"></b><span>⚡ З мережі сьогодні</span></div>
  <div class="st" data-e="out_today"><b id="fOut"></b><span>🏠 Спожито сьогодні</span></div>
 </div>
</ha-card>`;
    r.querySelectorAll("[data-e]").forEach(el => el.addEventListener("click", () => {
      const ev = new Event("hass-more-info", { bubbles: true, composed: true });
      ev.detail = { entityId: this._c[el.dataset.e] }; this.dispatchEvent(ev);
    }));
    this._flows = {};
    this._built = true;
  }
  _flow(key, pathId, color, watts, reverse) {
    const g = this.shadowRoot.getElementById("dots");
    const path = this.shadowRoot.getElementById(pathId);
    const active = Math.abs(watts) >= 5;
    path.classList.toggle("on", active);
    path.style.stroke = active ? color + "66" : "";
    const dur = active ? Math.max(0.6, Math.min(4, 3.2 - Math.log10(Math.abs(watts) + 1) * 0.8)) : 0;
    const sig = active ? `${dur.toFixed(1)}|${reverse}` : "off";
    const f = this._flows[key];
    if (f && f.sig === sig) return;
    if (f) f.els.forEach(e => e.remove());
    const els = [];
    if (active) {
      for (let i = 0; i < 3; i++) {
        const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        c.setAttribute("r", "4"); c.setAttribute("fill", color); c.setAttribute("class", "dot"); c.style.color = color;
        const m = document.createElementNS("http://www.w3.org/2000/svg", "animateMotion");
        m.setAttribute("dur", dur + "s"); m.setAttribute("repeatCount", "indefinite");
        m.setAttribute("begin", (-(dur / 3) * i).toFixed(2) + "s");
        if (reverse) { m.setAttribute("keyPoints", "1;0"); m.setAttribute("keyTimes", "0;1"); m.setAttribute("calcMode", "linear"); }
        const mp = document.createElementNS("http://www.w3.org/2000/svg", "mpath");
        mp.setAttributeNS("http://www.w3.org/1999/xlink", "href", "#" + pathId); mp.setAttribute("href", "#" + pathId);
        m.appendChild(mp); c.appendChild(m); g.appendChild(c); els.push(c);
      }
    }
    this._flows[key] = { sig, els };
  }
  set hass(h) {
    this._h = h;
    if (!this._built) this._build();
    const c = this._c, $ = id => this.shadowRoot.getElementById(id);
    const pv = this._n(c.pv), grid = this._n(c.grid), load = this._n(c.load);
    let bat = this._n(c.batt); if (c.battery_invert) bat = -bat;
    const soc = this._n(c.soc), online = this._s(c.online) === "on", gridok = this._s(c.gridok) === "on";
    $("tPv").textContent = this._w(pv);
    $("tGr").textContent = gridok ? this._w(grid) : "немає";
    $("tLd").textContent = this._w(load);
    $("tSoc").textContent = Math.round(soc) + "%";
    $("tBt").textContent = this._w(bat);
    $("tBl").textContent = Math.abs(bat) < 5 ? "Очікування" : bat > 0 ? "Розряд" : "Заряд";
    const ring = $("ring");
    ring.setAttribute("stroke-dashoffset", (251.3 * (1 - Math.max(0, Math.min(100, soc)) / 100)).toFixed(1));
    const sc = soc <= 20 ? "#f87171" : soc <= 45 ? "#fbbf24" : "#34d399";
    ring.setAttribute("stroke", sc);
    $("nPv").classList.toggle("dim", pv < 5);
    $("nGr").classList.toggle("dim", !gridok);
    const gv = this._n(c.gv), ov = this._n(c.ov), pct = this._n(c.pct);
    $("tGv").textContent = gridok ? gv.toFixed(0) + " В" : "";
    $("tOv").textContent = ov.toFixed(0) + " В · " + pct.toFixed(0) + "%";
    // Inverter body: screen shows mode + load, LEDs mirror the front panel.
    const st = this._s(c.status), prob = this._s(c.problem) === "on";
    const modes = { grid_mode: "МЕРЕЖА", battery_mode: "БАТАРЕЯ", solar_mode: "СОНЦЕ", standby: "ОЧІКУВ.", fault: "АВАРІЯ",
      power_off: "ВИМК.", generator_mode: "ГЕНЕР.", initialization: "СТАРТ", power_on: "СТАРТ", upgrade: "ОНОВЛ." };
    const scol = (prob || st === "fault") ? "#f87171" : !online ? "#6b7280" : "#34d399";
    $("iMode").textContent = modes[st] || (online ? "ONLINE" : "OFFLINE");
    $("iMode").style.fill = scol;
    $("iPct").textContent = online ? this._w(load) : "";
    $("scr").setAttribute("stroke", scol);
    // LEDs follow the inverter manual's front-panel table:
    // AC  green : solid = mains OK and in mains mode, flashing = mains OK but not in mains mode
    // INV yellow: solid = output powered by battery/PV (battery mode)
    // CHG yellow: solid = float charging, flashing = constant-voltage charging
    // FLT red   : solid = fault, flashing = warning
    const cnt = id => { const s = this._h && this._h.states[id]; return s && s.attributes ? Number(s.attributes.count) || 0 : 0; };
    const led = (id, mode, col) => {
      const e = $(id), on = mode !== "off";
      e.style.fill = on ? col : "rgba(0,0,0,.28)";
      e.style.filter = on ? `drop-shadow(0 0 3px ${col})` : "";
      e.classList.toggle("blink", mode === "blink");
    };
    const GREEN = "#22c55e", YELLOW = "#fbbf24", RED = "#ef4444";
    led("lAc", st === "grid_mode" ? "on" : gridok ? "blink" : "off", GREEN);
    led("lInv", (st === "battery_mode" || st === "solar_mode") ? "on" : "off", YELLOW);
    const stage = this._s(c.stage);
    const chg = stage === "float" ? "on"
      : (stage === "constant_voltage" || stage === "equalize") ? "blink"
      : (stage === "unavailable" || stage === "unknown") ? (bat < -5 ? "on" : "off")
      : "off";
    led("lChg", chg, YELLOW);
    led("lFlt", (cnt(c.faults) > 0 || st === "fault") ? "on" : cnt(c.alarms) > 0 ? "blink" : "off", RED);
    const t = this.shadowRoot.querySelector(".tt"); t.textContent = c.title;
    const co = $("cOn"); co.className = "chip " + (online ? "ok" : "bad"); co.querySelector("span").textContent = online ? "Онлайн" : "Офлайн";
    const cg = $("cGr"); cg.className = "chip " + (gridok ? "ok" : "bad"); cg.querySelector("span").textContent = gridok ? "Світло є" : "Світла немає";
    const kwh = id => { const v = this._n(id); return v.toFixed(v >= 10 ? 1 : 2) + " кВт·год"; };
    $("fPv").textContent = kwh(c.pv_today); $("fGr").textContent = kwh(c.grid_today); $("fOut").textContent = kwh(c.out_today);
    this._flow("pv", "pPv", "#fbbf24", pv, false);
    this._flow("gr", "pGr", "#60a5fa", gridok ? grid : 0, grid < 0);
    this._flow("ld", "pLd", "#a78bfa", load, false);
    this._flow("bt", "pBt", sc, bat, bat > 0);
  }
}
if (!customElements.get("wattseek-flow-card")) customElements.define("wattseek-flow-card", WattseekFlowCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "wattseek-flow-card", name: "WattSeek Flow Card", description: "Анімований потік енергії для інвертора WattSeek", preview: false });
