# UCLA Moonshot Math Verifier v.1.0 website

The public website is a statically exported Vinext site deployed through GitHub
Pages. Its source lives in `app/`; the generated output is `dist/client/`.

The homepage links to a dedicated installation guide at `install.html` in the
static export (`/install` during development). Both pages are exported as HTML.
Installation links are relative; return links explicitly target the site base,
shared with Vite in `site-base.ts`, so they work under a GitHub Pages repository
subpath and do not depend on the installation URL's trailing slash. Flat HTML
output avoids a trailing-slash prerender issue in the current Vinext version.

## Local development

```sh
pnpm install
pnpm dev
```

## Production build

```sh
pnpm build
```

The build reads `GITHUB_REPOSITORY` to set the correct Pages base path. The
deployment workflow also provides `NEXT_PUBLIC_REPOSITORY_URL` so links point to
the final public repository rather than the local placeholder.

During `pnpm dev`, `repository-links.ts` supplies the current development
repository URL so repository and release-download controls do not disappear.
The deployment environment always overrides that fallback with the repository
actually serving GitHub Pages.

## Downloads and first-party analytics

Tagged releases produce a skill-only `math-verifier.zip` plus its SHA-256 file.
The release tag must match `verifier/math-paper-verifier/VERSION` exactly; the
current release tag is `v.1.0`.
The website uses GitHub's stable latest-asset URL, so its download buttons do not
need to change for each release. The ZIP contains the top-level README and license
alongside `verifier/`; it deliberately omits the website and research data.

The site supports a self-hosted Umami instance. Page views and the following
anonymous interaction events are recorded only when all required build variables
are configured:

- `release-download`
- `repository-open`, `releases-open`, and `clone-command-copy`
- `provider-select` and `install-command-copy`
- prompt-copy events for the full review and both focused shortcuts

Set these GitHub Actions repository variables before deploying:

- `UMAMI_SCRIPT_URL`: the full tracker script URL, such as
  `https://stats.example.edu/script.js`
- `UMAMI_WEBSITE_ID`: the website ID from the Umami dashboard
- `UMAMI_DOMAINS` (optional): a comma-separated production-domain allowlist

If the script URL or website ID is absent, no analytics script is emitted. The
tracker respects Do Not Track and excludes URL queries and fragments. No paper,
prompt, finding, filename, or local-system data is sent by the website. Event
data is limited to the interaction location and the selected provider.

## Demo video

The homepage's `#demo` section plays the 2:28 Partitioning Clusters demo (v7),
with recorded human narration and the animated curve explanation, using a native
HTML video player. Public video, poster, WebVTT captions,
and transcript assets live in `public/media/`. The video loads when the visitor
starts playback; it does not autoplay. Relative asset URLs work at the development
root and when GitHub Pages serves the site from a repository subpath.

To update the demo, replace those four assets together so captions and transcript
stay in sync, and update the displayed runtime and media version query in
`app/page.tsx` when needed so browsers fetch the revised files.
