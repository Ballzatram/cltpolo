const DEFAULT_REPOSITORY = "Ballzatram/cltpolo";
const DEFAULT_WORKFLOW = "update-properties.yml";
const DEFAULT_REF = "main";
const DEFAULT_ALLOWED_ORIGIN = "https://charlottepolo.com";

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
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin"
  };
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

    if (request.method !== "POST") {
      return jsonResponse(
        { message: "Use POST to start the CSV refresh agent." },
        405,
        corsHeaders
      );
    }

    const requestOrigin = request.headers.get("Origin");
    const allowedOrigin = env.ALLOWED_ORIGIN || DEFAULT_ALLOWED_ORIGIN;

    if (requestOrigin && requestOrigin !== allowedOrigin) {
      return jsonResponse(
        { message: "This origin is not allowed to start the CSV refresh agent." },
        403,
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
        message: "CSV refresh agent started. The dashboard will reload committed data automatically in about a minute."
      },
      202,
      corsHeaders
    );
  }
};
