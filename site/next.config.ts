import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'export',
  // Export install.html directly: this Vinext version skips non-root pages
  // when a trailing-slash redirect intercepts their prerender request.
  trailingSlash: false,
};

export default nextConfig;
