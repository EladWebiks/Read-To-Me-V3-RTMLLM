import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'
import prettier from 'eslint-plugin-prettier'
import prettierConfig from 'eslint-config-prettier'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    plugins: { prettier },
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      ...prettierConfig.rules,
      'prettier/prettier': 'error',
      'max-lines': ['error', { max: 110, skipBlankLines: false, skipComments: false }],
      'max-lines-per-function': [
        'error',
        { max: 60, skipBlankLines: true, skipComments: true },
      ],
      'max-depth': ['error', 3],
      'max-statements': ['warn', 20],
    },
  },
  {
    files: ['src/**/*.{test,spec}.{ts,tsx}', 'src/**/test-setup.ts'],
    rules: {
      'max-lines': 'off',
      'max-lines-per-function': 'off',
      'max-depth': 'off',
      'max-statements': 'off',
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    files: ['src/**/index.ts'],
    rules: { 'max-lines': 'off' },
  },
])
