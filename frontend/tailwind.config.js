/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{html,ts}"
  ],
  theme: {
    extend: {
      colors: {
        nexus: {
          bg: '#0f172a', /* slate-950 */
          sidebar: '#1e293b', /* slate-800 */
          hover: '#334155', /* slate-700 */
          active: '#475569', /* slate-600 */
          text: '#f1f5f9', /* slate-100 */
          dim: '#94a3b8', /* slate-400 */
          accent: '#6366f1' /* indigo-500 */
        }
      },
      borderRadius: {
        'nexus': '1.75rem',
      }
    }
  },
  plugins: [
    require('@tailwindcss/typography'),
  ]
};
