# Repository Instructions

## Project purpose
A small, read-only HTTP artifact browser deployed only on remote Linux/embedded devices. It is not a general file manager, upload service, IDE, or DSH plugin.

## Non-negotiable constraints
- Default and supported v0.1 bind addresses are loopback only; access remotely through SSH port forwarding.
- Never add write, upload, rename, delete, shell execution, or arbitrary filesystem APIs.
- Every file operation must be scoped to an explicitly configured root. Resolve paths and reject traversal and symlink escapes.
- Do not reveal physical root paths in API responses.
- Stream file content; do not read large files fully into memory. Preserve HTTP Range semantics for media and large downloads.
- Do not add authentication complexity while the service is loopback-only; do not silently expand network exposure.
- Keep runtime dependencies small and support Python 3.10+ on Linux ARM64 and x86_64.
- Do not introduce Docker, a database, a reverse proxy, or a frontend build system unless a concrete requirement justifies it.

## Engineering workflow
- Keep configuration explicit and local; never commit device-specific real paths, credentials, tokens, or private data.
- Add tests for path traversal, symlink escapes, hidden files, read-only behavior, and byte-range handling.
- Run focused tests and compile checks for changed code. State clearly when device-side ARM64 validation has not been performed.
- Keep the UI small and accessible; use browser-native preview for HTML, images, audio, video, and PDF where possible.
- Do not claim Markdown rendering or media seeking unless it has been verified.
