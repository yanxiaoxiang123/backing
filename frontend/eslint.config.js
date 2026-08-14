import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'
import prettier from 'eslint-config-prettier'

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'node_modules'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    plugins: {
      'react-hooks': reactHooks
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // 存量代码大量使用 any（API 响应等）；先降为 warn 暴露问题，
      // 后续逐步收紧。unused-vars 保持 error（阻断 CI）。
      '@typescript-eslint/no-explicit-any': 'warn'
    }
  },
  prettier
)
