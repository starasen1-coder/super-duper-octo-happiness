# Optional LEMO Opuscar handoff

LEMO Opuscar is a code-driven film-making skill for compatible coding agents. It is not a data collector, research validator, MT5 component, or autonomous market-analysis engine.

## Compatibility and license

Reviewed upstream release: **v2.0.0**.

- The upstream README requires Node.js 20+, ffmpeg 7+, and Python 3.11+.
- Three styles require an external image-generation tool; the README does not state that a GPU is required.
- The code is MIT.
- Since v2.0.0, documentation and style prompts are CC BY-NC 4.0; commercial use of those materials requires separate permission.
- Demo films are CC BY 4.0. Do not copy upstream styles, prompts, demos, sample libraries, or assets into this repository.

Upstream: https://github.com/lemomo-ai/lemo-opuscar

## Integration boundary

This repository provides a provenance manifest for a manual handoff only. LEMO Opuscar is a coding-agent skill intended for its supported agent environment; this ChatGPT session and the research VPS do not expose a compatible LEMO runtime. Therefore:

- Do not install LEMO Opuscar on the always-on research VPS.
- Do not claim that this manifest adapter renders a video.
- Prepare a curated, non-sensitive report and its manifest; then, if desired, use LEMO Opuscar manually in a compatible coding-agent environment.
- Keep the original Markdown/HTML report as the authoritative output.
- Never send credentials, broker data, personal account data, browser sessions, or private connector exports to the renderer.

The manifest records the report ID, renderer version, input hashes, intended use, and asset credits. Commercial use of CC BY-NC style documentation is blocked unless separate permission is explicitly recorded.
