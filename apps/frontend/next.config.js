/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      {
        source: "/receipts",
        destination: "/invoices",
        permanent: false,
      },
      {
        source: "/receipts/:path*",
        destination: "/invoices/:path*",
        permanent: false,
      },
    ];
  },
};

module.exports = nextConfig;