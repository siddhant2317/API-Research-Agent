/**
 * Vercel serverless function: run the research agent on one app, live.
 * Called from the case study's "Run the agent" button.
 *
 * Workflow:
 *   1. Look up the app in our cached dataset (so we know its docs_url).
 *   2. Query Composio's getToolkits for ground-truth auth schemes.
 *   3. Fetch the docs URL, convert HTML to text (basic).
 *   4. Call GLM-4.5-flash for extraction with a small prompt.
 *   5. Return the structured result.
 *
 * This is a real agent run — not a cached response. It typically takes 10-20s.
 *
 * NOTE: Uses CommonJS (module.exports) for maximum Vercel compatibility.
 */

// API keys MUST be set as Vercel environment variables.
// Set them in: Vercel dashboard → Project → Settings → Environment Variables
const COMPOSIO_KEY = process.env.COMPOSIO_KEY;
const GLM_KEY = process.env.GLM_KEY;

// Load app list — try relative path first, fall back to inlined
let APPS;
try {
  APPS = require('../data/apps.json');
} catch (e) {
  // If the require fails (e.g., path issue on Vercel), use an empty array
  // and return an error that tells the user to check the data file
  APPS = [];
}

module.exports = async (req, res) => {
  // CORS + caching headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Cache-Control', 'no-store');

  // Handle preflight
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  // Check env vars are set
  if (!COMPOSIO_KEY || !GLM_KEY) {
    return res.status(500).json({
      error: 'Environment variables not set',
      missing: [
        !COMPOSIO_KEY && 'COMPOSIO_KEY',
        !GLM_KEY && 'GLM_KEY',
      ].filter(Boolean),
      hint: 'Set these in Vercel dashboard → Settings → Environment Variables. See .env.example for details.',
    });
  }

  const appName = req.query.app;
  if (!appName) {
    return res.status(400).json({ error: 'Missing "app" query parameter' });
  }

  if (!APPS.length) {
    return res.status(500).json({
      error: 'App data not loaded. Check that data/apps.json is deployed alongside the function.',
      hint: 'The function is at /api/run-agent.js, data should be at /data/apps.json'
    });
  }

  // Find the app (case-insensitive)
  const app = APPS.find(a => (a.name || '').toLowerCase() === appName.toLowerCase());
  if (!app) {
    return res.status(404).json({
      error: `App "${appName}" not found in our 100-app list`,
      available: APPS.slice(0, 5).map(a => a.name)
    });
  }

  const t0 = Date.now();
  const result = {
    app: app.name,
    category: app.category,
    docs_url: app.docs_url,
    website: app.website,
    started_at: new Date().toISOString(),
  };

  try {
    // 1. Query Composio for ground truth
    try {
      const composioResp = await fetch(
        `https://backend.composio.dev/api/v3.1/toolkits?search=${encodeURIComponent(app.name)}&limit=5`,
        { headers: { Authorization: `Bearer ${COMPOSIO_KEY}` } }
      );
      if (composioResp.ok) {
        const data = await composioResp.json();
        const items = data.items || [];
        const match = items.find(i => (i.name || '').toLowerCase() === app.name.toLowerCase());
        result.composio = match ? {
          slug: match.slug,
          auth_schemes: match.auth_schemes,
          tools_count: match.meta && match.meta.tools_count,
          managed_auth: match.composio_managed_auth_schemes,
        } : null;
      } else {
        result.composio = null;
        result.composio_status = composioResp.status;
      }
    } catch (e) {
      result.composio = null;
      result.composio_error = e.message;
    }

    // 2. Fetch the docs URL (with timeout via Promise.race)
    let docsMd = '';
    let docsStatus = 0;
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 12000);
      const docsResp = await fetch(app.docs_url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          'Accept': 'text/html,application/xhtml+xml',
        },
        signal: controller.signal,
      });
      clearTimeout(timeout);
      docsStatus = docsResp.status;
      if (docsResp.ok) {
        const html = await docsResp.text();
        // Basic HTML to text — strip tags
        docsMd = html
          .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
          .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
          .replace(/<[^>]+>/g, ' ')
          .replace(/&nbsp;/g, ' ')
          .replace(/&amp;/g, '&')
          .replace(/&lt;/g, '<')
          .replace(/&gt;/g, '>')
          .replace(/&quot;/g, '"')
          .replace(/&#39;/g, "'")
          .replace(/\s+/g, ' ')
          .trim()
          .substring(0, 6000);
      }
    } catch (e) {
      result.docs_error = e.name === 'AbortError' ? 'timeout (12s)' : e.message;
    }
    result.docs_status = docsStatus;
    result.docs_md_length = docsMd.length;

    // 3. Call GLM-4.5-flash for extraction
    const extractionPrompt = `You are researching the API for "${app.name}" (category: ${app.category}).

Official docs URL: ${app.docs_url}

COMPOSIO REGISTRY:
${result.composio ? JSON.stringify(result.composio, null, 2) : '(not in Composio)'}

FETCHED DOCS (truncated, may be empty if fetch failed):
${docsMd}

Return JSON only:
{
  "auth_methods": array of strings from ["oauth2","api_key","basic","bearer_token","jwt","none","other"],
  "self_serve": boolean,
  "gating_type": one of "free","free_trial","paid_required","contact_sales","partner_program","enterprise_only","unknown",
  "api_surface_breadth": one of "broad","medium","narrow","unknown",
  "buildability_score": integer 0-5,
  "main_blocker": one of "none","auth_complexity","gated_access","poor_docs","no_public_api","rate_limits","unknown",
  "confidence": one of "high","medium","low",
  "evidence_urls": array of strings,
  "agent_notes": string
}

Be conservative. Use Composio data if available (it's ground truth).`;

    try {
      const controller2 = new AbortController();
      const timeout2 = setTimeout(() => controller2.abort(), 55000);
      const glmResp = await fetch('https://open.bigmodel.cn/api/paas/v4/chat/completions', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${GLM_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'glm-4.5-flash',
          messages: [
            { role: 'system', content: 'You extract structured API data. Return JSON only.' },
            { role: 'user', content: extractionPrompt },
          ],
          response_format: { type: 'json_object' },
          max_tokens: 2500,
          temperature: 0.2,
          thinking: { type: 'disabled' },
        }),
        signal: controller2.signal,
      });
      clearTimeout(timeout2);

      if (glmResp.ok) {
        const glmData = await glmResp.json();
        const content = glmData.choices[0].message.content;
        let parsed;
        try {
          let cleaned = content.trim();
          if (cleaned.startsWith('```')) {
            cleaned = cleaned.replace(/^```(?:json)?\s*/, '').replace(/\s*```$/, '');
          }
          parsed = JSON.parse(cleaned);
        } catch (e) {
          parsed = { parse_error: e.message, raw: content.substring(0, 500) };
        }
        result.result = parsed;
        result.glm_usage = glmData.usage;
      } else {
        result.result = { error: `GLM HTTP ${glmResp.status}` };
        result.glm_error = (await glmResp.text()).substring(0, 200);
      }
    } catch (e) {
      result.result = { error: e.name === 'AbortError' ? 'GLM timeout (55s)' : e.message };
    }

    result.duration_ms = Date.now() - t0;
    result.success = true;
    return res.status(200).json(result);

  } catch (e) {
    result.duration_ms = Date.now() - t0;
    result.success = false;
    result.error = e.message;
    return res.status(500).json(result);
  }
};
