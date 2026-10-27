(() => {
  "use strict";
  const ua = navigator.userAgent || "";
  const platform = navigator.platform || "";
  const isIPad = /iPad/i.test(ua) || (platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const isIPhone = /iPhone|iPod/i.test(ua);
  const isIOS = isIPhone || isIPad;
  const isAndroid = /Android/i.test(ua);
  const isTablet = isIPad || /Tablet|PlayBook|Silk/i.test(ua) || (isAndroid && !/Mobile/i.test(ua));
  const isSamsung = /SamsungBrowser/i.test(ua) || /SM-[A-Z0-9]+/i.test(ua);
  const deviceType = isTablet
    ? (isIPad ? "ipad" : (isSamsung ? "samsung-tablet" : "tablet"))
    : (isIPhone ? "iphone" : (isSamsung ? "samsung" : (isAndroid ? "android" : (/Macintosh|MacIntel/i.test(ua + " " + platform) ? "mac" : "desktop"))));
  const installDismissKey = "laLigaInstallDismissed";
  const installNeverKey = "laLigaInstallNeverAsk";
  const installSessionDismissKey = "laLigaInstallDismissedThisSession";
  const notificationsKey = "laLigaResultNotifications";
  const isInstalledApp = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
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
    .install-modal-backdrop { position:fixed; inset:0; z-index:1100; display:flex; align-items:flex-end; justify-content:center; padding:0; background:rgba(7,18,32,.0); backdrop-filter:blur(0); animation:installBackdropIn .42s cubic-bezier(.2,.8,.2,1) forwards; }
    .install-modal { width:min(620px,100%); max-height:76vh; overflow:auto; position:relative; padding:1.6rem 1.35rem max(1.5rem,env(safe-area-inset-bottom)); border-radius:26px 26px 0 0; background:linear-gradient(145deg,#fff 0%,#f2f7fc 62%,#e7f1fb 100%); color:#243b53; box-shadow:0 -18px 70px rgba(0,0,0,.28); transform:translateY(105%); opacity:.8; animation:installSheetUp .72s cubic-bezier(.16,1,.3,1) .04s forwards; border:1px solid rgba(255,255,255,.8); border-bottom:0; }
    .install-modal::before { content:""; display:block; width:46px; height:5px; border-radius:99px; background:#b9c9d9; margin:-.55rem auto 1.15rem; }
    .install-modal h2 { font-size:clamp(1.3rem,5vw,1.65rem); line-height:1.2; margin:.4rem 2rem .6rem 0; letter-spacing:-.025em; }
    .install-modal p { color:#526579; line-height:1.5; }
    .install-modal .modal-actions { display:flex; gap:.6rem; flex-wrap:wrap; margin-top:1rem; }
    .install-modal button { border:0; border-radius:12px; padding:.75rem 1rem; font-weight:750; cursor:pointer; background:linear-gradient(135deg,#243b53,#356da8); color:#fff; box-shadow:0 7px 18px rgba(36,59,83,.18); transition:transform .2s ease,box-shadow .2s ease; }
    .install-modal button:hover { transform:translateY(-2px); box-shadow:0 10px 24px rgba(36,59,83,.24); }
    .install-modal button.secondary { background:#e6edf5; color:#243b53; box-shadow:none; }
    .install-modal .modal-close { position:absolute; right:.85rem; top:.85rem; background:#eaf0f6; color:#243b53; box-shadow:none; }
    .install-modal-backdrop.device-iphone .install-modal { animation:installIphoneUp .78s cubic-bezier(.2,1.35,.35,1) .03s both; }
    .install-modal-backdrop.device-samsung .install-modal { animation:installSamsungUp .72s cubic-bezier(.16,1.2,.3,1) .03s both; box-shadow:0 -20px 70px rgba(22,80,115,.32); }
    .install-modal-backdrop.device-android .install-modal { animation:installAndroidUp .68s cubic-bezier(.2,.9,.25,1) .03s both; }
    .install-modal-backdrop.device-ipad .install-modal,.install-modal-backdrop.device-tablet .install-modal,.install-modal-backdrop.device-samsung-tablet .install-modal { width:min(590px,calc(100vw - 2rem)); margin-bottom:1.5rem; border-radius:25px; border-bottom:1px solid rgba(255,255,255,.8); transform-origin:bottom center; }
    .install-modal-backdrop.device-ipad .install-modal { animation:installIPadLift .78s cubic-bezier(.2,1.25,.3,1) .03s both; }
    .install-modal-backdrop.device-tablet .install-modal { animation:installTabletLift .68s cubic-bezier(.18,.95,.28,1) .03s both; }
    .install-modal-backdrop.device-samsung-tablet .install-modal { animation:installSamsungTabLift .76s cubic-bezier(.16,1.15,.28,1) .03s both; box-shadow:0 -20px 70px rgba(22,80,115,.3); }
    .install-modal-backdrop.device-desktop,.install-modal-backdrop.device-mac { align-items:flex-end; justify-content:flex-end; padding:1.25rem; }
    .install-modal-backdrop.device-desktop .install-modal,.install-modal-backdrop.device-mac .install-modal { width:min(470px,calc(100vw - 2.5rem)); max-height:76vh; margin-bottom:.5rem; border-radius:24px; border-bottom:1px solid rgba(255,255,255,.8); transform-origin:bottom right; }
    .install-modal-backdrop.device-desktop .install-modal { animation:installDesktopRise .62s cubic-bezier(.18,1,.3,1) .02s both; }
    .install-modal-backdrop.device-mac .install-modal { animation:installMacRise .68s cubic-bezier(.2,1,.3,1) .02s both; }
    .install-modal .install-device-note { display:flex; gap:.6rem; align-items:center; padding:.7rem .8rem; border-radius:13px; background:rgba(224,235,247,.72); margin:.8rem 0; color:#314d68; font-size:.9rem; }
    .install-modal .install-device-note .device-symbol { font-size:1.35rem; }
    .install-modal .install-device-note strong { display:block; color:#243b53; }
    .install-modal .never-ask { background:transparent; color:#526579; box-shadow:none; padding:.6rem .35rem; text-decoration:underline; text-underline-offset:3px; }
    @keyframes installBackdropIn { from { background:rgba(7,18,32,0); backdrop-filter:blur(0); } to { background:rgba(7,18,32,.58); backdrop-filter:blur(5px); } }
    @keyframes installSheetUp { 0% { transform:translateY(110%); opacity:.75; } 72% { transform:translateY(-6px); opacity:1; } 100% { transform:translateY(0); opacity:1; } }
    @keyframes installIphoneUp { 0% { transform:translateY(115%) scale(.96); opacity:.7; } 68% { transform:translateY(-9px) scale(1.005); opacity:1; } 100% { transform:translateY(0) scale(1); opacity:1; } }
    @keyframes installSamsungUp { 0% { transform:translateY(115%) rotate(1deg); opacity:.65; filter:blur(3px); } 65% { transform:translateY(-8px) rotate(0); opacity:1; filter:blur(0); } 100% { transform:translateY(0); opacity:1; filter:blur(0); } }
    @keyframes installAndroidUp { 0% { transform:translateY(115%); opacity:.65; } 75% { transform:translateY(-5px); opacity:1; } 100% { transform:translateY(0); opacity:1; } }
    @keyframes installTabletLift { 0% { transform:translateY(80px) scale(.96); opacity:0; } 70% { transform:translateY(-5px) scale(1.008); opacity:1; } 100% { transform:translateY(0) scale(1); opacity:1; } }
    @keyframes installIPadLift { 0% { transform:translateY(95px) rotateX(9deg) scale(.93); opacity:0; filter:blur(3px); } 68% { transform:translateY(-6px) rotateX(0) scale(1.01); opacity:1; filter:blur(0); } 100% { transform:translateY(0) rotateX(0) scale(1); opacity:1; filter:blur(0); } }
    @keyframes installSamsungTabLift { 0% { transform:translateY(105px) translateX(14px) scale(.94); opacity:0; } 65% { transform:translateY(-6px) translateX(0) scale(1.01); opacity:1; } 100% { transform:translateY(0) translateX(0) scale(1); opacity:1; } }
    @keyframes installDesktopRise { 0% { transform:translateY(75px) scale(.94); opacity:0; } 70% { transform:translateY(-4px) scale(1.005); opacity:1; } 100% { transform:translateY(0) scale(1); opacity:1; } }
    @keyframes installMacRise { 0% { transform:translateY(70px) translateX(18px) scale(.93); opacity:0; } 68% { transform:translateY(-5px) translateX(0) scale(1.01); opacity:1; } 100% { transform:translateY(0) translateX(0) scale(1); opacity:1; } }
    @media(max-width:600px) {
      .install-modal-backdrop.device-desktop,.install-modal-backdrop.device-mac { justify-content:center; padding:0; }
      .install-modal-backdrop.device-desktop .install-modal,.install-modal-backdrop.device-mac .install-modal { width:100%; margin:0; border-radius:26px 26px 0 0; border-bottom:0; animation:installSheetUp .72s cubic-bezier(.16,1,.3,1) .03s both; }
      .install-modal-backdrop.device-ipad .install-modal,.install-modal-backdrop.device-tablet .install-modal,.install-modal-backdrop.device-samsung-tablet .install-modal { width:100%; margin-bottom:0; border-radius:26px 26px 0 0; border-bottom:0; }
    }
    @media(prefers-reduced-motion:reduce) { .install-modal-backdrop,.install-modal { animation:none !important; } .install-modal { transform:none; opacity:1; filter:none; } }
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
    try {
      // Compatibilidad con el aviso persistente de versiones anteriores.
      if (localStorage.getItem(installDismissKey) === "1") {
        localStorage.removeItem(installDismissKey);
        sessionStorage.setItem(installSessionDismissKey, "1");
      }
      if (isInstalledApp() || localStorage.getItem(installNeverKey) === "1" ||
          sessionStorage.getItem(installSessionDismissKey) === "1" ||
          document.querySelector(".install-modal-backdrop")) return;
    } catch (_) {
      if (isInstalledApp() || document.querySelector(".install-modal-backdrop")) return;
    }

    const deviceInfo = {
      iphone: {
        badge: "IPHONE · SAFARI", title: "La Liga, siempre a mano en tu iPhone",
        message: "Añádela a tu pantalla de inicio y ábrela como una app, sin tener que buscar la web cada vez.",
        note: "En iPhone, la instalación se hace desde Safari.", symbol: ""
      },
      ipad: {
        badge: "IPAD · TABLET", title: "Tu liga, también en el iPad",
        message: "Pon La Liga en la pantalla de inicio de tu iPad para entrar al calendario y los resultados con un toque.",
        note: "Usa Safari y el menú Compartir.", symbol: "▣"
      },
      samsung: {
        badge: "SAMSUNG GALAXY", title: "La Liga en tu Samsung",
        message: "Añade La Liga a la pantalla de inicio de tu Galaxy para acceder rápidamente como si fuera una app.",
        note: "Funciona desde Samsung Internet o Chrome.", symbol: "◈"
      },
      "samsung-tablet": {
        badge: "SAMSUNG · TABLET", title: "La Liga en tu Galaxy Tab",
        message: "Instala un acceso directo en tu tablet para consultar los partidos cómodamente en pantalla grande.",
        note: "Abre el menú del navegador de tu tablet.", symbol: "▣"
      },
      android: {
        badge: "ANDROID", title: "Lleva La Liga en tu móvil",
        message: "Añádela a tu pantalla de inicio y tendrás el calendario y los resultados listos con un toque.",
        note: "Chrome suele ofrecer la opción Instalar aplicación.", symbol: "📱"
      },
      tablet: {
        badge: "TABLET ANDROID", title: "La Liga en pantalla grande",
        message: "Añade La Liga a la pantalla de inicio de tu tablet para consultar la competición de forma más cómoda.",
        note: "Abre el menú del navegador para instalarla.", symbol: "▣"
      },
      mac: {
        badge: "MAC · ORDENADOR", title: "Ten La Liga en tu Mac",
        message: "Añade La Liga al Dock o instala la app desde el navegador para abrirla en una ventana independiente.",
        note: "Safari y Chrome muestran opciones diferentes.", symbol: "▰"
      },
      desktop: {
        badge: "PC · ORDENADOR", title: "Instala La Liga en tu ordenador",
        message: "Abre La Liga como una aplicación independiente desde tu PC y vuelve a los resultados cuando quieras.",
        note: "Chrome y Edge suelen mostrar el icono de instalación junto a la barra de direcciones.", symbol: "▰"
      }
    }[deviceType] || {
      badge: "LA LIGA · APLICACIÓN", title: "¿Quieres añadir esto como una aplicación?",
      message: "Ten el calendario y los resultados de La Liga a mano desde tu pantalla de inicio.",
      note: "Busca la opción de instalar o añadir a pantalla de inicio en el menú del navegador.", symbol: "📲"
    };

    const backdrop = document.createElement("div");
    backdrop.className = "install-modal-backdrop device-" + deviceType;
    backdrop.setAttribute("role", "dialog");
    backdrop.setAttribute("aria-modal", "true");
    backdrop.setAttribute("aria-labelledby", "install-app-title");
    const modal = document.createElement("section");
    modal.className = "install-modal";
    modal.innerHTML = '<button type="button" class="modal-close" aria-label="Cerrar">×</button>' +
      '<span class="install-platform"></span><h2 id="install-app-title"></h2>' +
      '<p class="install-message"></p><div class="install-device-note"><span class="device-symbol" aria-hidden="true"></span><span class="device-note-text"></span></div>' +
      '<ol id="install-steps"></ol><div class="modal-actions">' +
      '<button type="button" id="install-app-button">Añadir aplicación</button>' +
      '<button type="button" class="secondary" id="dismiss-install">Ahora no</button>' +
      '<button type="button" class="never-ask" id="never-ask-install">No preguntar nunca más</button></div>' +
      '<p class="install-hint" id="install-hint">Puedes decidir ahora o desactivar este aviso para siempre desde aquí.</p>';
    modal.querySelector(".install-platform").textContent = deviceInfo.badge;
    modal.querySelector("#install-app-title").textContent = deviceInfo.title;
    modal.querySelector(".install-message").textContent = deviceInfo.message;
    modal.querySelector(".device-symbol").textContent = deviceInfo.symbol;
    modal.querySelector(".device-note-text").textContent = deviceInfo.note;
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);

    const steps = modal.querySelector("#install-steps");
    const button = modal.querySelector("#install-app-button");
    const hint = modal.querySelector("#install-hint");
    const addStep = text => {
      const item = document.createElement("li");
      item.textContent = text;
      steps.appendChild(item);
    };
    if (deviceType === "iphone") {
      addStep("Abre esta web en Safari.");
      addStep("Pulsa Compartir y elige «Añadir a pantalla de inicio».");
      addStep("Confirma y abre La Liga desde el icono nuevo.");
    } else if (deviceType === "ipad") {
      addStep("Abre la web en Safari en tu iPad.");
      addStep("Pulsa Compartir → «Añadir a pantalla de inicio».");
      addStep("Confirma y abre el icono de La Liga.");
    } else if (deviceType === "samsung" || deviceType === "samsung-tablet") {
      addStep("Abre el menú de Samsung Internet o Chrome.");
      addStep("Pulsa «Añadir a pantalla de inicio» o «Instalar aplicación».");
      addStep("Confirma la instalación y abre La Liga desde el icono.");
    } else if (deviceType === "android" || deviceType === "tablet") {
      addStep("Abre el menú ⋮ de Chrome.");
      addStep("Elige «Instalar aplicación» o «Añadir a pantalla de inicio».");
      addStep("Confirma y abre La Liga desde el nuevo icono.");
    } else if (deviceType === "mac") {
      addStep("En Safari, utiliza Compartir → «Añadir al Dock» si aparece.");
      addStep("En Chrome, pulsa el icono de instalación o abre el menú del navegador.");
      addStep("Abre La Liga desde el Dock o desde Aplicaciones.");
    } else {
      addStep("En Chrome o Edge, busca el icono de instalación junto a la barra de direcciones.");
      addStep("También puedes abrir el menú ⋮ y elegir «Instalar página como aplicación».");
      addStep("Confirma y abre La Liga desde el menú de aplicaciones.");
    }

    const close = () => {
      backdrop.classList.add("is-closing");
      backdrop.remove();
    };
    const dismiss = () => {
      try { sessionStorage.setItem(installSessionDismissKey, "1"); } catch (_) {}
      close();
    };
    const neverAsk = () => {
      try {
        localStorage.setItem(installNeverKey, "1");
        sessionStorage.removeItem(installSessionDismissKey);
      } catch (_) {}
      close();
    };
    modal.querySelector(".modal-close").addEventListener("click", dismiss);
    modal.querySelector("#dismiss-install").addEventListener("click", dismiss);
    modal.querySelector("#never-ask-install").addEventListener("click", neverAsk);
    backdrop.addEventListener("click", event => { if (event.target === backdrop) dismiss(); });
    if (!deferredPrompt) button.hidden = true;
    button.addEventListener("click", async () => {
      if (!deferredPrompt) {
        hint.textContent = "Sigue los pasos indicados para añadir La Liga desde el menú de tu navegador.";
        return;
      }
      deferredPrompt.prompt();
      try {
        const choice = await deferredPrompt.userChoice;
        if (choice && choice.outcome === "accepted") {
          try { sessionStorage.setItem(installSessionDismissKey, "1"); } catch (_) {}
        } else {
          try { sessionStorage.setItem(installSessionDismissKey, "1"); } catch (_) {}
        }
      } catch (_) {}
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
    try { sessionStorage.setItem(installSessionDismissKey, "1"); } catch (_) {}
    document.querySelector(".install-modal-backdrop")?.remove();
    showToast("La Liga instalada", "La app ya está lista. Abre el icono instalado para configurar los avisos.");
  });

  function addNotificationSettings() {
    if (!isInstalledApp() || !("Notification" in window)) return;
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
      if (!enabled.checked) {
        status.textContent = "Activa y guarda las notificaciones antes de enviar una prueba.";
        return;
      }
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
    if (!isInstalledApp() || checkInProgress || !("Notification" in window) ||
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