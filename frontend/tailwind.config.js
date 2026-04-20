/** @type {import('tailwindcss').Config} */
// 工作台视觉系统 design tokens：色板 / 字体 / 阴影 / 圆角 / 缓动函数
// 仅用于 MainBoard 与未来新页面；既有 style.css / fixed-rules.css 保持原状
export default {
  content: [
    './index.html',
    './src/**/*.{vue,ts,tsx,js}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '"Noto Sans SC"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Consolas', 'monospace'],
      },
      colors: {
        canvas: '#F7F8FA',
        card: '#FFFFFF',
        subtle: '#F1F3F6',
        ink: {
          900: '#0F172A',
          700: '#1F2937',
          500: '#64748B',
          300: '#CBD5E1',
        },
        line: '#E5E7EB',
        accent: {
          DEFAULT: '#2563EB',
          soft: '#EFF4FF',
          ink: '#1D4ED8',
        },
        success: { DEFAULT: '#10B981', soft: '#ECFDF5' },
        warning: { DEFAULT: '#F59E0B', soft: '#FFFBEB' },
        danger: { DEFAULT: '#EF4444', soft: '#FEF2F2' },
      },
      boxShadow: {
        'card-1': '0 1px 2px rgba(15, 23, 42, .04)',
        'card-2': '0 1px 2px rgba(15, 23, 42, .04), 0 8px 24px rgba(15, 23, 42, .06)',
      },
      borderRadius: {
        field: '6px',
        card: '12px',
      },
      transitionTimingFunction: {
        premium: 'cubic-bezier(.2, 0, 0, 1)',
      },
    },
  },
  // 关闭 Preflight 重置：避免与 Element Plus / 既有 4000+ 行 CSS 冲突
  // 我们只需要 utility 类，不需要 Tailwind 重置浏览器默认样式
  corePlugins: {
    preflight: false,
  },
  plugins: [],
}
