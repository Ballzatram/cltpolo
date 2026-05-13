const DEFAULT_REPOSITORY = "Ballzatram/cltpolo";
const DEFAULT_WORKFLOW = "update-properties.yml";
const DEFAULT_REF = "main";
const DEFAULT_ALLOWED_ORIGIN = "https://charlottepolo.com";
const PROPERTY_VOTES_KEY = "property-votes-v1";

function jsonResponse(body, status, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...headers
    }
  });
}

function getCorsHeaders(request, env) {
  const requestOrigin = request.headers.get("Origin");
  const allowedOrigin = env.ALLOWED_ORIGIN || DEFAULT_ALLOWED_ORIGIN;
  const responseOrigin = requestOrigin === allowedOrigin ? requestOrigin : allowedOrigin;

  return {
    "Access-Control-Allow-Origin": responseOrigin,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin"
  };
}

function isOriginAllowed(request, env) {
  const requestOrigin = request.headers.get("Origin");
  const allowedOrigin = env.ALLOWED_ORIGIN || DEFAULT_ALLOWED_ORIGIN;

  return !requestOrigin || requestOrigin === allowedOrigin;
}

function normalizeVoteTally(tally) {
  const up = Number(tally && tally.up);
  const down = Number(tally && tally.down);

  return {
    up: Number.isFinite(up) && up > 0 ? Math.floor(up) : 0,
    down: Number.isFinite(down) && down > 0 ? Math.floor(down) : 0
  };
}

async function readPropertyVotes(env) {
  if (!env.PROPERTY_VOTES) {
    return null;
  }

  const storedVotes = await env.PROPERTY_VOTES.get(PROPERTY_VOTES_KEY, "json");

  return storedVotes && typeof storedVotes === "object" ? storedVotes : {};
}

async function writePropertyVotes(env, votes) {
  await env.PROPERTY_VOTES.put(PROPERTY_VOTES_KEY, JSON.stringify(votes));
}

async function handleVotes(request, env, corsHeaders) {
  const votes = await readPropertyVotes(env);

  if (!votes) {
    return jsonResponse(
      { message: "Property voting is not configured. Add the PROPERTY_VOTES KV binding to this Worker." },
      503,
      corsHeaders
    );
  }

  if (request.method === "GET") {
    return jsonResponse({ votes }, 200, corsHeaders);
  }

  if (request.method !== "POST") {
    return jsonResponse({ message: "Use GET or POST for property votes." }, 405, corsHeaders);
  }

  const payload = await request.json().catch(() => null);
  const propertyId = String(payload && payload.propertyId ? payload.propertyId : "").trim();
  const vote = Number(payload && payload.vote);
  const previousVote = Number(payload && payload.previousVote);

  if (!/^[a-z0-9-]{1,120}$/.test(propertyId)) {
    return jsonResponse({ message: "A valid propertyId is required." }, 400, corsHeaders);
  }

  if (![1, -1, 0].includes(vote) || ![1, -1, 0].includes(previousVote)) {
    return jsonResponse({ message: "Vote values must be 1, -1, or 0." }, 400, corsHeaders);
  }

  const tally = normalizeVoteTally(votes[propertyId]);

  if (previousVote === 1) {
    tally.up = Math.max(0, tally.up - 1);
  } else if (previousVote === -1) {
    tally.down = Math.max(0, tally.down - 1);
  }

  if (vote === 1) {
    tally.up += 1;
  } else if (vote === -1) {
    tally.down += 1;
  }

  votes[propertyId] = tally;
  await writePropertyVotes(env, votes);

  return jsonResponse({ votes, propertyId, tally }, 200, corsHeaders);
}

async function handleRefresh(request, env, corsHeaders) {
  if (request.method !== "POST") {
    return jsonResponse(
      { message: "Use POST to start the CSV refresh agent." },
      405,
      corsHeaders
    );
  }

  if (!env.GITHUB_TOKEN) {
    return jsonResponse(
      { message: "Refresh endpoint is missing the GITHUB_TOKEN secret." },
      500,
      corsHeaders
    );
  }

  const repository = env.GITHUB_REPOSITORY || DEFAULT_REPOSITORY;
  const workflow = env.GITHUB_WORKFLOW || DEFAULT_WORKFLOW;
  const ref = env.GITHUB_REF || DEFAULT_REF;
  const dispatchUrl = `https://api.github.com/repos/${repository}/actions/workflows/${workflow}/dispatches`;

  const githubResponse = await fetch(dispatchUrl, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "Content-Type": "application/json",
      "User-Agent": "cltpolo-property-refresh-worker",
      "X-GitHub-Api-Version": "2022-11-28"
    },
    body: JSON.stringify({ ref })
  });

  if (githubResponse.status !== 204) {
    const errorData = await githubResponse.json().catch(() => null);
    const errorMessage = errorData && errorData.message
      ? errorData.message
      : "GitHub did not accept the workflow dispatch request.";

    return jsonResponse(
      { message: errorMessage },
      githubResponse.status,
      corsHeaders
    );
  }

  return jsonResponse(
    {
      message: "CSV refresh agent started. It will keep existing listings, append newly discovered listings, update data/charlotte_polo_properties.csv, and publish the refreshed dashboard data after deployment."
    },
    202,
    corsHeaders
  );
}

export default {
  async fetch(request, env) {
    const corsHeaders = getCorsHeaders(request, env);

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders
      });
    }

    if (!isOriginAllowed(request, env)) {
      return jsonResponse(
        { message: "This origin is not allowed to use the property dashboard Worker." },
        403,
        corsHeaders
      );
    }

    const url = new URL(request.url);

    if (url.pathname === "/votes") {
      return handleVotes(request, env, corsHeaders);
    }

    if (url.pathname === "/" || url.pathname === "") {
      return handleRefresh(request, env, corsHeaders);
    }

    return jsonResponse({ message: "Not found." }, 404, corsHeaders);
  }
};
