(() => {
  "use strict";

  const form = document.getElementById("donationForm");

  if (!form) {
    return;
  }

  const endpoint = String(form.dataset.squareEndpoint || "").replace(/\/$/, "");
  const contactUrl = String(form.dataset.contactUrl || "/contact").trim() || "/contact";
  const submitButton = document.getElementById("donationSubmit");
  const statusElement = document.getElementById("donationStatus");
  const cardLoadingElement = document.getElementById("donationCardLoading");
  const customAmountInput = document.getElementById("customDonationAmount");
  const amountHelp = document.getElementById("donationAmountHelp");
  const firstNameInput = document.getElementById("donorFirstName");
  const lastNameInput = document.getElementById("donorLastName");
  const emailInput = document.getElementById("donorEmail");
  const successElement = document.getElementById("donationSuccess");
  const successMessage = document.getElementById("donationSuccessMessage");
  const receiptLink = document.getElementById("donationReceiptLink");
  const amountRadios = Array.from(form.querySelectorAll('input[name="donationAmount"]'));

  const DEFAULT_MIN_AMOUNT_CENTS = 500;
  const DEFAULT_MAX_AMOUNT_CENTS = 500000;
  const INITIALIZATION_TIMEOUT_MS = 15000;

  let squareCard = null;
  let donationConfig = null;
  let isCardReady = false;
  let donationServiceUnavailable = false;
  let isSubmitting = false;
  let paymentOutcomeUncertain = false;

  function setStatus(message, type = "info", includeContactLink = false) {
    statusElement.replaceChildren(document.createTextNode(message));

    if (includeContactLink) {
      const contactLink = document.createElement("a");
      contactLink.href = contactUrl;
      contactLink.textContent = "Contact the club.";
      statusElement.append(" ", contactLink);
    }

    statusElement.classList.toggle("is-error", type === "error");
    statusElement.classList.toggle("is-success", type === "success");
  }

  async function withTimeout(promise, timeoutMs, message) {
    let timeoutId;
    const timeoutPromise = new Promise((resolve, reject) => {
      timeoutId = window.setTimeout(() => reject(new Error(message)), timeoutMs);
    });

    try {
      return await Promise.race([promise, timeoutPromise]);
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  async function fetchWithTimeout(url, options, timeoutMs = INITIALIZATION_TIMEOUT_MS) {
    const abortController = new AbortController();
    const timeoutId = window.setTimeout(() => abortController.abort(), timeoutMs);

    try {
      return await fetch(url, { ...options, signal: abortController.signal });
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error("The donation service took too long to respond.");
      }

      throw error;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  function formatMoney(amountCents, currencyCode = "USD") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencyCode,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amountCents / 100);
  }

  function parseDollarAmount(value) {
    const normalized = String(value || "").trim();

    if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) {
      return null;
    }

    const [wholeDollars, fractional = ""] = normalized.split(".");
    const amountCents = Number(wholeDollars) * 100 + Number(fractional.padEnd(2, "0"));

    return Number.isSafeInteger(amountCents) ? amountCents : null;
  }

  function getAmountLimits() {
    return {
      minimum: donationConfig?.minAmountCents || DEFAULT_MIN_AMOUNT_CENTS,
      maximum: donationConfig?.maxAmountCents || DEFAULT_MAX_AMOUNT_CENTS
    };
  }

  function getSelectedAmountCents() {
    const customAmount = customAmountInput.value.trim();

    if (customAmount) {
      return parseDollarAmount(customAmount);
    }

    const selectedAmount = amountRadios.find((radio) => radio.checked);
    const amountCents = Number(selectedAmount?.value);

    return Number.isSafeInteger(amountCents) ? amountCents : null;
  }

  function validateAmount() {
    const amountCents = getSelectedAmountCents();
    const { minimum, maximum } = getAmountLimits();
    let errorMessage = "";

    if (!amountCents) {
      errorMessage = "Choose a donation amount or enter a custom amount using no more than two decimal places.";
    } else if (amountCents < minimum || amountCents > maximum) {
      errorMessage = `Enter an amount between ${formatMoney(minimum)} and ${formatMoney(maximum)}.`;
    }

    customAmountInput.setCustomValidity(errorMessage);
    return errorMessage ? null : amountCents;
  }

  function validateTrimmedName(input, label) {
    const value = input.value.trim();
    input.setCustomValidity(value ? "" : `Enter your ${label}.`);
    return value;
  }

  function updateSubmitButton() {
    if (donationServiceUnavailable) {
      submitButton.disabled = true;
      submitButton.textContent = "Donations Temporarily Unavailable";
      return;
    }

    if (paymentOutcomeUncertain) {
      submitButton.disabled = true;
      submitButton.textContent = "Payment Status Unconfirmed";
      return;
    }

    if (isSubmitting) {
      submitButton.disabled = true;
      submitButton.textContent = "Processing Donation\u2026";
      return;
    }

    const amountCents = validateAmount();
    const checkoutIsReady = Boolean(isCardReady && squareCard && donationConfig);
    submitButton.disabled = !checkoutIsReady;
    submitButton.textContent = checkoutIsReady && amountCents
      ? `Donate ${formatMoney(amountCents, donationConfig.currencyCode)}`
      : checkoutIsReady
        ? "Review Donation Amount"
        : "Preparing Secure Form\u2026";
  }

  function validateConfig(config) {
    const environmentIsValid = config?.environment === "sandbox" || config?.environment === "production";
    const currencyIsValid = typeof config?.currencyCode === "string" && /^[A-Z]{3}$/.test(config.currencyCode);
    const minimumIsValid = Number.isSafeInteger(config?.minAmountCents) && config.minAmountCents > 0;
    const maximumIsValid = Number.isSafeInteger(config?.maxAmountCents)
      && config.maxAmountCents >= config.minAmountCents;

    if (
      !environmentIsValid
      || !config.applicationId
      || !config.locationId
      || !currencyIsValid
      || !minimumIsValid
      || !maximumIsValid
    ) {
      throw new Error("The donation service returned an invalid configuration.");
    }

    return config;
  }

  async function loadSquareSdk(environment) {
    if (window.Square) {
      return;
    }

    const sdkUrl = environment === "production"
      ? "https://web.squarecdn.com/v1/square.js"
      : "https://sandbox.web.squarecdn.com/v1/square.js";

    let script;

    try {
      await withTimeout(new Promise((resolve, reject) => {
        script = document.createElement("script");
        script.src = sdkUrl;
        script.async = true;
        script.dataset.squareSdk = environment;
        script.addEventListener("load", resolve, { once: true });
        script.addEventListener("error", () => reject(new Error("Square.js failed to load.")), { once: true });
        document.head.appendChild(script);
      }), INITIALIZATION_TIMEOUT_MS, "Square.js took too long to load.");
    } catch (error) {
      script?.remove();
      throw error;
    }

    if (!window.Square) {
      throw new Error("Square.js did not initialize.");
    }
  }

  async function initializeDonationForm() {
    if (!endpoint) {
      throw new Error("The donation endpoint is not configured.");
    }

    const configResponse = await fetchWithTimeout(`${endpoint}/config`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      credentials: "omit"
    });
    const configData = await configResponse.json().catch(() => null);

    if (!configResponse.ok) {
      throw new Error(configData?.message || "The donation service is unavailable.");
    }

    donationConfig = validateConfig(configData);
    amountHelp.textContent = `Minimum ${formatMoney(donationConfig.minAmountCents)}; maximum ${formatMoney(donationConfig.maxAmountCents)}.`;

    await loadSquareSdk(donationConfig.environment);

    const payments = window.Square.payments(donationConfig.applicationId, donationConfig.locationId);
    const card = await withTimeout(
      payments.card(),
      INITIALIZATION_TIMEOUT_MS,
      "The secure card form took too long to initialize."
    );
    await withTimeout(
      card.attach("#squareCardContainer"),
      INITIALIZATION_TIMEOUT_MS,
      "The secure card form took too long to open."
    );
    squareCard = card;
    isCardReady = true;

    cardLoadingElement.hidden = true;
    setStatus("Secure card form ready.", "success");
    updateSubmitButton();
  }

  function createIdempotencyKey() {
    if (!window.crypto || typeof window.crypto.randomUUID !== "function") {
      throw new Error("This browser cannot securely start a payment. Please update your browser and try again.");
    }

    return window.crypto.randomUUID();
  }

  function createRequestOptions(payload, signal) {
    return {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload),
      credentials: "omit",
      signal
    };
  }

  async function sendPaymentRequest(payload) {
    let lastError = null;
    let outcomeMayBeUncertain = false;

    for (let attempt = 0; attempt < 2; attempt += 1) {
      const abortController = new AbortController();
      const timeoutId = window.setTimeout(() => abortController.abort(), 20000);

      try {
        const response = await fetch(
          `${endpoint}/payments`,
          createRequestOptions(payload, abortController.signal)
        );
        const data = await response.json().catch(() => null);

        if (response.ok) {
          if (!data || data.status !== "COMPLETED") {
            const confirmationError = new Error("Square did not return a completed payment confirmation.");
            confirmationError.outcomeUncertain = true;
            throw confirmationError;
          }

          return data;
        }

        const paymentError = new Error(data?.message || "Square could not complete the donation.");
        const responseMayBeUncertain = data?.outcome === "unknown"
          || (response.status >= 500 && data?.outcome !== "not_charged");
        outcomeMayBeUncertain = outcomeMayBeUncertain || responseMayBeUncertain;
        paymentError.outcomeUncertain = outcomeMayBeUncertain;
        paymentError.serviceUnavailable = response.status === 503 && !outcomeMayBeUncertain;

        if (responseMayBeUncertain && attempt === 0) {
          lastError = paymentError;
          continue;
        }

        throw paymentError;
      } catch (error) {
        const isNetworkError = error.name === "AbortError" || error instanceof TypeError;

        if (isNetworkError) {
          outcomeMayBeUncertain = true;
          error.outcomeUncertain = true;

          if (attempt === 0) {
            lastError = error;
            continue;
          }
        }

        throw error;
      } finally {
        window.clearTimeout(timeoutId);
      }
    }

    const retryError = lastError || new Error("The donation could not be confirmed.");
    retryError.outcomeUncertain = true;
    throw retryError;
  }

  function getSafeReceiptUrl(value) {
    try {
      const receiptUrl = new URL(value);
      const isSquareHost = receiptUrl.hostname === "squareup.com"
        || receiptUrl.hostname.endsWith(".squareup.com");

      return receiptUrl.protocol === "https:" && isSquareHost ? receiptUrl.href : "";
    } catch (error) {
      return "";
    }
  }

  async function showSuccess(payment) {
    const amountCents = Number.isSafeInteger(payment.amountCents)
      ? payment.amountCents
      : getSelectedAmountCents();
    const receiptUrl = getSafeReceiptUrl(payment.receiptUrl);

    form.hidden = true;
    successMessage.textContent = `Your ${formatMoney(amountCents, donationConfig.currencyCode)} donation was completed. Your support helps Charlotte Polo Club build what comes next.`;

    if (receiptUrl) {
      receiptLink.href = receiptUrl;
      receiptLink.hidden = false;
    }

    successElement.hidden = false;
    successElement.focus();

    if (squareCard && typeof squareCard.destroy === "function") {
      try {
        await squareCard.destroy();
      } catch (error) {
        // The donation is already confirmed; cleanup failure must not replace success.
      }
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (isSubmitting || paymentOutcomeUncertain || !isCardReady || !squareCard || !donationConfig) {
      return;
    }

    const amountCents = validateAmount();
    const firstName = validateTrimmedName(firstNameInput, "first name");
    const lastName = validateTrimmedName(lastNameInput, "last name");

    if (!amountCents || !firstName || !lastName || !form.checkValidity()) {
      form.reportValidity();
      setStatus("Review the highlighted fields before continuing.", "error");
      return;
    }

    isSubmitting = true;
    updateSubmitButton();
    setStatus("Encrypting your card details with Square\u2026");

    try {
      const verificationDetails = {
        amount: (amountCents / 100).toFixed(2),
        currencyCode: donationConfig.currencyCode,
        intent: "CHARGE",
        customerInitiated: true,
        sellerKeyedIn: false,
        billingContact: {
          givenName: firstName,
          familyName: lastName,
          email: emailInput.value.trim()
        }
      };
      const tokenResult = await squareCard.tokenize(verificationDetails);

      if (tokenResult.status !== "OK" || !tokenResult.token) {
        throw new Error("Square could not verify the card details. Check them and try again.");
      }

      setStatus("Processing your donation securely\u2026");

      const payment = await sendPaymentRequest({
        sourceId: tokenResult.token,
        idempotencyKey: createIdempotencyKey(),
        amountCents,
        email: emailInput.value.trim()
      });

      await showSuccess(payment);
    } catch (error) {
      if (error.outcomeUncertain) {
        paymentOutcomeUncertain = true;
        setStatus(
          "We could not confirm the payment result. Please do not submit again yet.",
          "error",
          true
        );
      } else if (error.serviceUnavailable) {
        donationServiceUnavailable = true;
        setStatus("Online donations are temporarily unavailable. Please try again later.", "error", true);
      } else {
        setStatus(error.message || "The donation could not be completed. Please try again.", "error");
      }
    } finally {
      isSubmitting = false;
      updateSubmitButton();
    }
  }

  amountRadios.forEach((radio) => {
    radio.addEventListener("change", () => {
      if (radio.checked) {
        customAmountInput.value = "";
        customAmountInput.setCustomValidity("");
      }

      updateSubmitButton();
    });
  });

  customAmountInput.addEventListener("input", () => {
    if (customAmountInput.value) {
      amountRadios.forEach((radio) => {
        radio.checked = false;
      });
    } else if (!amountRadios.some((radio) => radio.checked) && amountRadios[1]) {
      amountRadios[1].checked = true;
    }

    updateSubmitButton();
  });

  [firstNameInput, lastNameInput].forEach((input) => {
    input.addEventListener("input", () => input.setCustomValidity(""));
  });

  form.addEventListener("submit", handleSubmit);

  initializeDonationForm().catch(() => {
    isCardReady = false;
    donationServiceUnavailable = true;
    squareCard = null;
    cardLoadingElement.textContent = "The secure card form is unavailable.";
    setStatus(
      "Online donations are temporarily unavailable. Please try again later.",
      "error",
      true
    );
    submitButton.disabled = true;
    submitButton.textContent = "Donations Temporarily Unavailable";
  });
})();
