(function () {
  "use strict";

  // Everything renders inside a shadow root. The host page's CSS cannot reach
  // in and ours cannot leak out, which is the only way a widget looks the same
  // on a site nobody here controls. The tokens mirror design-tokens.css; they
  // are inlined because a shadow root inherits no stylesheet.
  //
  // No @font-face here on purpose. Inter is asked for and used if the visitor
  // already has it, but this bundle never makes a customer's page download a
  // font — 70 KB on someone else's site is how a widget gets removed.
  var STYLE = `
  :host {
    all: initial;
    --font: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    --canvas: #ffffff;
    --surface-strong: #f0f0f3;
    --ink: #171717;
    --body: #60646c;
    --muted: #999999;
    --hairline: #f0f0f3;
    --hairline-strong: #dcdee0;
    --primary: #000000;
    --primary-active: #1a1a1a;
    --on-primary: #ffffff;
    --success: #16a34a;
    --error-line: #eb8e90;
    --shadow-card: 0 4px 12px rgba(0,0,0,.04);
    --ease: cubic-bezier(.32,.72,0,1);
    display: block;
    font-family: var(--font);
    color: var(--ink);
    -webkit-font-smoothing: antialiased;
  }

  /* Dark is a surface, not a theme. It exists because this widget can land on
     a dark page, and there the CTA inverts: black on #171717 would vanish. */
  :host([data-theme="dark"]) {
    --canvas: #171717;
    --surface-strong: #1a1a1a;
    --ink: #ffffff;
    --body: #b0b4ba;
    --muted: #b0b4ba;
    --hairline: rgba(255,255,255,.10);
    --hairline-strong: rgba(255,255,255,.16);
    --primary: #ffffff;
    --primary-active: #f0f0f3;
    --on-primary: #171717;
    --shadow-card: 0 4px 12px rgba(0,0,0,.4);
  }

  * { box-sizing: border-box; margin: 0; font-family: inherit; }

  /* Flat, separated by a hairline rather than a shadow. */
  .card {
    background: var(--canvas);
    border: 1px solid var(--hairline-strong);
    border-radius: 12px;
    padding: 24px;
    max-width: 400px;
    transition: box-shadow var(--ease) 200ms;
  }
  .card:hover { box-shadow: var(--shadow-card); }

  .title {
    font-size: 22px; font-weight: 600; line-height: 1.25;
    letter-spacing: -0.5px; color: var(--ink);
  }
  .description {
    margin-top: 8px; font-size: 16px; line-height: 1.5; color: var(--body);
  }

  form { margin-top: 20px; display: flex; flex-direction: column; gap: 16px; }
  .field { display: flex; flex-direction: column; gap: 6px; }
  .label { font-size: 14px; font-weight: 500; color: var(--body); }
  .req { color: var(--muted); }

  input, textarea, select {
    width: 100%; height: 44px; padding: 0 14px;
    font-size: 16px; color: var(--ink);
    background: var(--canvas);
    border: 1px solid var(--hairline-strong);
    border-radius: 8px;
    outline: none;
    transition: border-color 200ms var(--ease);
    -webkit-appearance: none; appearance: none;
  }
  textarea { height: auto; min-height: 96px; padding: 12px 14px; resize: vertical; line-height: 1.5; }
  select {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1.5 6 6.5l5-5' stroke='%2360646c' stroke-width='1.6' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 14px center;
    padding-right: 36px;
  }
  input::placeholder, textarea::placeholder { color: var(--muted); }

  /* A checkbox is not a text box and must not inherit its size. */
  input[type="checkbox"] {
    width: 20px; height: 20px; padding: 0; align-self: flex-start;
    accent-color: var(--primary); -webkit-appearance: auto; appearance: auto;
    border: 0;
  }

  /* A solid two-pixel edge rather than a coloured glow: this system spends no
     colour on chrome. Still unmistakably focused, still accessible. */
  input:focus, textarea:focus, select:focus {
    border: 2px solid var(--ink);
    padding-left: 13px;
  }
  textarea:focus { padding: 11px 13px; }
  .field.invalid input, .field.invalid textarea, .field.invalid select {
    border-color: var(--error-line);
  }

  button {
    margin-top: 4px; height: 40px; width: 100%;
    font-size: 14px; font-weight: 500;
    color: var(--on-primary); background: var(--primary);
    border: 0; border-radius: 8px; cursor: pointer;
    transition: background 200ms var(--ease);
  }
  button:hover:not(:disabled) { background: var(--primary-active); }
  button:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }
  button:disabled { opacity: .5; cursor: default; }

  /* Expo's error token is a light rose. It carries the border, and the message
     itself stays in ink so it clears AA contrast on white. */
  .error {
    font-size: 13px; line-height: 1.4; color: var(--ink);
    border-left: 2px solid var(--error-line); padding-left: 10px;
  }
  .error:empty { display: none; }

  /* Off-screen rather than display:none — some bots skip hidden inputs but
     happily fill a positioned one. Never read aloud. */
  .trap {
    position: absolute; left: -9999px; top: auto;
    width: 1px; height: 1px; overflow: hidden;
  }

  .done { text-align: center; padding: 8px 0 4px; }
  .check {
    width: 44px; height: 44px; margin: 0 auto 16px;
    border-radius: 50%; background: var(--success);
    display: flex; align-items: center; justify-content: center;
    animation: pop 420ms var(--ease) both;
  }
  .done .title { font-size: 18px; letter-spacing: 0; }
  @keyframes pop { from { transform: scale(.7); opacity: 0 } to { transform: scale(1); opacity: 1 } }
  @keyframes rise { from { transform: translateY(10px); opacity: 0 } to { transform: none; opacity: 1 } }

  /* Popover layout: a black pill that opens a panel. */
  .launcher {
    position: fixed; right: 24px; bottom: 24px; z-index: 2147483000;
    height: 40px; width: auto; padding: 0 18px; margin: 0;
    display: inline-flex; align-items: center;
    box-shadow: var(--shadow-card);
  }
  .panel {
    position: fixed; right: 24px; bottom: 76px; z-index: 2147483000;
    width: 360px; max-width: calc(100vw - 48px);
    max-height: calc(100vh - 120px); overflow: auto;
    animation: rise 320ms var(--ease) both;
  }
  .panel .card { position: relative; box-shadow: var(--shadow-card); }
  .close {
    position: absolute; top: 16px; right: 16px;
    height: 28px; width: 28px; margin: 0; padding: 0;
    border-radius: 9999px; background: var(--surface-strong); color: var(--body);
    font-size: 15px; line-height: 1; display: flex; align-items: center; justify-content: center;
  }
  .close:hover:not(:disabled) { background: var(--hairline-strong); }

  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: .01ms !important; transition-duration: .01ms !important; }
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
