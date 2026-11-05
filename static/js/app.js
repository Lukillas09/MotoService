if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {});
  });
}

const loadingBar = document.querySelector("#global-loading");

// El HTML trae "Ctrl K"; en Mac/iOS el atajo real es ⌘K.
const platform = navigator.userAgentData?.platform || navigator.platform || "";
if (/mac|iphone|ipad|ipod/i.test(platform)) {
  document.querySelectorAll(".search-hint").forEach((hint) => {
    hint.textContent = "⌘K";
  });
}

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    const search = document.querySelector("#global-search");
    if (search) {
      event.preventDefault();
      search.focus();
    }
  }
});

// Confirmación de acciones: modal propio para forms con data-confirm-message.
const confirmModal = document.querySelector("#confirm-modal");
const CONFIRM_TONES = {
  danger: "btn-confirm-danger",
  warning: "btn-confirm-warning",
  primary: "btn-primary",
};
let pendingConfirmation = null;

const resubmitConfirmed = (form, submitter) => {
  // La segunda vuelta no vuelve a pedir confirmación y conserva el botón
  // usado (nombre y valor), así HTMX y el estado is-submitting funcionan igual.
  form.dataset.confirmed = "true";
  if (typeof form.requestSubmit === "function") {
    form.requestSubmit(submitter?.form === form ? submitter : undefined);
    return;
  }
  if (submitter?.name) {
    const hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = submitter.name;
    hidden.value = submitter.value;
    form.append(hidden);
  }
  form.submit();
};

const openConfirmation = (form, submitter) => {
  const tone = CONFIRM_TONES[form.dataset.confirmTone] ? form.dataset.confirmTone : "danger";
  const accept = confirmModal.querySelector("[data-confirm-accept]");
  confirmModal.querySelector("#confirm-modal-title").textContent =
    form.dataset.confirmTitle || "¿Confirmás esta acción?";
  confirmModal.querySelector("#confirm-modal-message").textContent = form.dataset.confirmMessage;
  accept.textContent = form.dataset.confirmButton || "Confirmar";
  accept.className = `btn ${CONFIRM_TONES[tone]}`;
  pendingConfirmation = {
    form,
    submitter,
    tone,
    confirmed: false,
    returnFocus: submitter || document.activeElement,
  };
  window.bootstrap.Modal.getOrCreateInstance(confirmModal).show();
};

if (confirmModal) {
  confirmModal.addEventListener("shown.bs.modal", () => {
    // En acciones destructivas el foco arranca en "Cancelar".
    const selector = pendingConfirmation?.tone === "primary" ? "[data-confirm-accept]" : "[data-confirm-cancel]";
    confirmModal.querySelector(selector)?.focus();
  });
  confirmModal.querySelector("[data-confirm-accept]").addEventListener("click", () => {
    if (!pendingConfirmation) return;
    pendingConfirmation.confirmed = true;
    window.bootstrap.Modal.getOrCreateInstance(confirmModal).hide();
  });
  confirmModal.addEventListener("hidden.bs.modal", () => {
    // Cancelar, Escape o clic afuera llegan acá sin confirmar.
    const pending = pendingConfirmation;
    pendingConfirmation = null;
    if (!pending) return;
    if (pending.returnFocus?.isConnected) pending.returnFocus.focus();
    if (pending.confirmed) resubmitConfirmed(pending.form, pending.submitter);
  });
}

// Fase de captura: corre antes que HTMX y que el estado is-submitting.
document.addEventListener(
  "submit",
  (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.matches("[data-confirm-message]")) return;
    if (form.dataset.confirmed === "true") {
      delete form.dataset.confirmed;
      return;
    }
    if (!confirmModal || !window.bootstrap?.Modal) {
      if (!window.confirm(form.dataset.confirmMessage)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!pendingConfirmation) openConfirmation(form, event.submitter || null);
  },
  true
);

document.addEventListener("submit", (event) => {
  const form = event.target.closest("form");
  if (!form) return;

  if ((form.method || "get").toLowerCase() !== "post") return;

  const button = event.submitter || form.querySelector("button[type='submit']");
  if (!button || button.disabled) return;

  button.dataset.originalText = button.innerHTML;
  button.setAttribute("aria-busy", "true");
  button.classList.add("is-submitting");
  window.setTimeout(() => {
    button.disabled = true;
  }, 0);
});

document.body.addEventListener("htmx:beforeRequest", () => {
  loadingBar?.classList.add("is-visible");
});

const finishHtmxRequest = (event) => {
  loadingBar?.classList.remove("is-visible");
  const form = event.detail?.elt?.closest?.("form");
  const button = form?.querySelector("button.is-submitting");
  if (button) {
    button.disabled = false;
    button.removeAttribute("aria-busy");
    button.classList.remove("is-submitting");
    if (button.dataset.originalText) button.innerHTML = button.dataset.originalText;
  }
};

document.body.addEventListener("htmx:afterRequest", finishHtmxRequest);
document.body.addEventListener("htmx:responseError", finishHtmxRequest);

window.addEventListener("load", () => {
  document.querySelectorAll(".app-toast").forEach((toast) => {
    const tags = toast.dataset.messageTags || "";
    if (tags.includes("error")) return;
    window.setTimeout(() => {
      if (window.bootstrap?.Alert) {
        window.bootstrap.Alert.getOrCreateInstance(toast).close();
      }
    }, 6500);
  });
});
