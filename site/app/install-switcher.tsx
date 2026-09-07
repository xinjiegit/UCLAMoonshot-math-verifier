'use client';

import { Check, Clipboard } from 'lucide-react';
import { useEffect, useState } from 'react';
import { trackEvent } from './analytics';

const providers = {
  Codex: { command: 'python3 verifier/install.py codex', directory: '~/.agents/skills/', prefix: '$' },
  'Claude Code': { command: 'python3 verifier/install.py claude', directory: '~/.claude/skills/', prefix: '/' },
};

type Provider = keyof typeof providers;

export function CommandBlock({
  command,
  label,
  eventName,
  eventData,
}: {
  command: string;
  label: string;
  eventName?: string;
  eventData?: Record<string, string>;
}) {
  const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle');

  useEffect(() => {
    if (status !== 'copied') return;
    const timeout = window.setTimeout(() => setStatus('idle'), 2000);
    return () => window.clearTimeout(timeout);
  }, [status]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setStatus('copied');
      if (eventName) trackEvent(eventName, eventData);
    } catch {
      setStatus('failed');
    }
  }

  return (
    <div className="command-block">
      <div className="command-toolbar">
        <span>{label}</span>
        <button onClick={copy} type="button" aria-label={`Copy: ${label}`}>
          {status === 'copied' ? <Check size={17} aria-hidden="true" /> : <Clipboard size={17} aria-hidden="true" />}
          {status === 'copied' ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre><code>{command}</code></pre>
      <output className={status === 'failed' ? 'copy-error' : 'visually-hidden'}>
        {status === 'failed' ? 'Copy is unavailable. Select the text above and copy it manually.' : status === 'copied' ? 'Copied to clipboard.' : ''}
      </output>
    </div>
  );
}

export default function InstallSwitcher() {
  const [active, setActive] = useState<Provider>('Codex');
  const { command, directory, prefix } = providers[active];

  return (
    <>
      <section className="guide-section" id="install-skill" aria-labelledby="install-heading">
        <p className="guide-step">02 / Install the skill</p>
        <h2 id="install-heading">Choose where you’ll use it.</h2>
        <p>Choose your provider, then run the command below in a terminal at the repository root.</p>
        <fieldset className="provider-choice">
          <legend className="visually-hidden">Choose your provider</legend>
          {(Object.keys(providers) as Provider[]).map((provider) => (
            <button
              aria-pressed={active === provider}
              key={provider}
              onClick={() => {
                setActive(provider);
                trackEvent('provider-select', { provider });
              }}
              type="button"
            >
              {provider}
            </button>
          ))}
        </fieldset>
        <CommandBlock
          key={active}
          command={command}
          label="Run in your terminal"
          eventName="install-command-copy"
          eventData={{ provider: active }}
        />
        <p>
          This links the main skill and both shortcuts into <code>{directory}</code>.
          The same installation works in the app and CLI. It does not install a provider CLI.
        </p>
        <p className="guide-note">
          Keep the repository folder in place: the installed skills link to it.
          Existing copies or conflicting links are never overwritten.
        </p>
      </section>

      <section className="guide-section" id="first-review" aria-labelledby="review-heading">
        <p className="guide-step">03 / Run your first review</p>
        <h2 id="review-heading">Open a new session with your paper.</h2>
        <p>
          Restart {active === 'Codex' ? 'Codex' : 'Claude Code'} or open a new session
          so it discovers the skills. In the desktop app, open a local task with
          access to your paper{active === 'Claude Code' ? ' in the Code tab, not an ordinary Chat conversation' : ''}.
        </p>
        <CommandBlock
          command="Use math-paper-verifier to verify paper.pdf and give me a findings report."
          label={`Ask in ${active}`}
          eventName="first-review-prompt-copy"
          eventData={{ provider: active }}
        />
        <p>
          Replace <code>paper.pdf</code> with your file or its path. You can also
          provide a TeX source folder, a text file, or Markdown. If you have both
          TeX and its matching compiled PDF, supply both for more readable finding locations.
        </p>
        <div className="guide-callout">
          <h3>Your results</h3>
          <p>
            Open <code>verifier-report.md</code> for the human-readable report.
            The accompanying <code>verifier-output.json</code> retains the structured
            findings. Reports include severity, supporting evidence, and paper
            locations where they can be established.
          </p>
        </div>
      </section>

      <section className="guide-section" id="focused-checks" aria-labelledby="focused-heading">
        <p className="guide-step">Optional / Targeted checks</p>
        <h2 id="focused-heading">Check something specific.</h2>
        <p>
          Use a shortcut when you want just one kind of check instead of the full
          review. Enter these in your {active} conversation, not your terminal.
        </p>
        <h3>A focus you specify</h3>
        <CommandBlock
          key={`focused-${active}`}
          command={`${prefix}math-paper-verifier-focused paper.pdf — check the equations in Section 3`}
          label="Focused verification"
          eventName="focused-prompt-copy"
          eventData={{ provider: active }}
        />
        <p>
          Describe what you want examined: boundary cases, quantifier order,
          whether a construction is well-defined, or another mathematical aspect.
          Equations and boundary cases are examples, not a fixed menu.
        </p>
        <h3>Counterexamples to central claims</h3>
        <CommandBlock
          key={`refuter-${active}`}
          command={`${prefix}math-paper-verifier-central-refuter paper.pdf`}
          label="Central refuter"
          eventName="central-refuter-prompt-copy"
          eventData={{ provider: active }}
        />
        <p className="guide-note">
          These shortcuts use the same reporting and safeguards as the main skill,
          but do not perform a full paper review or verify outside sources.
        </p>
      </section>
    </>
  );
}
