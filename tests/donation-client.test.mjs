import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const DONATION_SOURCE = readFileSync(
  new URL("../donation.js", import.meta.url),
  "utf8"
);
const IDEMPOTENCY_KEY = "47f1f4a6-4817-4f99-9238-c65055455d2d";

function createElement(overrides = {}) {
  const listeners = new Map();
  const classes = new Set();

  return {
    value: "",
    hidden: false,
    disabled: false,
    textContent: "",
    dataset: {},
    classList: {
      toggle(name, enabled) {
        if (enabled) {
          classes.add(name);
        } else {
          classes.delete(name);
        }
      }
    },
    addEventListener(type, callback) {
      listeners.set(type, callback);
    },
    setCustomValidity(message) {
      this.validationMessage = message;
    },
    replaceChildren(...children) {
      this.children = children;
    },
    append(...children) {
      this.children = [...(this.children || []), ...children];
    },
    focus() {},
    remove() {},
    listeners,
    classes,
    ...overrides
  };
}

async function createDonationHarness(paymentResponder, formDataset = {}) {
  const presetAmount = createElement({ checked: true, value: "5000" });
  const customAmount = createElement();
  const submitButton = createElement({ disabled: true });
  const status = createElement();
  const form = createElement({
    dataset: {
      squareEndpoint: "https://donations.example",
      ...formDataset
    },
    querySelectorAll: () => [presetAmount],
    checkValidity: () => true,
    reportValidity() {}
  });
  const elements = {
    donationForm: form,
    donationSubmit: submitButton,
    donationStatus: status,
    donationCardLoading: createElement(),
    customDonationAmount: customAmount,
    donationAmountHelp: createElement(),
    donorFirstName: createElement({ value: "Ada" }),
    donorLastName: createElement({ value: "Lovelace" }),
    donorEmail: createElement({ value: "ada@example.com" }),
    donationSuccess: createElement({ hidden: true }),
    donationSuccessMessage: createElement(),
    donationReceiptLink: createElement({ hidden: true })
  };
  const paymentCalls = [];
  const card = {
    async attach() {},
    async tokenize() {
      return { status: "OK", token: "cnon:card-nonce-ok" };
    },
    async destroy() {}
  };
  const document = {
    getElementById(id) {
      return elements[id] || null;
    },
    createTextNode(text) {
      return { textContent: text };
    },
    createElement() {
      return createElement();
    },
    head: {
      appendChild() {}
    }
  };
  const windowObject = {
    Square: {
      payments() {
        return { card: async () => card };
      }
    },
    crypto: {
      randomUUID: () => IDEMPOTENCY_KEY
    },
    setTimeout,
    clearTimeout
  };

  async function fetchMock(url, options = {}) {
    if (String(url).endsWith("/config")) {
      return new Response(JSON.stringify({
        environment: "sandbox",
        applicationId: "sandbox-sq0idb-test-app",
        locationId: "TEST_LOCATION",
        currencyCode: "USD",
        minAmountCents: 500,
        maxAmountCents: 500000
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }

    paymentCalls.push({ url: String(url), options });
    return paymentResponder(paymentCalls.length);
  }

  vm.runInNewContext(DONATION_SOURCE, {
    AbortController,
    console,
    document,
    fetch: fetchMock,
    Headers,
    Intl,
    Request,
    Response,
    setTimeout,
    clearTimeout,
    TypeError,
    URL,
    window: windowObject
  });

  for (let attempt = 0; attempt < 20 && submitButton.disabled; attempt += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }

  assert.equal(submitButton.disabled, false, "checkout should finish initializing");

  return {
    elements,
    form,
    paymentCalls,
    status,
    submitButton,
    async submit() {
      const submitHandler = form.listeners.get("submit");
      assert.equal(typeof submitHandler, "function");
      await submitHandler({ preventDefault() {} });
    }
  };
}

test("an uncertain payment is retried once with the same idempotency key", async () => {
  const harness = await createDonationHarness((attempt) => {
    if (attempt === 1) {
      return new Response(JSON.stringify({
        message: "Square is temporarily unavailable.",
        outcome: "unknown"
      }), {
        status: 502,
        headers: { "Content-Type": "application/json" }
      });
    }

    return new Response(JSON.stringify({
      paymentId: "square-payment-id",
      status: "COMPLETED",
      receiptUrl: "https://squareup.com/receipt/preview/test-receipt",
      amountCents: 5000,
      currencyCode: "USD"
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  });

  await harness.submit();

  assert.equal(harness.paymentCalls.length, 2);
  const firstPayload = JSON.parse(harness.paymentCalls[0].options.body);
  const secondPayload = JSON.parse(harness.paymentCalls[1].options.body);
  assert.deepEqual(secondPayload, firstPayload);
  assert.equal(firstPayload.idempotencyKey, IDEMPOTENCY_KEY);
  assert.equal(harness.form.hidden, true);
  assert.equal(harness.elements.donationSuccess.hidden, false);
});

test("a definite service failure is not retried and links to contact", async () => {
  const harness = await createDonationHarness(() => new Response(JSON.stringify({
    message: "Online donations are temporarily unavailable. Please try again later.",
    outcome: "not_charged"
  }), {
    status: 503,
    headers: { "Content-Type": "application/json" }
  }));

  await harness.submit();

  assert.equal(harness.paymentCalls.length, 1);
  assert.equal(harness.submitButton.disabled, true);
  assert.equal(harness.submitButton.textContent, "Donations Temporarily Unavailable");
  const contactLink = harness.status.children.find((child) => child?.href === "/contact");
  assert.ok(contactLink, "service failure should provide a contact link");
});

test("a hosted checkout can link failures back to the main contact page", async () => {
  const contactUrl = "https://charlottepolo.com/contact";
  const harness = await createDonationHarness(() => new Response(JSON.stringify({
    message: "Online donations are temporarily unavailable. Please try again later.",
    outcome: "not_charged"
  }), {
    status: 503,
    headers: { "Content-Type": "application/json" }
  }), { contactUrl });

  await harness.submit();

  const contactLink = harness.status.children.find((child) => child?.href === contactUrl);
  assert.ok(contactLink, "hosted checkout failures should return donors to the main contact page");
});
