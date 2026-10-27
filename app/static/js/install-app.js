(() => {
  "use strict";
  const ua = navigator.userAgent || "";
  const platform = navigator.platform || "";
  const isIOS = /iPhone|iPad|iPod/i.test(ua) || (platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const isSamsung = /SamsungBrowser/i.test(ua) || /SM-[A-Z0-9]+/i.test(ua);
  const isAndroid = /Android/i.test(ua);
  const isStandalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const isChromium = /Chrome|Chromium|Edg/i.test(ua) && !/SamsungBrowser/i.test(ua);
  const installDismissKey = "laLigaInstallDismissed";
  const notificationsKey = "laLigaResultNotifications";
  let deferredPrompt = null;
  let knownResults = null;
  let checkInProgress = false;

  const style = document.createElement("style");
  style.textContent = `
    .league-toast { position:fixed; z-index:1080; right:1rem; bottom:1rem; width:min(390px,calc(100vw - 2rem)); background:#fff; color:#243b53; border:1px solid #cbd9e8; border-left:5px solid #356da8; border-radius:14px; box-shadow:0 12px 38px rgba(20,35,55,.22); padding:1rem 1.1rem; animation:leagueToastIn .25s ease-out; }
    .league-toast strong { display:block; margin-right:1.8rem; margin-bottom:.25rem; }
    .league-toast p { margin:0; font-size:.92rem; }
    .league-toast-close { position:absolute; top:.45rem; right:.55rem; border:0; background:transparent; font-size:1.25rem; color:#526579; padding:.2rem .45rem; }
    .league-toast-actions { display:flex; gap:.5rem; flex-wrap:wrap; margin-top:.8rem; }
    .league-toast-actions button { border:0; border-radius:8px; padding:.55rem .75rem; font-weight:700; background:#243b53; color:#fff; }
    .league-toast-actions .secondary { background:#eaf0f6; color:#243b53; }
    .install-app-card { position:relative; margin:1rem 0 1.5rem; padding:1rem 1.1rem; border:1px solid #cbd9e8; border-radius:16px; background:linear-gradient(135deg,#fff 0%,#edf4fb 100%); box-shadow:0 8px 24px rgba(36,59,83,.08); }
    .install-app-card h2 { font-size:1.2rem; margin:0 2rem .4rem 0; color:#243b53; }
    .install-app-card p { margin:0 0 .6rem; font-size:.93rem; }
    .install-app-card ol { padding-left:1.25rem; margin:.5rem 0 .8rem; }
    .install-app-card li { margin:.35rem 0; }
    .install-app-card .install-platform { display:inline-block; padding:.3rem .65rem; border-radius:999px; background:#e0ebf7; color:#243b53; font-size:.8rem; font-weight:750; margin-bottom:.65rem; }
    .install-app-card .install-button,.install-app-card .install-dismiss { border:0; border-radius:9px; padding:.6rem .8rem; font-weight:700; cursor:pointer; }
    .install-app-card .install-button { background:#243b53; color:#fff; }
    .install-app-card .install-dismiss { position:absolute; top:.65rem; right:.65rem; background:#eaf0f6; color:#243b53; font-size:.8rem; }
    .install-app-card .install-hint { color:#526579; font-size:.83rem; margin-top:.65rem; }
    .result-notifications { margin:1rem 0; padding:1rem; border-radius:14px; background:#fff; border:1px solid #cbd9e8; color:#243b53; display:flex; align-items:center; justify-content:space-between; gap:.75rem; flex-wrap:wrap; }
    .result-notifications p { margin:.2rem 0 0; font-size:.88rem; color:#526579; }
    .result-notifications button { border:0; border-radius:9px; background:#243b53; color:#fff; padding:.6rem .85rem; font-weight:700; }
    .result-notifications button:disabled { opacity:.7; }
    @keyframes leagueToastIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
    @media(prefers-reduced-motion:reduce) { .league-toast { animation:none; } }
  `;
  document.head.appendChild(style);

  function showToast(title, message, actions = []) {
    document.querySelectorAll(".league-toast").forEach(el => el.remove());
    const toast = document.createElement("aside");
    toast.className = "league-toast";
    toast.setAttribute("role", "status");
    const heading = document.createElement("strong");
    heading.textContent = title;
    const close = document.createElement("button");
    close.className = "league-toast-close";
    close.type = "button";
    close.setAttribute("aria-label", "Cerrar notificación");
    close.textContent = "×";
    close.addEventListener("click", () => toast.remove());
    const body = document.createElement("p");
    body.textContent = message;
    toast.append(close, heading, body);
    if (actions.length) {
      const row = document.createElement("div");
      row.className = "league-toast-actions";
      actions.forEach(action => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = action.label;
        if (action.secondary) button.className = "secondary";
        button.addEventListener("click", () => { toast.remove(); action.run(); });
        row.appendChild(button);
      });
      toast.appendChild(row);
    }
    document.body.appendChild(toast);
    window.setTimeout(() => toast.remove(), 12000);
  }

  function addInstallCard() {
    if (isStandalone || localStorage.getItem(installDismissKey) === "1" ||
        document.querySelector(".install-app-card")) return;
    const main = document.querySelector("main.container");
    if (!main) return;
    const card = document.createElement("section");
    card.className = "install-app-card";
    card.setAttribute("aria-labelledby", "install-app-title");
    card.innerHTML = `
      <button type="button" class="install-dismiss" id="dismiss-install">Ahora no ✕</button>
      <span class="install-platform" id="install-platform">📲 Instala La Liga</span>
      <h2 id="install-app-title">Lleva La Liga contigo</h2>
      <p>Abre el calendario y los resultados desde tu pantalla de inicio o escritorio.</p>
      <ol id="install-steps"></ol>
      <button type="button" class="install-button" id="install-app-button" hidden>Instalar La Liga</button>
      <p class="install-hint" id="install-hint">Puedes rechazar este aviso con «Ahora no».</p>`;
    main.appendChild(card);
    const steps = card.querySelector("#install-steps");
    const platformLabel = card.querySelector("#install-platform");
    const hint = card.querySelector("#install-hint");
    const button = card.querySelector("#install-app-button");
    card.querySelector("#dismiss-install").addEventListener("click", () => {
      localStorage.setItem(installDismissKey, "1");
      card.remove();
    });
    if (isIOS) {
      platformLabel.textContent = "🍏 Instalar en iPhone o iPad";
      steps.innerHTML = "<li>Abre la web con <strong>Safari</strong>.</li><li>Pulsa <strong>Compartir</strong> y después <strong>Añadir a pantalla de inicio</strong>.</li><li>Confirma la instalación y abre el icono de La Liga.</li>";
    } else if (isSamsung) {
      platformLabel.textContent = "📱 Instalar en Samsung";
      steps.innerHTML = "<li>Abre la web con Samsung Internet o Chrome.</li><li>Abre el menú del navegador.</li><li>Pulsa <strong>Añadir a pantalla de inicio</strong> o <strong>Instalar aplicación</strong>, si aparece.</li>";
    } else if (isAndroid) {
      platformLabel.textContent = "🤖 Instalar en Android";
      steps.innerHTML = "<li>Abre la web con Chrome.</li><li>Abre ⋮ y pulsa <strong>Instalar aplicación</strong> o <strong>Añadir a pantalla de inicio</strong>.</li><li>Confirma.</li>";
    } else {
      platformLabel.textContent = "💻 Instalar en ordenador";
      steps.innerHTML = "<li>En Chrome o Edge, busca el icono de instalación junto a la barra de direcciones o en el menú.</li><li>Selecciona <strong>Instalar La Liga</strong> y confirma.</li><li>En macOS con Safari, busca <strong>Compartir → Añadir al Dock</strong>.</li>";
    }
    if (deferredPrompt) button.hidden = false;
    button.addEventListener("click", async () => {
      if (!deferredPrompt) {
        hint.textContent = "Usa las instrucciones anteriores para instalarla desde el menú del navegador.";
        return;
      }
      deferredPrompt.prompt();
      try { await deferredPrompt.userChoice; } catch (_) {}
      deferredPrompt = null;
      button.hidden = true;
    });
  }

  window.addEventListener("beforeinstallprompt", event => {
    event.preventDefault();
    deferredPrompt = event;
    const button = document.getElementById("install-app-button");
    if (button) button.hidden = false;
  });
  window.addEventListener("appinstalled", () => {
    localStorage.setItem(installDismissKey, "1");
    document.querySelector(".install-app-card")?.remove();
    showToast("La Liga instalada", "La app ya está lista en tu dispositivo.");
  });

  function addNotificationSettings() {
    if (!("Notification" in window)) return;
    const main = document.querySelector("main.container");
    if (!main || document.querySelector(".result-notifications")) return;
    const panel = document.createElement("section");
    panel.className = "result-notifications";
    panel.innerHTML = '<div><strong>🔔 Avisos de resultados</strong><p>Activa las notificaciones para enterarte de los marcadores nuevos o actualizados mientras tengas La Liga abierta.</p></div><button type="button">Activar avisos</button>';
    const button = panel.querySelector("button");
    const syncButton = () => {
      if (Notification.permission === "granted" && localStorage.getItem(notificationsKey) === "1") {
        button.textContent = "Avisos activados";
        button.disabled = true;
      } else if (Notification.permission === "denied") {
        button.textContent = "Permiso bloqueado";
        button.disabled = true;
      }
    };
    button.addEventListener("click", async () => {
      if (!("Notification" in window)) return;
      try {
        const permission = await Notification.requestPermission();
        if (permission === "granted") {
          localStorage.setItem(notificationsKey, "1");
          button.textContent = "Avisos activados";
          button.disabled = true;
          await checkResults(true);
          showToast("Avisos activados", "Te avisaremos cuando se registren o cambien resultados con La Liga abierta.");
        } else {
          button.textContent = permission === "denied" ? "Permiso bloqueado" : "Puedes activarlos después";
          showToast("Avisos no activados", "Puedes cambiar los permisos de notificación en los ajustes de tu navegador.");
        }
      } catch (_) {
        showToast("No se pudieron activar", "Comprueba que estás usando una conexión segura y un navegador compatible.");
      }
    });
    main.prepend(panel);
    syncButton();
  }

  async function checkResults(firstCheck = false) {
    if (checkInProgress || !("Notification" in window) ||
        Notification.permission !== "granted" ||
        localStorage.getItem(notificationsKey) !== "1") return;
    checkInProgress = true;
    try {
      const response = await fetch("/matches/api/results", {
        headers: { Accept: "application/json" }, cache: "no-store"
      });
      if (!response.ok) return;
      const results = await response.json();
      if (knownResults === null) {
        knownResults = new Map(results.map(item => [String(item.id), item.signature]));
        return;
      }
      for (const item of results) {
        const id = String(item.id);
        const oldSignature = knownResults.get(id);
        const isNew = oldSignature === undefined;
        if ((isNew && !firstCheck) || (!isNew && oldSignature !== item.signature)) {
          const body = item.home + " " + item.home_goals + " – " + item.away_goals + " " + item.away;
          try {
            const notification = new Notification(isNew ? "Nuevo resultado · La Liga" : "Resultado actualizado · La Liga", {
              body, icon: "/static/league-logo.svg", tag: "league-result-" + id
            });
            notification.onclick = () => {
              window.focus();
              window.location.href = item.url;
            };
          } catch (_) {
            showToast("Resultado actualizado", body, [{label:"Ver partido",run:()=>{window.location.href=item.url;}}]);
          }
        }
        knownResults.set(id, item.signature);
      }
    } catch (_) {
      // La función de avisos no debe impedir que el resto de la web funcione.
    } finally {
      checkInProgress = false;
    }
  }

  function init() {
    addInstallCard();
    addNotificationSettings();
    checkResults();
    window.setInterval(() => checkResults(false), 60000);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();