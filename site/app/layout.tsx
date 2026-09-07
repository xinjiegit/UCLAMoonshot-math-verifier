import type { Metadata } from 'next';
import './globals.css';
import { skillVersion } from '../skill-version';

const analyticsScriptUrl = process.env.NEXT_PUBLIC_UMAMI_SCRIPT_URL || '';
const analyticsWebsiteId = process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID || '';
const analyticsDomains = process.env.NEXT_PUBLIC_UMAMI_DOMAINS || '';

export const metadata: Metadata = {
  title: `UCLA Moonshot Math Verifier ${skillVersion} — Structured verification for mathematical papers`,
  description:
    `UCLA Moonshot Math Verifier ${skillVersion} presents a public skill for structured verification of mathematical papers in Codex and Claude Code.`,
  keywords: [
    'mathematics',
    'UCLA Moonshot Math Verifier',
    'Math Verifier',
    'math-paper-verifier',
    'mathematical paper review',
    'proof audit',
    'Codex skill',
    'Claude skill',
  ],
  openGraph: {
    title: `UCLA Moonshot Math Verifier ${skillVersion} — Structured verification for mathematical papers`,
    description:
      `UCLA Moonshot Math Verifier ${skillVersion} presents a public skill for structured verification of mathematical papers in Codex and Claude Code.`,
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {analyticsScriptUrl && analyticsWebsiteId && (
          <script
            defer
            src={analyticsScriptUrl}
            data-website-id={analyticsWebsiteId}
            data-domains={analyticsDomains || undefined}
            data-do-not-track="true"
            data-exclude-search="true"
            data-exclude-hash="true"
          />
        )}
        {children}
      </body>
    </html>
  );
}
