import assert from "node:assert/strict";
import test from "node:test";

import donationWorker from "../workers/donations.js";

const ALLOWED_ORIGIN = "https://charlottepolo.com";
const TEST_ACCESS_TOKEN = "square-test-access-token-never-return-this";
const TEST_ENV = {
  ALLOWED_ORIGINS: `${ALLOWED_ORIGIN},https://www.charlottepolo.com`,
  SQUARE_ENVIRONMENT: "sandbox",
  SQUARE_APPLICATION_ID: "sandbox-sq0idb-test-app",
  SQUARE_LOCATION_ID: "TEST_LOCATION",
  SQUARE_ACCESS_TOKEN: TEST_ACCESS_TOKEN,
  MIN_DONATION_CENTS: "500",
  MAX_DONATION_CENTS: "500000",
  DONATION_CLIENT_RATE_LIMITER: {
    limit: async () => ({ success: true })
  },
  DONATION_ROUTE_RATE_LIMITER: {
    limit: async () => ({ success: true })
  }
};

function createRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});

  if (options.includeOrigin !== false) {
    headers.set("Origin", options.origin || ALLOWED_ORIGIN);
  }

  return new Request(`https://donations.example${path}`, {
    method: options.method || "GET",
    headers,
    body: options.body,
    ...(options.duplex ? { duplex: options.duplex } : {})
  });
}

function createPaymentRequest(overrides = {}) {
  return createRequest("/payments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sourceId: "cnon:card-nonce-ok",
      idempotencyKey: "47f1f4a6-4817-4f99-9238-c65055455d2d",
      amountCents: 5000,
      email: "donor@example.com",
      ...overrides
    })
  });
}

async function readJson(response) {
  return JSON.parse(await response.text());
}

test("preflight allows only configured site origins", async () => {
  const allowedResponse = await donationWorker.fetch(
    createRequest("/payments", { method: "OPTIONS" }),
    TEST_ENV
  );

  assert.equal(allowedResponse.status, 204);
  assert.equal(allowedResponse.headers.get("Access-Control-Allow-Origin"), ALLOWED_ORIGIN);

  const blockedResponse = await donationWorker.fetch(
    createRequest("/payments", { method: "OPTIONS", origin: "https://example.net" }),
    TEST_ENV
  );

  assert.equal(blockedResponse.status, 403);
  assert.equal(blockedResponse.headers.get("Access-Control-Allow-Origin"), null);
});

test("requests without an allowed Origin are rejected", async () => {
  const response = await donationWorker.fetch(
    createRequest("/config", { includeOrigin: false }),
    TEST_ENV
  );

  assert.equal(response.status, 403);
  assert.deepEqual(await readJson(response), { message: "This origin is not allowed." });
});

test("public configuration never exposes the Square access token", async () => {
  const response = await donationWorker.fetch(createRequest("/config"), TEST_ENV);
  const responseText = await response.text();
  const config = JSON.parse(responseText);

  assert.equal(response.status, 200);
  assert.equal(config.environment, "sandbox");
  assert.equal(config.applicationId, TEST_ENV.SQUARE_APPLICATION_ID);
  assert.equal(config.locationId, TEST_ENV.SQUARE_LOCATION_ID);
  assert.equal(config.currencyCode, "USD");
  assert.equal(config.minAmountCents, 500);
  assert.equal(config.maxAmountCents, 500000);
  assert.equal(config.accessToken, undefined);
  assert.equal(responseText.includes(TEST_ACCESS_TOKEN), false);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
});

test("missing Square credentials fail closed", async () => {
  const response = await donationWorker.fetch(createRequest("/config"), {
    ...TEST_ENV,
    SQUARE_ACCESS_TOKEN: ""
  });

  assert.equal(response.status, 503);
  assert.deepEqual(await readJson(response), {
    message: "Online donations are temporarily unavailable."
  });
});

test("unexpected failures are logged without exception messages or secrets", async (t) => {
  const secretMarker = "never-log-this-sensitive-value";
  const loggedValues = [];
  const consoleError = t.mock.method(console, "error", (...values) => {
    loggedValues.push(values);
  });
  const failingEnv = { ...TEST_ENV };

  Object.defineProperty(failingEnv, "SQUARE_ENVIRONMENT", {
    get() {
      throw new TypeError(`configuration failed: ${secretMarker}`);
    }
  });

  const response = await donationWorker.fetch(createRequest("/config"), failingEnv);
  const body = await readJson(response);

  assert.equal(response.status, 500);
  assert.deepEqual(body, {
    message: "The donation service encountered an unexpected error."
  });
  assert.equal(consoleError.mock.callCount(), 1);
  assert.equal(loggedValues.length, 1);

  const logEntry = JSON.parse(String(loggedValues[0][0]));

  assert.deepEqual(logEntry, {
    event: "donation_worker_unhandled_error",
    method: "GET",
    path: "/config",
    errorType: "TypeError"
  });
  assert.equal(JSON.stringify(loggedValues).includes(secretMarker), false);
});

test("invalid or out-of-range amounts never reach Square", async (t) => {
  const squareFetch = t.mock.method(globalThis, "fetch", async () => {
    throw new Error("Square should not be called");
  });
  const response = await donationWorker.fetch(
    createPaymentRequest({ amountCents: 499 }),
    TEST_ENV
  );
  const body = await readJson(response);

  assert.equal(response.status, 400);
  assert.match(body.message, /between \$5\.00 and \$5000\.00/);
  assert.equal(squareFetch.mock.callCount(), 0);
});

test("streamed bodies over 10KB without Content-Length are rejected before Square", async (t) => {
  const squareFetch = t.mock.method(globalThis, "fetch", async () => {
    throw new Error("Square should not be called");
  });
  let streamCancelled = false;

  const request = createRequest("/payments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array(6000));
        controller.enqueue(new Uint8Array(4001));
      },
      cancel() {
        streamCancelled = true;
      }
    }),
    duplex: "half"
  });

  assert.equal(request.headers.get("Content-Length"), null);

  const response = await donationWorker.fetch(request, TEST_ENV);

  assert.equal(response.status, 413);
  assert.deepEqual(await readJson(response), {
    message: "The payment request is too large."
  });
  assert.equal(streamCancelled, true);
  assert.equal(squareFetch.mock.callCount(), 0);
});

test("a spoofed short Content-Length cannot bypass the streamed body cap", async (t) => {
  const squareFetch = t.mock.method(globalThis, "fetch", async () => {
    throw new Error("Square should not be called");
  });

  const request = createRequest("/payments", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Content-Length": "1"
    },
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array(10001));
      }
    }),
    duplex: "half"
  });

  const response = await donationWorker.fetch(request, TEST_ENV);

  assert.equal(response.status, 413);
  assert.equal(squareFetch.mock.callCount(), 0);
});

test("rate-limited requests fail before reaching Square", async (t) => {
  const squareFetch = t.mock.method(globalThis, "fetch", async () => {
    throw new Error("Square should not be called");
  });
  const response = await donationWorker.fetch(createPaymentRequest(), {
    ...TEST_ENV,
    DONATION_CLIENT_RATE_LIMITER: {
      limit: async () => ({ success: false })
    }
  });

  assert.equal(response.status, 429);
  assert.equal(response.headers.get("Retry-After"), "60");
  assert.deepEqual(await readJson(response), {
    message: "Too many payment attempts. Please wait a minute and try again.",
    outcome: "not_charged"
  });
  assert.equal(squareFetch.mock.callCount(), 0);
});

test("missing rate-limit bindings fail closed before reaching Square", async (t) => {
  const squareFetch = t.mock.method(globalThis, "fetch", async () => {
    throw new Error("Square should not be called");
  });
  const { DONATION_CLIENT_RATE_LIMITER, ...envWithoutClientLimiter } = TEST_ENV;
  const response = await donationWorker.fetch(createPaymentRequest(), envWithoutClientLimiter);

  assert.equal(response.status, 503);
  assert.deepEqual(await readJson(response), {
    message: "Online donations are temporarily unavailable. Please try again later.",
    outcome: "not_charged"
  });
  assert.equal(squareFetch.mock.callCount(), 0);
});

test("a valid sandbox donation is sent to Square and returns a minimal receipt", async (t) => {
  let outgoingUrl = "";
  let outgoingOptions = null;

  t.mock.method(globalThis, "fetch", async (url, options) => {
    outgoingUrl = String(url);
    outgoingOptions = options;

    return new Response(JSON.stringify({
      payment: {
        id: "square-payment-id",
        status: "COMPLETED",
        location_id: TEST_ENV.SQUARE_LOCATION_ID,
        amount_money: {
          amount: 5000,
          currency: "USD"
        },
        receipt_url: "https://squareup.com/receipt/preview/test-receipt"
      }
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  });

  const response = await donationWorker.fetch(createPaymentRequest(), TEST_ENV);
  const responseText = await response.text();
  const body = JSON.parse(responseText);
  const squareBody = JSON.parse(outgoingOptions.body);

  assert.equal(response.status, 200);
  assert.equal(outgoingUrl, "https://connect.squareupsandbox.com/v2/payments");
  assert.equal(outgoingOptions.headers.Authorization, `Bearer ${TEST_ACCESS_TOKEN}`);
  assert.equal(outgoingOptions.headers["Square-Version"], "2026-07-15");
  assert.equal(squareBody.source_id, "cnon:card-nonce-ok");
  assert.equal(squareBody.idempotency_key, "47f1f4a6-4817-4f99-9238-c65055455d2d");
  assert.deepEqual(squareBody.amount_money, { amount: 5000, currency: "USD" });
  assert.equal(squareBody.location_id, TEST_ENV.SQUARE_LOCATION_ID);
  assert.equal(squareBody.buyer_email_address, "donor@example.com");
  assert.deepEqual(body, {
    paymentId: "square-payment-id",
    status: "COMPLETED",
    receiptUrl: "https://squareup.com/receipt/preview/test-receipt",
    amountCents: 5000,
    currencyCode: "USD"
  });
  assert.equal(responseText.includes(TEST_ACCESS_TOKEN), false);
  assert.equal(responseText.includes("cnon:card-nonce-ok"), false);
});

test("Square decline details are replaced with a safe customer message", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({
    errors: [{
      code: "CARD_DECLINED",
      detail: `Sensitive upstream detail: ${TEST_ACCESS_TOKEN}`
    }]
  }), {
    status: 400,
    headers: { "Content-Type": "application/json" }
  }));

  const response = await donationWorker.fetch(createPaymentRequest(), TEST_ENV);
  const responseText = await response.text();
  const body = JSON.parse(responseText);

  assert.equal(response.status, 402);
  assert.equal(body.message, "The card was declined. Check the details or try another card.");
  assert.equal(responseText.includes(TEST_ACCESS_TOKEN), false);
  assert.equal(responseText.includes("Sensitive upstream detail"), false);
});

test("Square authentication failures are definite service errors", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({
    errors: [{ code: "UNAUTHORIZED", detail: TEST_ACCESS_TOKEN }]
  }), {
    status: 401,
    headers: { "Content-Type": "application/json" }
  }));

  const response = await donationWorker.fetch(createPaymentRequest(), TEST_ENV);

  assert.equal(response.status, 503);
  assert.deepEqual(await readJson(response), {
    message: "Online donations are temporarily unavailable. Please try again later.",
    outcome: "not_charged"
  });
});

test("Square rate limits preserve retry timing without implying a charge", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({
    errors: [{ code: "RATE_LIMITED" }]
  }), {
    status: 429,
    headers: {
      "Content-Type": "application/json",
      "Retry-After": "17"
    }
  }));

  const response = await donationWorker.fetch(createPaymentRequest(), TEST_ENV);

  assert.equal(response.status, 429);
  assert.equal(response.headers.get("Retry-After"), "17");
  assert.deepEqual(await readJson(response), {
    message: "The payment service is busy. Please wait a moment and try again.",
    outcome: "not_charged"
  });
});

test("Square server failures are marked as an uncertain outcome", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({
    errors: [{ code: "INTERNAL_SERVER_ERROR" }]
  }), {
    status: 500,
    headers: { "Content-Type": "application/json" }
  }));

  const response = await donationWorker.fetch(createPaymentRequest(), TEST_ENV);

  assert.equal(response.status, 502);
  assert.deepEqual(await readJson(response), {
    message: "Online donations are temporarily unavailable. Please try again later.",
    outcome: "unknown"
  });
});

test("a mismatched Square completion is not reported as successful", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({
    payment: {
      id: "square-payment-id",
      status: "COMPLETED",
      location_id: TEST_ENV.SQUARE_LOCATION_ID,
      amount_money: {
        amount: 2500,
        currency: "USD"
      }
    }
  }), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  }));

  const response = await donationWorker.fetch(createPaymentRequest(), TEST_ENV);

  assert.equal(response.status, 502);
  assert.match((await readJson(response)).message, /did not return a completed payment confirmation/);
});
