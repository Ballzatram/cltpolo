const SQUARE_API_VERSION = "2026-07-15";
const DEFAULT_ALLOWED_ORIGINS = [
  "https://charlottepolo.com",
  "https://www.charlottepolo.com"
];
const DEFAULT_MIN_DONATION_CENTS = 500;
const DEFAULT_MAX_DONATION_CENTS = 500000;
const CURRENCY_CODE = "USD";
const MAX_REQUEST_BODY_BYTES = 10000;

function jsonResponse(body, status, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "application/json; charset=utf-8",
      "X-Content-Type-Options": "nosniff",
      ...headers
    }
  });
}

function getAllowedOrigins(env) {
  const configuredOrigins = String(env.ALLOWED_ORIGINS || env.ALLOWED_ORIGIN || "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);

  return configuredOrigins.length ? configuredOrigins : DEFAULT_ALLOWED_ORIGINS;
}

function getRequestOrigin(request) {
  return String(request.headers.get("Origin") || "").trim();
}

function isOriginAllowed(request, env) {
  const requestOrigin = getRequestOrigin(request);
  return Boolean(requestOrigin && getAllowedOrigins(env).includes(requestOrigin));
}

function getCorsHeaders(request, env) {
  const requestOrigin = getRequestOrigin(request);
  const headers = {
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin"
  };

  if (requestOrigin && getAllowedOrigins(env).includes(requestOrigin)) {
    headers["Access-Control-Allow-Origin"] = requestOrigin;
  }

  return headers;
}

function parsePositiveInteger(value, fallback) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }

  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

function getSquareConfig(env) {
  const environment = String(env.SQUARE_ENVIRONMENT || "production").trim().toLowerCase();
  const minAmountCents = parsePositiveInteger(
    env.MIN_DONATION_CENTS,
    DEFAULT_MIN_DONATION_CENTS
  );
  const maxAmountCents = parsePositiveInteger(
    env.MAX_DONATION_CENTS,
    DEFAULT_MAX_DONATION_CENTS
  );

  if (
    !["sandbox", "production"].includes(environment)
    || !minAmountCents
    || !maxAmountCents
    || maxAmountCents < minAmountCents
  ) {
    return null;
  }

  const applicationId = String(env.SQUARE_APPLICATION_ID || "").trim();
  const locationId = String(env.SQUARE_LOCATION_ID || "").trim();
  const accessToken = String(env.SQUARE_ACCESS_TOKEN || "").trim();

  if (!applicationId || !locationId || !accessToken) {
    return null;
  }

  return {
    environment,
    applicationId,
    locationId,
    accessToken,
    minAmountCents,
    maxAmountCents,
    currencyCode: CURRENCY_CODE
  };
}

function getPublicConfig(config) {
  return {
    environment: config.environment,
    applicationId: config.applicationId,
    locationId: config.locationId,
    minAmountCents: config.minAmountCents,
    maxAmountCents: config.maxAmountCents,
    currencyCode: config.currencyCode
  };
}

function isValidEmail(value) {
  return value.length <= 255
    && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function validatePaymentPayload(payload, config) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return { error: "Enter valid donation details and try again." };
  }

  const sourceId = typeof payload.sourceId === "string" ? payload.sourceId.trim() : "";
  const idempotencyKey = typeof payload.idempotencyKey === "string"
    ? payload.idempotencyKey.trim()
    : "";
  const amountCents = Number(payload.amountCents);
  const email = typeof payload.email === "string" ? payload.email.trim() : "";

  if (!sourceId || sourceId.length > 500 || /[\u0000-\u001F\u007F]/.test(sourceId)) {
    return { error: "Square could not verify the card details. Please try again." };
  }

  if (!/^[A-Za-z0-9_-]{8,45}$/.test(idempotencyKey)) {
    return { error: "The payment request could not be started. Please try again." };
  }

  if (
    !Number.isSafeInteger(amountCents)
    || amountCents < config.minAmountCents
    || amountCents > config.maxAmountCents
  ) {
    return {
      error: `Donation amounts must be between $${(config.minAmountCents / 100).toFixed(2)} and $${(config.maxAmountCents / 100).toFixed(2)}.`
    };
  }

  if (!isValidEmail(email)) {
    return { error: "Enter a valid email address." };
  }

  return {
    value: {
      sourceId,
      idempotencyKey,
      amountCents,
      email
    }
  };
}

async function readJsonBody(request) {
  const contentLengthHeader = request.headers.get("Content-Length");

  if (contentLengthHeader !== null) {
    if (!/^\d+$/.test(contentLengthHeader)) {
      return { invalid: true };
    }

    if (Number(contentLengthHeader) > MAX_REQUEST_BODY_BYTES) {
      if (request.body) {
        try {
          await request.body.cancel();
        } catch {
          // The request still fails closed if stream cancellation is unavailable.
        }
      }

      return { tooLarge: true };
    }
  }

  if (!request.body) {
    return { invalid: true };
  }

  const reader = request.body.getReader();
  const bodyBytes = new Uint8Array(MAX_REQUEST_BODY_BYTES);
  let bytesRead = 0;

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      if (bytesRead + value.byteLength > MAX_REQUEST_BODY_BYTES) {
        try {
          await reader.cancel();
        } catch {
          // Preserve the 413 response even if stream cancellation fails.
        }

        return { tooLarge: true };
      }

      bodyBytes.set(value, bytesRead);
      bytesRead += value.byteLength;
    }
  } catch {
    return { invalid: true };
  } finally {
    reader.releaseLock();
  }

  try {
    const rawBody = new TextDecoder("utf-8", { fatal: true })
      .decode(bodyBytes.subarray(0, bytesRead));

    return { value: JSON.parse(rawBody) };
  } catch {
    return { invalid: true };
  }
}

function getSquareApiBaseUrl(environment) {
  return environment === "sandbox"
    ? "https://connect.squareupsandbox.com"
    : "https://connect.squareup.com";
}

function getSquareFailureMessage(squareResponse, squareData) {
  const errorCode = String(squareData?.errors?.[0]?.code || "");
  const cardDeclineCodes = new Set([
    "ADDRESS_VERIFICATION_FAILURE",
    "CARD_DECLINED",
    "CVV_FAILURE",
    "EXPIRATION_FAILURE",
    "GENERIC_DECLINE",
    "INSUFFICIENT_FUNDS",
    "INVALID_ACCOUNT",
    "INVALID_CARD",
    "INVALID_CARD_DATA",
    "INVALID_EXPIRATION",
    "INVALID_PIN",
    "TRANSACTION_LIMIT"
  ]);

  if (cardDeclineCodes.has(errorCode)) {
    return "The card was declined. Check the details or try another card.";
  }

  if (squareResponse.status === 429) {
    return "The payment service is busy. Please wait a moment and try again.";
  }

  if ([401, 403, 404].includes(squareResponse.status) || squareResponse.status >= 500) {
    return "Online donations are temporarily unavailable. Please try again later.";
  }

  return "Square could not complete the donation. Please check the card details and try again.";
}

async function handleConfig(config, corsHeaders) {
  return jsonResponse(getPublicConfig(config), 200, corsHeaders);
}

async function checkPaymentRateLimits(request, env) {
  const clientLimiter = env.DONATION_CLIENT_RATE_LIMITER;
  const routeLimiter = env.DONATION_ROUTE_RATE_LIMITER;

  if (
    !clientLimiter
    || typeof clientLimiter.limit !== "function"
    || !routeLimiter
    || typeof routeLimiter.limit !== "function"
  ) {
    return { available: false, allowed: false };
  }

  const clientAddress = String(request.headers.get("CF-Connecting-IP") || "unknown").slice(0, 64);

  try {
    const [clientResult, routeResult] = await Promise.all([
      clientLimiter.limit({ key: `client:${clientAddress}` }),
      routeLimiter.limit({ key: "create-payment" })
    ]);

    return {
      available: true,
      allowed: Boolean(clientResult?.success && routeResult?.success)
    };
  } catch (error) {
    return { available: false, allowed: false };
  }
}

async function handlePayment(request, env, config, corsHeaders) {
  const parsedBody = await readJsonBody(request);

  if (parsedBody.tooLarge) {
    return jsonResponse({ message: "The payment request is too large." }, 413, corsHeaders);
  }

  if (parsedBody.invalid) {
    return jsonResponse({ message: "Enter valid donation details and try again." }, 400, corsHeaders);
  }

  const validation = validatePaymentPayload(parsedBody.value, config);

  if (validation.error) {
    return jsonResponse({ message: validation.error }, 400, corsHeaders);
  }

  const rateLimit = await checkPaymentRateLimits(request, env);

  if (!rateLimit.available) {
    return jsonResponse(
      {
        message: "Online donations are temporarily unavailable. Please try again later.",
        outcome: "not_charged"
      },
      503,
      corsHeaders
    );
  }

  if (!rateLimit.allowed) {
    return jsonResponse(
      {
        message: "Too many payment attempts. Please wait a minute and try again.",
        outcome: "not_charged"
      },
      429,
      { ...corsHeaders, "Retry-After": "60" }
    );
  }

  const paymentRequest = {
    source_id: validation.value.sourceId,
    idempotency_key: validation.value.idempotencyKey,
    amount_money: {
      amount: validation.value.amountCents,
      currency: config.currencyCode
    },
    autocomplete: true,
    location_id: config.locationId,
    buyer_email_address: validation.value.email,
    note: "Charlotte Polo Club website donation"
  };

  let squareResponse;

  try {
    squareResponse = await fetch(`${getSquareApiBaseUrl(config.environment)}/v2/payments`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${config.accessToken}`,
        "Content-Type": "application/json",
        "Square-Version": SQUARE_API_VERSION
      },
      body: JSON.stringify(paymentRequest)
    });
  } catch (error) {
    return jsonResponse(
      {
        message: "The payment service could not be reached. Please contact the club before retrying.",
        outcome: "unknown"
      },
      502,
      corsHeaders
    );
  }

  const squareData = await squareResponse.json().catch(() => null);

  if (!squareResponse.ok) {
    let responseStatus = 402;
    let outcome = "not_charged";
    const responseHeaders = { ...corsHeaders };

    if (squareResponse.status === 429) {
      responseStatus = 429;
      const squareRetryAfter = String(squareResponse.headers.get("Retry-After") || "");
      responseHeaders["Retry-After"] = /^\d{1,5}$/.test(squareRetryAfter)
        ? squareRetryAfter
        : "60";
    } else if ([401, 403, 404].includes(squareResponse.status)) {
      responseStatus = 503;
    } else if (squareResponse.status >= 500) {
      responseStatus = 502;
      outcome = "unknown";
    }

    return jsonResponse(
      { message: getSquareFailureMessage(squareResponse, squareData), outcome },
      responseStatus,
      responseHeaders
    );
  }

  const payment = squareData?.payment;
  const paidAmount = Number(payment?.amount_money?.amount);
  const paidCurrency = String(payment?.amount_money?.currency || "");

  if (
    !payment?.id
    || payment.status !== "COMPLETED"
    || paidAmount !== validation.value.amountCents
    || paidCurrency !== config.currencyCode
    || payment.location_id !== config.locationId
  ) {
    return jsonResponse(
      {
        message: "Square did not return a completed payment confirmation. Please contact the club before retrying.",
        outcome: "unknown"
      },
      502,
      corsHeaders
    );
  }

  return jsonResponse(
    {
      paymentId: payment.id,
      status: "COMPLETED",
      receiptUrl: typeof payment.receipt_url === "string" ? payment.receipt_url : "",
      amountCents: paidAmount,
      currencyCode: paidCurrency
    },
    200,
    corsHeaders
  );
}

async function handleRequest(request, env) {
  const corsHeaders = getCorsHeaders(request, env);

  if (request.method === "OPTIONS") {
    if (!isOriginAllowed(request, env)) {
      return jsonResponse({ message: "This origin is not allowed." }, 403, corsHeaders);
    }

    return new Response(null, {
      status: 204,
      headers: corsHeaders
    });
  }

  if (!isOriginAllowed(request, env)) {
    return jsonResponse({ message: "This origin is not allowed." }, 403, corsHeaders);
  }

  const url = new URL(request.url);

  if (url.pathname === "/config") {
    if (request.method !== "GET") {
      return jsonResponse({ message: "Use GET for donation configuration." }, 405, corsHeaders);
    }
  } else if (url.pathname === "/payments") {
    if (request.method !== "POST") {
      return jsonResponse({ message: "Use POST to create a donation payment." }, 405, corsHeaders);
    }
  } else {
    return jsonResponse({ message: "Not found." }, 404, corsHeaders);
  }

  const config = getSquareConfig(env);

  if (!config) {
    return jsonResponse(
      {
        message: "Online donations are temporarily unavailable.",
        ...(url.pathname === "/payments" ? { outcome: "not_charged" } : {})
      },
      503,
      corsHeaders
    );
  }

  if (url.pathname === "/config") {
    return handleConfig(config, corsHeaders);
  }

  return handlePayment(request, env, config, corsHeaders);
}

export {
  getAllowedOrigins,
  getPublicConfig,
  getSquareConfig,
  handleRequest,
  validatePaymentPayload
};

export default {
  async fetch(request, env) {
    try {
      return await handleRequest(request, env);
    } catch (error) {
      const corsHeaders = getCorsHeaders(request, env);
      const path = new URL(request.url).pathname;
      const isPaymentRequest = path === "/payments";

      console.error(JSON.stringify({
        event: "donation_worker_unhandled_error",
        method: request.method,
        path,
        errorType: error instanceof TypeError
          ? "TypeError"
          : error instanceof RangeError
            ? "RangeError"
            : error instanceof Error
              ? "Error"
              : "NonError"
      }));

      return jsonResponse(
        {
          message: "The donation service encountered an unexpected error.",
          ...(isPaymentRequest ? { outcome: "unknown" } : {})
        },
        500,
        corsHeaders
      );
    }
  }
};
