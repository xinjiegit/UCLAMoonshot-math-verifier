/* eslint-disable next/no-html-link-for-pages -- Document links support the static GitHub Pages export, including repository subpaths. */
import type { Metadata } from 'next';
import { ArrowLeft, ArrowRight, ExternalLink } from 'lucide-react';
import InstallSwitcher, { CommandBlock } from '../install-switcher';
import { siteBasePath } from '../../site-base';
import { releaseDownloadUrl, repositoryUrl } from '../../repository-links';
import { skillVersion } from '../../skill-version';

const description = `Install the Math Verifier ${skillVersion} skill in Codex or Claude Code, run your first paper review, and use focused verification shortcuts.`;

export const metadata: Metadata = {
  title: `Installation guide — UCLA Moonshot Math Verifier ${skillVersion}`,
  description,
  openGraph: { title: `Installation guide — UCLA Moonshot Math Verifier ${skillVersion}`, description, type: 'website' },
};

export default function InstallationGuide() {
  return (
    <>
      <header className="site-header">
        <div className="shell header-inner">
          <a className="wordmark" href={siteBasePath} aria-label={`UCLA Moonshot Math Verifier ${skillVersion} home`}>
            <span className="mark" aria-hidden="true">V</span>
            <span>UCLA Moonshot Math Verifier</span>
            <span className="wordmark-version">{skillVersion}</span>
          </a>
          <a className="guide-home-link" href={siteBasePath}>
            <ArrowLeft size={17} aria-hidden="true" /> Overview
          </a>
        </div>
      </header>

      <main className="shell installation-guide">
        <div className="guide-heading">
          <p className="eyebrow">Get started</p>
          <h1>Install the Math Verifier {skillVersion} skill.</h1>
          <p>
            One installation for your provider’s app and CLI. Follow the steps
            below to set up the skill and review your first paper.
          </p>
        </div>

        <div className="guide-layout">
          <nav className="guide-contents" aria-label="Installation guide contents">
            <p>On this page</p>
            <a href="#before-you-start">Before you start</a>
            <a href="#get-repository">1. Get the repository</a>
            <a href="#install-skill">2. Install the skill</a>
            <a href="#first-review">3. Run your first review</a>
            <a href="#focused-checks">Targeted checks</a>
            <a href="#troubleshooting">Troubleshooting</a>
          </nav>

          <div className="guide-content">
            <section className="guide-section guide-prerequisites" id="before-you-start" aria-labelledby="before-heading">
              <h2 id="before-heading">Before you start</h2>
              <ul>
                <li>A signed-in Codex app or Claude Code session with local file access and fresh subagents.</li>
                <li>Python 3.10 or newer for the local preparation and reporting helpers.</li>
                <li>For PDF input, the <code>pypdf</code> Python package.</li>
              </ul>
              <p className="guide-note">
                Desktop use does not require a separate Codex or Claude CLI installation,
                CLI login, or API key. In Claude’s desktop app, use the Code tab.
                Direct CLI runners require the corresponding authenticated CLI.
              </p>
            </section>

            <section className="guide-section" id="get-repository" aria-labelledby="repository-heading">
              <p className="guide-step">01 / Get the repository</p>
              <h2 id="repository-heading">Keep a local copy.</h2>
              <p>
                Use a Git clone if you want the easiest update path, or download
                a versioned release if you prefer a smaller skill-only bundle.
              </p>
              {repositoryUrl && (
                <div className="source-options">
                  <article className="source-option">
                    <p className="source-option-label">Recommended</p>
                    <h3>Clone with Git</h3>
                    <p>Keep an updatable checkout and pull later releases in place.</p>
                    <CommandBlock
                      command={`git clone ${repositoryUrl}.git math-verifier`}
                      label="Clone the repository"
                      eventName="clone-command-copy"
                    />
                    <a
                      className="guide-text-link"
                      href={repositoryUrl}
                      target="_blank"
                      rel="noreferrer"
                      data-umami-event="repository-open"
                      data-umami-event-location="install-guide"
                    >
                      Browse the source <ExternalLink size={17} aria-hidden="true" />
                    </a>
                  </article>
                  <article className="source-option">
                    <p className="source-option-label">Versioned snapshot</p>
                    <h3>Download the release</h3>
                    <p>
                      Get the installer and skill without Git history, then extract
                      the ZIP and keep that folder in place.
                    </p>
                    <a
                      className="button button-primary release-download-button"
                      href={releaseDownloadUrl}
                      data-umami-event="release-download"
                      data-umami-event-location="install-guide"
                    >
                      Download latest release
                      <ArrowRight size={17} aria-hidden="true" />
                    </a>
                    <a
                      className="guide-text-link releases-link"
                      href={`${repositoryUrl}/releases`}
                      target="_blank"
                      rel="noreferrer"
                      data-umami-event="releases-open"
                    >
                      View all versions <ExternalLink size={17} aria-hidden="true" />
                    </a>
                  </article>
                </div>
              )}
              <p>
                Open a terminal in the extracted or cloned project root: the folder containing
                both <code>README.md</code> and the <code>verifier/</code> directory.
                You do not need to build this website or install its dependencies.
              </p>
            </section>

            <InstallSwitcher />

            <section className="guide-section guide-troubleshooting" id="troubleshooting" aria-labelledby="troubleshooting-heading">
              <h2 id="troubleshooting-heading">If something gets in the way</h2>
              <details>
                <summary>The skill does not appear</summary>
                <p>
                  Restart the app or open a new session after installing. Check
                  that you chose the correct provider and kept the repository
                  folder in place. In Claude’s desktop app, check the Code tab.
                </p>
              </details>
              <details>
                <summary>The installer reports an existing copy or link</summary>
                <p>
                  Already-correct links are safe to reuse. For conflicting copies
                  or links, move the named entry outside the skills directory to
                  preserve local edits, then rerun the installer. It will never
                  overwrite an existing copy. Retired shortcuts are reported and
                  left untouched as well.
                </p>
              </details>
              <details>
                <summary>Python or PDF support is missing</summary>
                <p>
                  Run <code>python3 --version</code> to check your Python version.
                  If it is older than 3.10, use a newer interpreter for the installer
                  and skill helpers. For PDFs, install <code>pypdf</code> in that
                  interpreter’s environment:
                </p>
                <pre className="guide-code"><code>python3 -m pip install pypdf</code></pre>
                <p>
                  If Python is externally managed, use a virtual environment and
                  have the skill use its interpreter. TeX, text, and Markdown input
                  do not need the PDF package.
                </p>
              </details>
              <details>
                <summary>I want to update my installation</summary>
                <p>
                  Update the repository at the same location, then rerun the
                  installer and open a new session. Existing correct links stay
                  unchanged; any new shortcuts are added.
                  If you installed a release ZIP, download and extract the new
                  release, then rerun the installer from the new folder.
                </p>
              </details>
              {repositoryUrl && (
                <a
                  className="guide-text-link"
                  href={`${repositoryUrl}/blob/main/verifier/INSTALL.md`}
                  target="_blank"
                  rel="noreferrer"
                  data-umami-event="repository-open"
                  data-umami-event-location="installation-reference"
                >
                  Full installation reference <ArrowRight size={17} aria-hidden="true" />
                </a>
              )}
            </section>
          </div>
        </div>
      </main>

      <footer>
        <div className="shell guide-footer">
          <span>UCLA Moonshot Math Verifier {skillVersion}</span>
          <a href={siteBasePath}>Back to the project <ArrowRight size={17} aria-hidden="true" /></a>
        </div>
      </footer>
    </>
  );
}
