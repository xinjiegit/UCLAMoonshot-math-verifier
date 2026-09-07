/* eslint-disable next/no-html-link-for-pages -- Relative document links support the static GitHub Pages export, including repository subpaths. */
import {
  ArrowRight,
  Braces,
  Check,
  Code2,
  ExternalLink,
  FileSearch,
  GitBranch,
  Library,
  Play,
  ScanSearch,
  ShieldCheck,
  Sigma,
} from 'lucide-react';
import { releaseDownloadUrl, repositoryUrl } from '../repository-links';
import { skillVersion } from '../skill-version';

// The dev server uses app routes; GitHub Pages serves the exported HTML file.
const installationHref = process.env.NODE_ENV === 'development' ? 'install' : 'install.html';
// Relative media URLs work at the development root and under a Pages repository subpath.
const demoAssetBase = 'media/math-verifier-demo';
const demoAssetUrl = (suffix: string) => `${demoAssetBase}${suffix}?v=partitioning-clusters-v7`;

const team = [
  {
    role: 'Student researchers',
    names: ['Xinjie He', 'Hyunsik Chae', 'Alex Taylor', 'Kyle Hess'],
  },
  {
    role: 'Principal investigators',
    names: ['Kai-Wei Chang', 'Raghu Meka', 'Violet Peng', 'Amit Sahai', 'Terence Tao', 'Wei Wang'],
  },
];

const auditChecks = [
  {
    icon: GitBranch,
    title: 'Proof structure',
    text: 'Follow dependencies from hypotheses to the main result and flag steps that do not support the claimed conclusion.',
  },
  {
    icon: Sigma,
    title: 'Equations and constants',
    text: 'Re-derive numbered equations, signs, constants, and transitions between equations.',
  },
  {
    icon: Braces,
    title: 'Quantifiers and boundaries',
    text: 'Check endpoints, exceptional cases, theorem scope, omitted hypotheses, and changes in quantifier order.',
  },
  {
    icon: Library,
    title: 'External obligations',
    text: 'Verify that each cited source supports the claimed result and that its hypotheses are satisfied when the result is applied.',
  },
];

const workflow = [
  {
    number: '01',
    title: 'Read the argument globally',
    text: 'Map the main claims and dependency chain, and flag outside facts for separate source checking.',
  },
  {
    number: '02',
    title: 'Force local coverage',
    text: 'Partition the paper into small verification regions and audit every region line by line.',
  },
  {
    number: '03',
    title: 'Run targeted checks',
    text: 'Add equation, boundary, citation, or counterexample passes where the mathematical structure calls for them.',
  },
  {
    number: '04',
    title: 'Consolidate findings',
    text: 'Merge the results obtained from independent passes and generate a human-readable report.',
  },
];

const findingTaxonomy = [
  {
    branch: 'Not repairable',
    question: 'Does the failure reach a central claim?',
    findings: [
      {
        className: 'taxonomy-critical',
        label: 'Central unsalvageable error',
        summary: 'A central result cannot be recovered within the paper’s method.',
      },
      {
        className: 'taxonomy-noncentral',
        label: 'Noncentral unsalvageable error',
        summary: 'A secondary result fails, while the paper’s central contribution remains intact.',
      },
    ],
  },
  {
    branch: 'Repairable',
    question: 'What is the minimum adequate repair?',
    findings: [
      {
        className: 'taxonomy-major',
        label: 'Major repairable gap',
        summary: 'The repair needs substantive new mathematics, materially changes a principal result, or reworks multiple dependencies.',
      },
      {
        className: 'taxonomy-minor',
        label: 'Minor repairable gap',
        summary: 'A local correction or short addition works within the existing method and leaves the main results intact.',
      },
    ],
  },
  {
    branch: 'No mathematical change',
    question: 'Is the correction already forced by context?',
    findings: [
      {
        className: 'taxonomy-cosmetic',
        label: 'Cosmetic or exposition only',
        summary: 'The correction improves wording, notation, or presentation without changing the mathematical reasoning.',
      },
    ],
  },
];

const verdictTaxonomy = [
  { verdict: 'Reject', trigger: 'Central unsalvageable error' },
  { verdict: 'Major revision', trigger: 'Any major repairable gap' },
  { verdict: 'Minor revision', trigger: 'Noncentral unsalvageable or minor repairable' },
  { verdict: 'Accept', trigger: 'No mathematical gap, or cosmetic findings only' },
];

function RepoLink({
  path,
  children,
  className = '',
}: {
  path?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const href = repositoryUrl
    ? path
      ? `${repositoryUrl}/blob/main/${path}`
      : repositoryUrl
    : '#install';
  return (
    <a
      className={className}
      href={href}
      rel="noreferrer"
      target="_blank"
      data-umami-event="repository-open"
      data-umami-event-location={path ? 'documentation' : 'navigation'}
    >
      {children}
    </a>
  );
}

export default function Home() {
  return (
    <main>
      <header className="site-header">
        <div className="shell header-inner">
          <a className="wordmark" href="#top" aria-label={`UCLA Moonshot Math Verifier ${skillVersion} home`}>
            <span className="mark" aria-hidden="true">
              V
            </span>
            <span>UCLA Moonshot Math Verifier</span>
            <span className="wordmark-version">{skillVersion}</span>
            <span className="wordmark-note">skill for mathematics</span>
          </a>

          <nav className="primary-nav" aria-label="Primary navigation">
            <a href="#method">Method</a>
            <a href="#evidence">Evidence</a>
            <a href="#related-work">Related work</a>
            <a href={installationHref}>Install</a>
            <RepoLink className="github-link">
              <Code2 size={15} strokeWidth={1.8} aria-hidden="true" />
              Repository
            </RepoLink>
          </nav>
        </div>
      </header>

      <section className="hero" id="top">
        <div className="shell hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">
              Open research tool · Codex and Claude adapters
            </p>
            <h1>Structured verification for mathematical papers.</h1>
            <p className="hero-lede">
              UCLA Moonshot Math Verifier {skillVersion} turns a broad request to “check this paper” into a
              structured set of independent checks, then produces a clear
              report for human review.
            </p>
            <div className="hero-actions">
              <a
                className="button button-primary"
                href={installationHref}
                data-umami-event="installation-guide-open"
                data-umami-event-location="homepage-hero"
              >
                Install the skill
                <ArrowRight size={16} aria-hidden="true" />
              </a>
              {releaseDownloadUrl && (
                <a
                  className="button button-secondary"
                  href={releaseDownloadUrl}
                  data-umami-event="release-download"
                  data-umami-event-location="homepage-hero"
                >
                  Download ZIP
                </a>
              )}
              <a className="button button-secondary" href="#demo">
                Watch the demo
                <Play size={16} aria-hidden="true" />
              </a>
            </div>
            <p className="scope-note">
              For working mathematicians, authors, and readers. Designed to
              assist expert review.
            </p>
          </div>

          <div className="audit-sheet" aria-label="Illustrative structured finding, not an experimental result">
            <div className="sheet-head">
              <span>ILLUSTRATIVE FINDING</span>
              <span className="status-dot">
                <span aria-hidden="true" /> needs review
              </span>
            </div>
            <div className="sheet-body">
              <div className="location-rule">
                <span>LOCATION</span>
                <strong>§4, proof of Theorem 2 · display (17)</strong>
              </div>
              <div className="math-sample" aria-label="Mathematical expression">
                <span>claimed</span>
                <p>
                  ‖T f‖<sub>q</sub> ≤ C ‖f‖<sub>p</sub>
                </p>
              </div>
              <div className="finding-text">
                <span>MECHANISM</span>
                <p>
                  The interpolation step uses the endpoint estimate at{' '}
                  <i>p</i> = 1, while the preceding lemma only establishes it
                  for <i>p</i> &gt; 1. The stated range therefore does not follow.
                </p>
              </div>
              <div className="sheet-footer">
                <span>
                  <Check size={13} aria-hidden="true" /> exact location
                </span>
                <span>
                  <Check size={13} aria-hidden="true" /> failure mechanism
                </span>
                <span>
                  <Check size={13} aria-hidden="true" /> repair task
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="principle-strip" aria-label="Design principle">
        <div className="shell principle-inner">
          <span className="principle-label">CORE DESIGN PRINCIPLE</span>
          <p>
            The paper should be reviewed systematically across multiple
            passes so that errors are less likely to be missed.
          </p>
          <ScanSearch size={24} strokeWidth={1.5} aria-hidden="true" />
        </div>
      </section>

      <section className="section shell demo-section" id="demo" aria-labelledby="demo-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Quick demonstration</p>
            <h2 id="demo-title">See a review in practice.</h2>
          </div>
          <p>
            Install the skill in Codex, review a local PDF, and follow a finding
            from the completed report to the paper and its supporting evidence.
          </p>
        </div>
        <figure className="demo-player">
          <video
            controls
            playsInline
            preload="none"
            width={1920}
            height={1080}
            poster={demoAssetUrl('-poster.png')}
            aria-label="UCLA Moonshot Math Verifier demo: review a local paper"
          >
            <source src={demoAssetUrl('.mp4')} type="video/mp4" />
            <track
              kind="captions"
              src={demoAssetUrl('.vtt')}
              srcLang="en"
              label="English"
            />
            <a href={demoAssetUrl('.mp4')}>Download the demo video</a> to watch it.
          </video>
          <figcaption className="demo-caption">
            <span>2:28 · English narration and captions</span>
            <div className="demo-links">
              <a href={demoAssetUrl('-transcript.txt')}>Read the transcript</a>
              <a href={demoAssetUrl('.mp4')} download>Download video</a>
            </div>
          </figcaption>
        </figure>
      </section>

      <section className="section shell" id="method">
        <div className="section-heading method-heading">
          <div>
            <p className="eyebrow">The method</p>
            <h2>A structured workflow for checking the whole argument.</h2>
          </div>
              <p>
                The Math Verifier skill first reads the paper as a whole, then checks it again
                in small sections. You can also invoke additional passes dedicated to
                equation checking, boundary cases, counterexample searches, or another
                focus you specify. A separate web-enabled pass checks cited sources.
                The findings are combined into a report that ranks candidate errors by
                severity.
              </p>
        </div>

        <ol className="workflow" aria-label="Audit workflow">
          {workflow.map((item, index) => (
            <li className="workflow-step" key={item.number}>
              <div className="step-top">
                <span>{item.number}</span>
                {index < workflow.length - 1 && (
                  <ArrowRight size={17} strokeWidth={1.5} aria-hidden="true" />
                )}
              </div>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </li>
          ))}
        </ol>

        <div className="method-surfaces">
          <div className="section-heading surfaces-heading">
            <div>
              <p className="eyebrow">Checks within the workflow</p>
              <h2>What the passes are organized to inspect.</h2>
            </div>
            <p>
              A proof can fail in its global structure, a local calculation, a
              boundary case, or a fact imported from the literature. The
              workflow treats these as distinct checks.
            </p>
          </div>
          <div className="checks-grid">
            {auditChecks.map((item) => {
              const Icon = item.icon;
              return (
                <article className="check-item" key={item.title}>
                  <Icon size={22} strokeWidth={1.55} aria-hidden="true" />
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </article>
              );
            })}
          </div>
          <div className="counterexample-note">
            <FileSearch size={21} strokeWidth={1.5} aria-hidden="true" />
            <p>
              A separate refuter pass can be enabled to search for small
              counterexamples to test central claims, as a complement to tracing
              the proof forward.
            </p>
          </div>
        </div>

        <div className="finding-taxonomy" id="taxonomy" aria-labelledby="taxonomy-title">
          <div className="section-heading taxonomy-heading">
            <div>
              <p className="eyebrow">Finding taxonomy</p>
              <h2 id="taxonomy-title">How candidate errors are classified.</h2>
            </div>
            <p>
              The class is determined by the smallest adequate repair and what
              that repair changes. A problem is not major merely because it
              appears in a central theorem.
            </p>
          </div>

          <div className="taxonomy-grid" aria-label="Finding classification taxonomy">
            {findingTaxonomy.map(({ branch, question, findings }) => (
              <section className="taxonomy-branch" key={branch}>
                <div className="taxonomy-branch-head">
                  <p>{branch}</p>
                  <h3>{question}</h3>
                </div>
                <div className="taxonomy-classes">
                  {findings.map((finding) => (
                    <article className={`taxonomy-card ${finding.className}`} key={finding.label}>
                      <h3>{finding.label}</h3>
                      <p>{finding.summary}</p>
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>

          <div className="verdict-map" aria-label="Finding classes mapped to overall paper verdicts">
            <div className="verdict-map-intro">
              <p className="eyebrow">Overall paper verdict</p>
              <p>Apply these rules in order to determine the recommendation.</p>
            </div>
            {verdictTaxonomy.map(({ verdict, trigger }) => (
              <div className="verdict-item" key={verdict}>
                <strong>{verdict}</strong>
                <span>{trigger}</span>
              </div>
            ))}
          </div>
          <p className="taxonomy-calibration-note">
            <strong>Calibration note.</strong> In human review of model-generated
            findings, we observed that the model can sometimes overstate an
            error’s severity. Severity labels should therefore be checked against
            the changes actually needed to fix the error.
          </p>
        </div>
      </section>

      <section className="section shell evidence-section" id="evidence">
        <div className="section-heading evidence-heading">
          <div>
            <p className="eyebrow">Evidence for the design</p>
            <h2>Structured verification found more known errors than a general prompt.</h2>
          </div>
          <p>
            In a controlled study using GPT-5.5-Sol-Ultra on 17 papers with 40 author-documented errors,
            two runs using required section-by-section verification found 32. Two
            runs using a general review prompt that left the strategy to the model
            found 25, while two runs using a prescribed whole-paper verification
            strategy found 26.
          </p>
        </div>

        <div className="evidence-grid">
          <div className="result-chart" aria-label="GPT-5.5-Sol-Ultra: known errors recovered out of 40">
            <div className="chart-scale" aria-hidden="true">
              <span>0</span>
              <span>10</span>
              <span>20</span>
              <span>30</span>
              <span>40</span>
            </div>
            <div className="bar-row">
              <div className="bar-label">
                <strong>Decomposed</strong>
                <span>two-run union</span>
              </div>
              <div className="bar-track">
                <span className="bar decomposed-bar" style={{ width: '80%' }}>
                  32
                </span>
              </div>
            </div>
            <div className="bar-row">
              <div className="bar-label">
                <strong>Guided</strong>
                <span>two-run union</span>
              </div>
              <div className="bar-track">
                <span className="bar guided-bar" style={{ width: '65%' }}>
                  26
                </span>
              </div>
            </div>
            <div className="bar-row">
              <div className="bar-label">
                <strong>Generic</strong>
                <span>two-run union</span>
              </div>
              <div className="bar-track">
                <span className="bar generic-bar" style={{ width: '62.5%' }}>
                  25
                </span>
              </div>
            </div>
            <p className="chart-caption">GPT-5.5-Sol-Ultra · known corrections recovered / 40</p>
          </div>

          <aside className="evidence-notes evidence-report-note">
            <h3>GPT-6 update</h3>
            <p>
              The skill supports GPT-6 and has passed compatibility checks.
            </p>
            <p>
              In a preliminary follow-up on four papers, with one run per
              strategy per paper, section-by-section verification again found
              more known errors than the general review prompt or the prescribed
              whole-paper strategy. This suggests the advantage carries over to
              GPT-6, but is not a full-scale replication. Scoring remains
              provisional pending human review.
            </p>
            <p>
              <strong>Technical report coming soon.</strong>
            </p>
          </aside>
        </div>

        <div className="comparison evidence-comparison">
          <div className="comparison-intro">
            <h3 className="eyebrow">What does structured verification add?</h3>
            <p className="comparison-description">
              A general prompt asks the model to find errors without requiring
              it to check every part of the argument. The Math Verifier skill assigns
              small portions of the paper to dedicated workers, instructs
              them to check each step, and records what they actually examined.
              A separate whole-paper pass checks how the argument fits together.
            </p>
          </div>
          <div className="comparison-column muted-column">
            <span className="column-label">GENERAL PROMPT</span>
            <p className="prompt-quote">“Read this paper and find errors.”</p>
            <ul>
              <li>No required division into small verification tasks</li>
              <li>No requirement to check every region individually</li>
            </ul>
          </div>
          <div className="comparison-column structured-column">
            <span className="column-label">MATH VERIFIER SKILL</span>
            <ul>
              <li>Independent whole-paper and local verification passes</li>
              <li>Small paper regions checked step by step</li>
              <li>A record of which regions were actually checked</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="section related-section" id="related-work">
        <div className="shell related-compact">
          <h2>Related Work</h2>
          <p>
            The closest precedents are narrower in scope.{' '}
            <a
              href="https://github.com/NNHieu/math_auditing_examples"
              rel="noreferrer"
              target="_blank"
            >
              Nguyen–Zhang
            </a>{' '}
            provide a practical Claude skill for math paper verification, while{' '}
            <a
              href="https://arxiv.org/abs/2605.20531"
              rel="noreferrer"
              target="_blank"
            >
              Pseudo-Formalization + Block Verification
            </a>{' '}
            experimentally studies decomposed verification.{' '}
            <strong>
              UCLA Moonshot Math Verifier develops math paper verification as a reusable,
              provider-neutral skill, backed by controlled evaluation on
              author-documented mathematical errors.
            </strong>
          </p>
        </div>
      </section>

      <section className="team-section" id="team" aria-labelledby="team-heading">
        <div className="shell team-layout">
          <h2 id="team-heading">Team</h2>
          <div className="team-groups">
            {team.map(({ role, names }) => (
              <div className="team-group" key={role}>
                <h3>{role}</h3>
                <ul aria-label={role}>
                  {names.map((name) => <li key={name}>{name}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section install-section" id="install">
        <div className="shell install-grid">
          <div className="install-copy">
            <p className="eyebrow">Use the skill</p>
            <h2>One installation for app and CLI.</h2>
            <p>
              Set up the Math Verifier skill in Codex or Claude Code, then start with a
              full paper review or a focused check. The installation guide walks
              through setup, your first report, and the available shortcuts.
            </p>
            <div className="runtime-list" aria-label="Supported runtimes">
              <span>Codex · app and CLI</span>
              <span>Claude Code · desktop and CLI</span>
            </div>
          </div>
          <div className="install-actions">
            <a
              className="button install-guide-link"
              href={installationHref}
              data-umami-event="installation-guide-open"
              data-umami-event-location="homepage-install"
            >
              Open the installation guide
              <ArrowRight size={20} aria-hidden="true" />
            </a>
            {releaseDownloadUrl && (
              <a
                className="install-download-link"
                href={releaseDownloadUrl}
                data-umami-event="release-download"
                data-umami-event-location="homepage-install"
              >
                Download latest release ZIP
              </a>
            )}
          </div>
        </div>
      </section>

      <section className="section shell responsible-section">
        <div className="responsible-mark" aria-hidden="true">
          <ShieldCheck size={28} strokeWidth={1.4} />
        </div>
        <div>
          <p className="eyebrow">A review instrument, not a verdict</p>
          <h2>Keep a mathematician in the loop.</h2>
        </div>
        <div className="responsible-copy">
          <p>
            The output is a set of candidate findings. Each one should be checked
            against the paper, its definitions, and—when relevant—the cited
            source before it is treated as an error.
          </p>
          <RepoLink path="README.md" className="text-link">
            Read the documentation
            <ExternalLink size={14} aria-hidden="true" />
          </RepoLink>
        </div>
      </section>

      <footer>
        <div className="shell footer-inner">
          <div>
            <a className="wordmark footer-wordmark" href="#top">
              <span className="mark" aria-hidden="true">
                V
              </span>
              <span>UCLA Moonshot Math Verifier {skillVersion}</span>
            </a>
            <p>Structured verification for mathematical papers.</p>
          </div>
          <div className="footer-links">
            <a href="#demo">Demo</a>
            <a href="#method">Method</a>
            <a href="#evidence">Evidence</a>
            <a href="#related-work">Related work</a>
            <a href="#team">Team</a>
            <a href={installationHref}>Install</a>
            <RepoLink>GitHub</RepoLink>
          </div>
        </div>
      </footer>
    </main>
  );
}
