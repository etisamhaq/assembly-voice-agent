# Second Chair — website

The marketing site. Deployed separately from the app: Next.js on Vercel, seven prerendered
pages, no server.

```bash
npm install
npm run dev     # http://localhost:3000
npm run build
```

## Structure

```
app/          one route per page, plus not-found.tsx
components/   Nav, Footer, DemoStatus, HeroTranscript, Console, Cta
lib/          content.ts — all copy and data in one place
```

Two pieces of behaviour are worth knowing about.

**`HeroTranscript`** plays a real excerpt of the reference call, timing each warning to land a
beat after the line that caused it — the gap between the two is the product. Under
`prefers-reduced-motion` it renders the finished state immediately.

**`DemoStatus`** probes the app's `/api/health`. The demo runs on a container that sleeps when
idle, so a first-time visitor can click and watch nothing happen for forty seconds. A short
first request separates "awake" from "waking", and a longer second one decides live from
unreachable. It needs CORS on the app side.

## Design

Cool archival paper, deep green-black ink, ultramarine accent. Newsreader for headings and body
(it is a document product), Inter for interface chrome, monospace only inside simulated product
surfaces where it is content rather than decoration.

The recurring layout is `.record` — a wide main column with a narrow annotation margin. That is
the site's version of the two channels: the record everyone sees, and the note only one person
gets. It collapses to a single column below 880px.
