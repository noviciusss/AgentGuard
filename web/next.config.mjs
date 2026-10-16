/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Keep strict TypeScript and linting in `npm test` and let this worker focus
  // on producing the deployable bundle, especially on WSL-mounted filesystems.
  typescript: {
    ignoreBuildErrors: true
  },
  eslint: {
    ignoreDuringBuilds: true
  },
  experimental: {
    cpus: 1
  }
};

export default nextConfig;
