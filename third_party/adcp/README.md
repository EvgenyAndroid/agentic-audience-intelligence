# Vendored AdCP schemas

These files are copied unmodified from [adcontextprotocol/adcp](https://github.com/adcontextprotocol/adcp) at commit `d033baef9adab46204db6c24a86f315580b40faf` (committed 2026-10-14, accessed 2026-10-14). The source paths are `dist/schemas/3.1.20/bundled/signals/get-signals-response.json` and `dist/schemas/3.1.20/bundled/signals/activate-signal-request.json`. They are distributed under the Apache License 2.0; a copy is in `LICENSE` in this folder.

`adcp.lock.json` records the SHA-256 of each file. `aip.exchange.adcp` refuses to validate if a hash differs, and `scripts\verify-adcp-lock.ps1` checks the same values. `.gitattributes` marks this folder `-text` so Git never rewrites line endings, which would change the hashes.

To re-pin: copy the new bundled files from a newer commit, update the commit, version and hashes in `adcp.lock.json`, update `ADCP_SCHEMA_VERSION` in `src/aip/exchange/adcp.py` if the version changed, and run `.\scripts\check-all.ps1`. Treat field changes as a mapping review, not a mechanical update.
