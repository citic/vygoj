module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  extends: [
    'airbnb',
  ],
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
  },
  rules: {
    // Allow modifying properties through function's params
    'no-param-reassign': ["error", { "props": false }],
    // Allow defensive programming
    'no-console': "off",
    // Allow .js extension in modules
    "import/extensions": ["error", "ignorePackages"],
    // Allow modules imported from a CDN URL
    "import/no-unresolved": ["error", { "ignore": ["^https://"] }],
    // Allow _id MongoDB identifier starting with underscore
    "no-underscore-dangle": ["error", { "allow": ["_id"] }],
    // Allow many small clases in the same file
    "max-classes-per-file": ["error", 100],
  },
  settings: {
    react: {
      version: '999.999.999',
    },
  },
};
