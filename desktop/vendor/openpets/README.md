# OpenPets selective adaptation

Source: https://github.com/OpenPetsHQ/openpets/tree/951771b774de9e49764150d3a707437cc88e256a

`LICENSE`, `agent-events.ts`, and `protocol.ts` are unmodified source snapshots from that commit (MIT, copyright 2026 OpenPets). The TypeScript files are reference fixtures, not imported by the application.

`events.cjs` removes TypeScript declarations and exports from `packages/agent-events/src/index.ts` and exposes its curated speech pools and validation through CommonJS. It copies only `allowedReactions` and the enum membership check from `packages/client/src/protocol.ts`; an ordinary Error replaces OpenPetsClientError. No IPC transport, assistant, memory, TTS, pet catalog, or plugin host is loaded.

The runtime sends only fixed Chinese status text through the validator. Model replies stay in the control window as text nodes. Successful chat changes the reaction to idle, never success. Task success reactions remain unavailable until real tool results exist.

`test/desktop_contract.cjs` evaluates the original speech functions and checks their behavior against the adaptation, plus enum parity, independent cancellation and missing-animation fallback. The original functions do not sanitize HTML; UI uses textContent regardless.
