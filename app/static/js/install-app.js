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
    .install-modal-backdrop { position:fixed; inset:0; z-index:1100; display:grid; place-items:center; padding:1rem; background:rgba(12,25,40,.62); backdrop-filter:blur(4px); }
    .install-modal { width:min(460px,100%); max-height:90vh; overflow:auto; position:relative; padding:1.4rem; border-radius:20px; background:#fff; color:#243b53; box-shadow:0 24px 80px rgba(0,0,0,.3); }
    .install-modal h2 { font-size:1.35rem; margin:.4rem 2rem .6rem 0; }
    .install-modal p { color:#526579; }
    .install-modal .modal-actions { display:flex; gap:.6rem; flex-wrap:wrap; margin-top:1rem; }
    .install-modal button { border:0; border-radius:9px; padding:.65rem .9rem; font-weight:700; cursor:pointer; background:#243b53; color:#fff; }
    .install-modal button.secondary { background:#eaf0f6; color:#243b53; }
    .install-modal .modal-close { position:absolute; right:.7rem; top:.7rem; background:#eaf0f6; color:#243b53; }
    .result-notifications { margin:1rem 0; padding:1rem; border-radius:14px; background:#fff; border:1px solid #cbd9e8; color:#243b53; }
    .result-notifications p { margin:.2rem 0 .8rem; font-size:.88rem; color:#526579; }
    .notification-controls { display:grid; gap:.65rem; }
    .notification-controls label { display:flex; align-items:center; gap:.55rem; font-size:.92rem; }
    .notification-actions { display:flex; gap:.5rem; flex-wrap:wrap; margin-top:.8rem; }
    .result-notifications button { border:0; border-radius:9px; background:#243b53; color:#fff; padding:.6rem .85rem; font-weight:700; }
    .result-notifications button.secondary { background:#eaf0f6; color:#243b53; }
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
        document.querySelector(".install-modal-backdrop")) return;
    const backdrop = document.createElement("div");
    backdrop.className = "install-modal-backdrop";
    backdrop.setAttribute("role", "dialog");
    backdrop.setAttribute("aria-modal", "true");
    backdrop.setAttribute("aria-labelledby", "install-app-title");
    const modal = document.createElement("section");
    modal.className = "install-modal";
    modal.innerHTML = `
      <button type="button" class="modal-close" aria-label="Cerrar">×</button>
      <span class="install-platform">📲 LA LIGA EN TU DISPOSITIVO</span>
      <h2 id="install-app-title">¿Quieres añadir esto como una aplicación?</h2>
      <p>Ten el calendario y los resultados de La Liga a mano desde tu pantalla de inicio.</p>
      <ol id="install-steps"></ol>
      <div class="modal-actions">
        <button type="button" id="install-app-button" hidden>Añadir aplicación</button>
        <button type="button" class="secondary" id="dismiss-install">Ahora no</button>
      </div>
      <p class="install-hint" id="install-hint">Puedes rechazarlo ahora y cambiar de opinión cuando quieras desde los ajustes del navegador.</p>`;
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);
    const steps = modal.querySelector("#install-steps");
    const button = modal.querySelector("#install-app-button");
    const hint = modal.querySelector("#install-hint");
    const close = () => backdrop.remove();
    const dismiss = () => { localStorage.setItem(installDismissKey, "1"); close(); };
    modal.querySelector(".modal-close").addEventListener("click", dismiss);
    modal.querySelector("#dismiss-install").addEventListener("click", dismiss);
    backdrop.addEventListener("click", event => { if (event.target === backdrop) dismiss(); });
    if (isIOS) {
      steps.innerHTML = "<li>Abre esta web con <strong>Safari</strong>.</li><li>Pulsa <strong>Compartir → Añadir a pantalla de inicio</strong>.</li><li>Confirma y abre el icono de La Liga.</li>";
    } else if (isSamsung) {
      steps.innerHTML = "<li>Abre el menú de Samsung Internet o Chrome.</li><li>Elige <strong>Añadir a pantalla de inicio</strong> o <strong>Instalar aplicación</strong>.</li>";
    } else if (isAndroid) {
      steps.innerHTML = "<li>En Chrome, abre el menú ⋮.</li><li>Elige <strong>Instalar aplicación</strong> o <strong>Añadir a pantalla de inicio</strong>.</li>";
    } else {
      steps.innerHTML = "<li>En Chrome o Edge, usa el icono de instalación de la barra de direcciones o el menú.</li><li>En Safari para macOS, usa <strong>Compartir → Añadir al Dock</strong>.</li>";
    }
    if (deferredPrompt) button.hidden = false;
    button.addEventListener("click", async () => {
      if (!deferredPrompt) {
        hint.textContent = "Sigue las instrucciones anteriores para añadirla desde el menú del navegador.";
        return;
      }
      deferredPrompt.prompt();
      try { await deferredPrompt.userChoice; } catch (_) {}
      deferredPrompt = null;
      close();
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
    document.querySelector(".install-modal-backdrop")?.remove();
    showToast("La Liga instalada", "La app ya está lista en tu dispositivo.");
  });

  function addNotificationSettings() {
    if (!("Notification" in window)) return;
    const main = document.querySelector("main.container");
    if (!main || document.querySelector(".result-notifications")) return;
    const panel = document.createElement("section");
    panel.className = "result-notifications";
    panel.innerHTML = `
      <strong>🔔 Ajustes de notificaciones</strong>
      <p>Elige qué avisos quieres recibir. Por ahora se envían mientras La Liga está abierta en este navegador.</p>
      <div class="notification-controls">
        <label><input type="checkbox" id="notify-enabled"> Activar notificaciones</label>
        <label><input type="checkbox" id="notify-new"> Avisarme de resultados nuevos</label>
        <label><input type="checkbox" id="notify-updated"> Avisarme si cambia un resultado</label>
      </div>
      <div class="notification-actions">
        <button type="button" id="notify-save">Guardar preferencias</button>
        <button type="button" class="secondary" id="notify-test">Enviar notificación de prueba</button>
      </div>
      <p id="notify-status" aria-live="polite"></p>`;
    main.prepend(panel);
    const enabled = panel.querySelector("#notify-enabled");
    const newResults = panel.querySelector("#notify-new");
    const updatedResults = panel.querySelector("#notify-updated");
    const status = panel.querySelector("#notify-status");
    const readPrefs = () => {
      try { return JSON.parse(localStorage.getItem(notificationsKey) || "{}"); }
      catch (_) { return {}; }
    };
    const prefs = readPrefs();
    enabled.checked = prefs.enabled === true;
    newResults.checked = prefs.newResults !== false;
    updatedResults.checked = prefs.updatedResults !== false;
    if (Notification.permission === "denied") {
      status.textContent = "El permiso está bloqueado en el navegador. Cámbialo en los ajustes del sitio para poder activar avisos.";
    } else if (enabled.checked && Notification.permission === "granted") {
      status.textContent = "Notificaciones activadas en este navegador.";
    } else {
      status.textContent = "Notificaciones desactivadas hasta que las actives y concedas permiso.";
    }

    panel.querySelector("#notify-save").addEventListener("click", async () => {
      if (!enabled.checked) {
        localStorage.setItem(notificationsKey, JSON.stringify({
          enabled:false, newResults:newResults.checked, updatedResults:updatedResults.checked
        }));
        status.textContent = "Notificaciones desactivadas. Puedes volver a activarlas cuando quieras.";
        return;
      }
      if (Notification.permission === "denied") {
        status.textContent = "El navegador bloquea los permisos. Actívalos desde los ajustes del sitio.";
        return;
      }
      let permission = Notification.permission;
      if (permission !== "granted") {
        try { permission = await Notification.requestPermission(); }
        catch (_) { permission = "denied"; }
      }
      if (permission !== "granted") {
        enabled.checked = false;
        status.textContent = "No se concedió permiso. Puedes cambiarlo desde los ajustes del navegador.";
        return;
      }
      localStorage.setItem(notificationsKey, JSON.stringify({
        enabled:true, newResults:newResults.checked, updatedResults:updatedResults.checked
      }));
      status.textContent = "Preferencias guardadas.";
      await checkResults(true);
    });

    panel.querySelector("#notify-test").addEventListener("click", async () => {
      if (Notification.permission !== "granted") {
        status.textContent = "Primero activa las notificaciones y concede el permiso del navegador.";
        return;
      }
      try {
        const notification = new Notification("Notificación de prueba · La Liga", {
          body:"¡Todo listo! Así verás los avisos de resultados.",
          icon:"/static/league-logo.svg",
          tag:"league-test-notification"
        });
        notification.onclick = () => { window.focus(); notification.close(); };
        status.textContent = "Notificación de prueba enviada a este dispositivo.";
      } catch (_) {
        status.textContent = "No se pudo mostrar la prueba. Comprueba el permiso del navegador.";
      }
    });
  }

    async function checkResults(firstCheck = false) {
    let prefs = {};
    try { prefs = JSON.parse(localStorage.getItem(notificationsKey) || "{}"); } catch (_) {}
    if (checkInProgress || !("Notification" in window) ||
        Notification.permission !== "granted" || prefs.enabled !== true) return;
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
        if ((isNew && !firstCheck && prefs.newResults !== false) || (!isNew && oldSignature !== item.signature && prefs.updatedResults !== false)) {
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