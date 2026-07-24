import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'

export default tseslint.config(
  { ignores: ['dist', 'node_modules'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    plugins: { 'react-hooks': reactHooks },
    rules: { ...reactHooks.configs.recommended.rules },
  },
  {
    // Vitest's own docs recommend this triple-slash reference in vite.config.ts
    // to augment Vite's config type with the `test` field.
    files: ['vite.config.ts'],
    rules: { '@typescript-eslint/triple-slash-reference': 'off' },
  },
)
