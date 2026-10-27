(() => {
  const ua = navigator.userAgent || "";
  const platform = navigator.platform || "";
  const isIOS = /iPhone|iPad|iPod/i.test(ua) || (platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const isSamsung = /SamsungBrowser/i.test(ua);
  const isAndroid = /Android/i.test(ua);
  const isStandalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const isChromium = /Chrome|Chromium|Edg/i.test(ua) && !isSamsung;
  let deferredPrompt = null;

  const style = document.createElement("style");
  style.textContent = `
    .install-app-card { margin: 1.5rem 0 2rem; padding: clamp(1.1rem, 3vw, 1.7rem); border: 1px solid #cbd9e8; border-radius: 18px; background: linear-gradient(135deg,#fff 0%,#edf4fb 100%); box-shadow: 0 10px 28px rgba(36,59,83,.08); }
    .install-app-card h2 { font-size: clamp(1.25rem,3vw,1.65rem); margin: 0 0 .45rem; color: #243b53; }
    .install-app-card p { margin-bottom: .75rem; }
    .install-app-card .install-platform { display:inline-flex; align-items:center; gap:.45rem; padding:.35rem .7rem; border-radius:999px; background:#e0ebf7; color:#243b53; font-size:.82rem; font-weight:750; margin-bottom:.8rem; }
    .install-app-card ol { padding-left:1.35rem; margin-bottom:1rem; }
    .install-app-card li { margin:.5rem 0; padding-left:.15rem; }
    .install-app-card .install-actions { display:flex; flex-wrap:wrap; gap:.6rem; align-items:center; }
    .install-app-card .install-hint { font-size:.9rem; color:#526579; margin:.8rem 0 0; }
    .install-app-card .install-button { display:none; border:0; border-radius:10px; padding:.7rem 1rem; background:#243b53; color:white; font-weight:700; }
    .install-app-card .install-button:focus-visible { outline:3px solid #8fb7df; outline-offset:2px; }
  `;
  document.head.appendChild(style);

  function addInstallCard() {
    if (document.querySelector(".install-app-card") || isStandalone) return;
    const main = document.querySelector("main.container");
    if (!main) return;
    const card = document.createElement("section");
    card.className = "install-app-card";
    card.setAttribute("aria-labelledby", "install-app-title");
    card.innerHTML = `
      <span class="install-platform" id="install-platform">📲 Instala La Liga</span>
      <h2 id="install-app-title">Lleva La Liga contigo</h2>
      <p>Accede más rápido al calendario, los resultados y la clasificación desde un icono en tu pantalla de inicio o escritorio.</p>
      <ol id="install-steps"></ol>
      <div class="install-actions">
        <button type="button" class="install-button" id="install-app-button">Instalar La Liga</button>
      </div>
      <p class="install-hint" id="install-hint">La instalación puede variar según el navegador y la versión del dispositivo.</p>
    `;
    main.appendChild(card);
    const steps = card.querySelector("#install-steps");
    const platform = card.querySelector("#install-platform");
    const hint = card.querySelector("#install-hint");
    const button = card.querySelector("#install-app-button");

    if (isIOS) {
      platform.textContent = "🍏 Instalación en iPhone o iPad";
      steps.innerHTML = "<li>Abre esta web desde <strong>Safari</strong>.</li><li>Pulsa <strong>Compartir</strong> (el cuadrado con la flecha).</li><li>Selecciona <strong>Añadir a pantalla de inicio</strong> y confirma.</li><li>Abre La Liga desde el nuevo icono cuando quieras consultar la competición.</li>";
      hint.textContent = "Si no aparece la opción, comprueba que estás usando Safari y no un navegador integrado dentro de otra aplicación.";
    } else if (isSamsung) {
      platform.textContent = "📱 Instalación en Samsung";
      steps.innerHTML = "<li>Abre La Liga en <strong>Samsung Internet</strong> o Chrome.</li><li>Abre el menú del navegador (☰ o ⋮).</li><li>Elige <strong>Añadir página a</strong> / <strong>Añadir a pantalla de inicio</strong> o <strong>Instalar aplicación</strong>, si aparece.</li><li>Confirma y abre La Liga desde el icono creado.</li>";
      hint.textContent = "El nombre exacto de la opción depende de la versión de Samsung Internet o Chrome.";
    } else if (isAndroid) {
      platform.textContent = "🤖 Instalación en Android";
      steps.innerHTML = "<li>Abre La Liga en <strong>Chrome</strong>.</li><li>Pulsa el menú de tres puntos (⋮).</li><li>Selecciona <strong>Instalar aplicación</strong> o <strong>Añadir a pantalla de inicio</strong>.</li><li>Confirma y entra desde el icono de La Liga.</li>";
      hint.textContent = "Si Chrome ofrece «Instalar aplicación», elige esa opción; si no, usa «Añadir a pantalla de inicio».";
    } else {
      platform.textContent = "💻 Instalación en ordenador";
      steps.innerHTML = "<li>Abre La Liga en <strong>Chrome</strong> o <strong>Microsoft Edge</strong>.</li><li>Busca el icono de instalación en la barra de direcciones o abre el menú del navegador.</li><li>Selecciona <strong>Instalar La Liga</strong> o <strong>Aplicaciones → Instalar este sitio como una aplicación</strong>.</li><li>Confirma. Después podrás abrirla desde el escritorio o el menú de aplicaciones.</li>";
      hint.textContent = "En macOS con Safari, usa Compartir → Añadir al Dock si esa opción está disponible. En otros navegadores, la instalación puede no estar disponible.";
    }

    if (isChromium || isAndroid || isSamsung) {
      button.style.display = "inline-block";
      button.addEventListener("click", async () => {
        if (!deferredPrompt) {
          hint.textContent = "Abre el menú del navegador y busca «Instalar aplicación» o «Añadir a pantalla de inicio».";
          return;
        }
        deferredPrompt.prompt();
        await deferredPrompt.userChoice;
        deferredPrompt = null;
        button.style.display = "none";
      });
    }
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    const button = document.getElementById("install-app-button");
    if (button) {
      button.style.display = "inline-block";
      button.textContent = "Instalar La Liga";
    }
  });

  window.addEventListener("appinstalled", () => {
    const card = document.querySelector(".install-app-card");
    if (card) card.innerHTML = "<h2>¡La Liga ya está instalada!</h2><p>Ábrela desde el icono para consultar la competición más rápido.</p>";
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", addInstallCard);
  else addInstallCard();
})();