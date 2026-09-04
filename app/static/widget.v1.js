(function () {
  "use strict";

  // Everything lives in a shadow root. The host page's CSS cannot reach in and
  // ours cannot leak out, which is the only way this looks the same on a site
  // we do not control.
  var STYLE = [
    ":host { all: initial; }",
    "* { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }",
    ".card { border: 1px solid rgba(0,0,0,.12); border-radius: 12px; padding: 20px; max-width: 420px; }",
    ".title { font-size: 18px; font-weight: 600; margin: 0 0 4px; }",
    ".description { font-size: 14px; margin: 0 0 16px; opacity: .7; }",
    ".field { display: block; margin-bottom: 12px; }",
    ".label { display: block; font-size: 13px; margin-bottom: 4px; }",
    "input, textarea, select { width: 100%; padding: 8px 10px; font-size: 14px; border: 1px solid rgba(0,0,0,.2); border-radius: 8px; }",
    "textarea { min-height: 88px; resize: vertical; }",
    "button { width: 100%; padding: 10px; font-size: 14px; font-weight: 600; border: 0; border-radius: 8px; background: #0071e3; color: #fff; cursor: pointer; }",
    "button[disabled] { opacity: .6; cursor: default; }",
    ".message { font-size: 13px; margin-top: 12px; }",
    ".message.error { color: #c00; }",
    // The honeypot: off-screen rather than display:none, because some bots skip
    // hidden inputs but not positioned ones. Never announced to screen readers.
    ".trap { position: absolute; left: -9999px; width: 1px; height: 1px; overflow: hidden; }"
  ].join("\n");

  function el(tag, props, children) {
    var node = document.createElement(tag);
    Object.keys(props || {}).forEach(function (key) {
      if (key === "text") node.textContent = props[key];
      else node.setAttribute(key, props[key]);
    });
    (children || []).forEach(function (child) { node.appendChild(child); });
    return node;
  }

  function buildInput(field) {
    var node;
    if (field.type === "textarea") {
      node = el("textarea", {});
    } else if (field.type === "select") {
      node = el("select", {}, [el("option", { value: "", text: "Choose one" })]);
      (field.options || []).forEach(function (option) {
        node.appendChild(el("option", { value: option, text: option }));
      });
    } else {
      var htmlType = field.type === "email" ? "email" : field.type === "number" ? "number" : field.type === "checkbox" ? "checkbox" : "text";
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

  function render(root, config) {
    root.innerHTML = "";
    root.appendChild(el("style", { text: STYLE }));

    var form = el("form", {});
    var card = el("div", { class: "card" }, [
      el("h2", { class: "title", text: config.title }),
      config.description ? el("p", { class: "description", text: config.description }) : el("span", {}),
      form
    ]);

    config.fields.forEach(function (field) {
      var input = buildInput(field);
      form.appendChild(el("label", { class: "field" }, [
        el("span", { class: "label", text: field.label + (field.required ? " *" : "") }),
        input
      ]));
    });

    // The bot bait. A person never sees it, so anything in it is not a person.
    var trap = el("input", { type: "text", tabindex: "-1", autocomplete: "off", "aria-hidden": "true" });
    trap.name = config.honeypot_field;
    form.appendChild(el("div", { class: "trap" }, [trap]));

    var button = el("button", { type: "submit", text: config.button_text });
    var message = el("p", { class: "message" });
    form.appendChild(button);
    form.appendChild(message);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      button.disabled = true;
      message.className = "message";
      message.textContent = "Sending…";

      var body = { widget_id: config.id, data: readValues(form, config) };
      body[config.honeypot_field] = trap.value;

      fetch(config.submit_url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }).then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (payload) {
          return { ok: response.ok, payload: payload };
        });
      }).then(function (result) {
        if (result.ok) {
          card.innerHTML = "";
          card.appendChild(el("h2", { class: "title", text: (config.options && config.options.success_message) || "Thanks." }));
          return;
        }
        button.disabled = false;
        message.className = "message error";
        message.textContent = result.payload.error || "Something went wrong. Try again.";
      }).catch(function () {
        button.disabled = false;
        message.className = "message error";
        message.textContent = "Could not reach the server.";
      });
    });

    root.appendChild(card);
  }

  function mount(request) {
    var root = request.mount.attachShadow ? request.mount.attachShadow({ mode: "open" }) : request.mount;
    fetch(request.base + "/public/widgets/" + encodeURIComponent(request.widgetId) + "/config")
      .then(function (response) {
        if (!response.ok) throw new Error("config " + response.status);
        return response.json();
      })
      .then(function (config) { render(root, config); })
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
