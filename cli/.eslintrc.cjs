module.exports = {
  root: true,
  env: {
    browser: false,
    es2021: true,
    node: true,
  },
  extends: [
    'airbnb-typescript',
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 12,
    sourceType: 'module',
    project: './tsconfig.json',
  },
  plugins: [
    '@typescript-eslint',
  ],
  rules: {
    // Allow modifying properties through function's params
    'no-param-reassign': ["error", { "props": false }],
    // Allow defensive programming
    'no-console': "off",
    // Allow .js extension in modules
    "import/extensions": ["error", "ignorePackages"],
    // Allow _id MongoDB identifier starting with underscore
    "no-underscore-dangle": ["error", { "allow": ["_id"] }],
  },
  settings: {
    react: {
      version: '999.999.999',
    },
  },
};
