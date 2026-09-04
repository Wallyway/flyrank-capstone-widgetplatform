(function () {
  "use strict";

  // Everything renders inside a shadow root. The host page's CSS cannot reach
  // in and ours cannot leak out, which is the only way a widget looks the same
  // on a site nobody here controls. The tokens below mirror design-tokens.css;
  // they are inlined because a shadow root inherits no stylesheet.
  var STYLE = `
  :host {
    all: initial;
    --font: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Inter, system-ui, sans-serif;
    --bg: #ffffff; --sunken: #f5f5f7;
    --text: #1d1d1f; --text-2: #6e6e73;
    --border: rgba(0,0,0,.10); --border-strong: rgba(0,0,0,.18);
    --accent: #0071e3; --accent-hover: #0077ed;
    --danger: #ff3b30; --success: #30d158;
    --shadow: 0 4px 24px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04);
    --shadow-lg: 0 12px 48px rgba(0,0,0,.14);
    --ease: cubic-bezier(.32,.72,0,1);
    display: block;
    font-family: var(--font);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
  }
  :host([data-theme="dark"]) {
    --bg: #1c1c1e; --sunken: #2c2c2e;
    --text: #f5f5f7; --text-2: #98989d;
    --border: rgba(255,255,255,.12); --border-strong: rgba(255,255,255,.22);
    --shadow: 0 4px 24px rgba(0,0,0,.5);
    --shadow-lg: 0 12px 48px rgba(0,0,0,.6);
  }

  * { box-sizing: border-box; margin: 0; font-family: inherit; }

  .card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 20px;
    box-shadow: var(--shadow);
    padding: 28px;
    max-width: 400px;
  }

  .title {
    font-size: 24px; font-weight: 600; line-height: 1.16;
    letter-spacing: -0.021em; color: var(--text);
  }
  .description {
    margin-top: 8px; font-size: 15px; line-height: 1.47;
    letter-spacing: -0.008em; color: var(--text-2);
  }

  form { margin-top: 22px; display: flex; flex-direction: column; gap: 14px; }
  .field { display: flex; flex-direction: column; gap: 6px; }
  .label {
    font-size: 13px; font-weight: 500; letter-spacing: -0.004em; color: var(--text-2);
  }
  .req { color: var(--text-2); opacity: .6; }

  input, textarea, select {
    width: 100%; padding: 11px 13px;
    font-size: 15px; letter-spacing: -0.008em; color: var(--text);
    background: var(--sunken);
    border: 1px solid transparent;
    border-radius: 10px;
    outline: none;
    transition: border-color 200ms var(--ease), box-shadow 200ms var(--ease), background 200ms var(--ease);
    -webkit-appearance: none; appearance: none;
  }
  textarea { min-height: 92px; resize: vertical; line-height: 1.47; }
  select {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1.5 6 6.5l5-5' stroke='%236e6e73' stroke-width='1.6' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 13px center;
    padding-right: 34px;
  }
  input::placeholder, textarea::placeholder { color: var(--text-2); opacity: .7; }

  /* The focus ring is accessibility, not decoration: it never gets removed. */
  input:focus, textarea:focus, select:focus {
    background: var(--bg);
    border-color: var(--accent);
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 22%, transparent);
  }
  .field.invalid input, .field.invalid textarea, .field.invalid select {
    border-color: var(--danger);
  }
  .hint { font-size: 12px; color: var(--danger); letter-spacing: -0.004em; }

  button {
    margin-top: 4px; height: 46px; width: 100%;
    font-size: 15px; font-weight: 600; letter-spacing: -0.01em;
    color: #fff; background: var(--accent);
    border: 0; border-radius: 12px; cursor: pointer;
    transition: background 200ms var(--ease), transform 200ms var(--ease), opacity 200ms var(--ease);
  }
  button:hover:not(:disabled) { background: var(--accent-hover); transform: translateY(-1px); }
  button:active:not(:disabled) { transform: translateY(0) scale(.99); }
  button:focus-visible { box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 30%, transparent); }
  button:disabled { opacity: .55; cursor: default; }

  .error {
    font-size: 13px; line-height: 1.4; color: var(--danger);
    letter-spacing: -0.004em;
  }

  /* The honeypot sits off-screen rather than display:none — some bots skip
     hidden inputs but happily fill a positioned one. Never read aloud. */
  .trap {
    position: absolute; left: -9999px; top: auto;
    width: 1px; height: 1px; overflow: hidden;
  }

  .done { text-align: center; padding: 8px 0 4px; }
  .check {
    width: 46px; height: 46px; margin: 0 auto 16px;
    border-radius: 50%; background: var(--success);
    display: flex; align-items: center; justify-content: center;
    animation: pop 420ms var(--ease) both;
  }
  .done .title { font-size: 19px; }
  @keyframes pop { from { transform: scale(.7); opacity: 0 } to { transform: scale(1); opacity: 1 } }
  @keyframes rise { from { transform: translateY(10px); opacity: 0 } to { transform: none; opacity: 1 } }

  /* Popover layout: a floating pill that opens a panel. */
  .launcher {
    position: fixed; right: 24px; bottom: 24px; z-index: 2147483000;
    height: 48px; width: auto; padding: 0 20px;
    display: inline-flex; align-items: center; gap: 8px;
    box-shadow: var(--shadow-lg);
  }
  .panel {
    position: fixed; right: 24px; bottom: 84px; z-index: 2147483000;
    width: 360px; max-width: calc(100vw - 48px);
    max-height: calc(100vh - 120px); overflow: auto;
    box-shadow: var(--shadow-lg);
    animation: rise 320ms var(--ease) both;
    backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
  }
  .close {
    position: absolute; top: 14px; right: 14px;
    height: 28px; width: 28px; margin: 0; padding: 0;
    border-radius: 50%; background: var(--sunken); color: var(--text-2);
    font-size: 16px; line-height: 1; display: flex; align-items: center; justify-content: center;
  }
  .close:hover:not(:disabled) { background: var(--border); transform: none; }
  .panel .card { border-radius: 20px; position: relative; }

  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: .01ms !important; transition-duration: .01ms !important; }
    button:hover:not(:disabled) { transform: none; }
  }
  `;

  var CHECK_SVG =
    '<svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">' +
    '<path d="M5 11.5 9 15.5 17 7" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function el(tag, props, children) {
    var node = document.createElement(tag);
    Object.keys(props || {}).forEach(function (key) {
      if (key === "text") node.textContent = props[key];
      else if (key === "html") node.innerHTML = props[key];
      else node.setAttribute(key, props[key]);
    });
    (children || []).forEach(function (child) { if (child) node.appendChild(child); });
    return node;
  }

  function buildInput(field) {
    var node;
    if (field.type === "textarea") {
      node = el("textarea", { rows: "3" });
    } else if (field.type === "select") {
      node = el("select", {}, [el("option", { value: "", text: "Choose one" })]);
      (field.options || []).forEach(function (option) {
        node.appendChild(el("option", { value: option, text: option }));
      });
    } else {
      var htmlType = field.type === "email" ? "email"
        : field.type === "number" ? "number"
        : field.type === "checkbox" ? "checkbox" : "text";
      node = el("input", { type: htmlType });
    }
    node.name = field.name;
    if (field.required) node.required = true;
    if (field.max_length && field.type !== "checkbox" && field.type !== "select") {
      node.setAttribute("maxlength", String(field.max_length));
    }
    return node;
  }

  function readValues(form, config) {
    var data = {};
    config.fields.forEach(function (field) {
      var input = form.elements[field.name];
      if (!input) return;
      var value = field.type === "checkbox" ? input.checked : input.value;
      if (value === "" && !field.required) return;
      data[field.name] = value;
    });
    return data;
  }

  function successCard(config) {
    return el("div", { class: "done" }, [
      el("div", { class: "check", html: CHECK_SVG }),
      el("h2", { class: "title", text: (config.options && config.options.success_message) || "Thanks." })
    ]);
  }

  function buildCard(config, onDone) {
    var card = el("div", { class: "card" });
    var header = el("div", {}, [
      el("h2", { class: "title", text: config.title }),
      config.description ? el("p", { class: "description", text: config.description }) : null
    ]);

    var form = el("form", { novalidate: "" });
    config.fields.forEach(function (field) {
      var input = buildInput(field);
      var wrapper = el("label", { class: "field" }, [
        el("span", { class: "label" }, [
          el("span", { text: field.label }),
          field.required ? el("span", { class: "req", text: " *" }) : null
        ]),
        input
      ]);
      form.appendChild(wrapper);
    });

    var trap = el("input", { type: "text", tabindex: "-1", autocomplete: "off", "aria-hidden": "true" });
    trap.name = config.honeypot_field;
    form.appendChild(el("div", { class: "trap" }, [trap]));

    var button = el("button", { type: "submit", text: config.button_text });
    var error = el("p", { class: "error", role: "alert" });
    form.appendChild(button);
    form.appendChild(error);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      button.disabled = true;
      button.textContent = "Sending…";
      error.textContent = "";

      var body = { widget_id: config.id, data: readValues(form, config) };
      body[config.honeypot_field] = trap.value;

      fetch(config.submit_url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }).then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (payload) {
          return { ok: response.ok, status: response.status, payload: payload };
        });
      }).then(function (result) {
        if (result.ok) {
          card.innerHTML = "";
          card.appendChild(successCard(config));
          if (onDone) onDone();
          return;
        }
        button.disabled = false;
        button.textContent = config.button_text;
        error.textContent = result.status === 429
          ? "Too many attempts. Give it a moment."
          : (result.payload.error || "Something went wrong. Try again.");
      }).catch(function () {
        button.disabled = false;
        button.textContent = config.button_text;
        error.textContent = "Could not reach the server.";
      });
    });

    card.appendChild(header);
    card.appendChild(form);
    return card;
  }

  function renderInline(root, config) {
    root.appendChild(buildCard(config, null));
  }

  function renderPopover(root, config) {
    var panel = null;
    var launcher = el("button", { type: "button", class: "launcher", text: config.button_text });

    function close() {
      if (!panel) return;
      panel.remove();
      panel = null;
      launcher.style.display = "";
    }

    launcher.addEventListener("click", function () {
      if (panel) return close();
      var card = buildCard(config, function () { setTimeout(close, 2200); });
      card.appendChild(el("button", { type: "button", class: "close", text: "✕", "aria-label": "Close" }));
      card.querySelector(".close").addEventListener("click", close);
      panel = el("div", { class: "panel" }, [card]);
      root.appendChild(panel);
      launcher.style.display = "none";
      var first = panel.querySelector("input, textarea, select");
      if (first) first.focus();
    });

    root.appendChild(launcher);
  }

  function applyTheme(hostElement, config) {
    var theme = (config.options && config.options.theme) || "auto";
    if (theme === "auto") {
      var dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");
      theme = dark && dark.matches ? "dark" : "light";
      if (dark && dark.addEventListener) {
        dark.addEventListener("change", function (event) {
          hostElement.setAttribute("data-theme", event.matches ? "dark" : "light");
        });
      }
    }
    hostElement.setAttribute("data-theme", theme);
  }

  function mount(request) {
    var host = request.mount;
    var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

    fetch(request.base + "/public/widgets/" + encodeURIComponent(request.widgetId) + "/config")
      .then(function (response) {
        if (!response.ok) throw new Error("config " + response.status);
        return response.json();
      })
      .then(function (config) {
        applyTheme(host, config);
        root.appendChild(el("style", { text: STYLE }));
        var layout = (config.options && config.options.layout) || "inline";
        if (layout === "popover") renderPopover(root, config);
        else renderInline(root, config);
      })
      // A widget that cannot load must not put an error on someone else's page.
      .catch(function (error) {
        if (window.console) console.warn("[lead-widget] " + error.message);
      });
  }

  window.LeadWidget = { mount: mount };

  var pending = window.__leadWidgetQueue || [];
  window.__leadWidgetQueue = [];
  pending.forEach(mount);
})();
