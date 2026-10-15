# Upload API on Cloudflare Containers

A Worker at `api.audiences.nofluffadvisory.com` forwards every request to one container built from the repository's `Dockerfile` (ADR 0005, stage B). The container holds the invite-key check, tenant isolation and retention (one hour for the live demo); this Worker only routes.

## One-time setup

1. **Plan.** Containers need the Workers Paid plan on the Cloudflare account.
2. **Invite keys.** For each person you invite:

   ```powershell
   aip api-key --tenant tenant_acme
   ```

   Send them the key privately. Collect the printed `"<sha256>": "tenant_acme"` lines into one JSON object.
3. **Secret.** From `deploy/api/`:

   ```powershell
   npm ci
   npx wrangler secret put AIP_API_KEYS   # paste the JSON object, e.g. {"<sha256>":"tenant_acme"}
   ```

   Adding or revoking a key means updating this secret; the container picks it up on its next start.

## Deploy

From `deploy/api/` on a machine with Docker running and `wrangler login` done:

```powershell
npm ci
npm run deploy
```

Wrangler builds the image, pushes it to Cloudflare's registry and deploys the Worker with the custom domain. The first request after an idle period starts the container, which takes a few seconds.

## Check it

```powershell
curl https://api.audiences.nofluffadvisory.com/healthz
curl -H "Authorization: Bearer <invite key>" https://api.audiences.nofluffadvisory.com/v1/record-types
```

## Settings

| Name | Where | Meaning |
| --- | --- | --- |
| `AIP_API_KEYS` | Worker secret | JSON object: SHA-256 of each invite key to its tenant id |
| `AIP_ALLOWED_ORIGINS` | `wrangler.jsonc` vars | Origins allowed by CORS (the demonstrator) |
| `AIP_RETENTION_HOURS` | `wrangler.jsonc` vars | Hours an upload is kept at most (1 for the live demo; see `app/terms.html`) |
