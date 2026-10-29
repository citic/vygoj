// MathJax reads this configuration when it loads, so this script must run before MathJax.
// Asciidoctor writes stem formulas as \(...\) and \[...\] for latexmath, and \$...\$ for asciimath
window.MathJax = {
  loader: { load: ['input/asciimath'] },
  // Otherwise TeX turns \$ into $ and breaks the asciimath delimiters
  tex: { processEscapes: false },
  asciimath: { delimiters: [['\\$', '\\$']] },
  // Only typeset the statement, not the code editors
  startup: { elements: ['.problem__statement'] },
};
