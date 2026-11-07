""" Sanitizes the HTML of problem statements. Statements come from course repositories, which are
untrusted, and they are shown as HTML in the problem page. Sanitizing keeps the formatting that
Asciidoctor, Markdown, and hand-written HTML produce, and removes everything that could run code,
change the page, or send data to other sites (scripts, event handlers, forms, javascript: URLs) """
import urllib.parse

import nh3

# Prefix added to every id of a statement, so its ids cannot collide with the ids of the problem
# page that JavaScript looks for, such as 'language' or 'run_button' (DOM clobbering). Asciidoctor
# ids are like '_section_title', and they become 'statement__section_title'
ID_PREFIX = 'statement_'

# The default tags of nh3 (formatting, lists, tables, images, links...) and some old ones that
# hand-written statements use. Tags not listed are removed, but their text is kept
TAGS = nh3.ALLOWED_TAGS | {'address', 'font'}

# Tags removed with all their contents, because their text is not meant to be shown (e.g. the
# <title> of a statement written as a whole HTML document), or it is code (scripts and styles,
# which could change the whole page). Inline SVG and MathML are not supported; SVG images can
# be shown with <img>
CLEAN_CONTENT_TAGS = {'head', 'math', 'noscript', 'script', 'style', 'svg', 'template',
    'textarea', 'title'}

# Attributes allowed for each tag, '*' for all tags. Event handler attributes (onclick...) are
# never allowed
ATTRIBUTES = {tag: set(names) for tag, names in nh3.ALLOWED_ATTRIBUTES.items()}
ATTRIBUTES['*'] = {'class', 'id', 'style', 'title'}
# Asciidoctor marks the language of source code blocks, e.g. <code data-lang="cpp">
ATTRIBUTES['code'] = {'data-lang'}
ATTRIBUTES['font'] = {'color'}
ATTRIBUTES['li'] = {'value'}
ATTRIBUTES['ol'] = ATTRIBUTES.get('ol', set()) | {'reversed', 'type'}
ATTRIBUTES['table'] = ATTRIBUTES.get('table', set()) | {'border', 'cellpadding', 'cellspacing'}

# CSS properties allowed in style attributes. Others, such as position, could place the statement
# over the controls of the page to deceive students
STYLE_PROPERTIES = {'background-color', 'border', 'color', 'font-family', 'font-size',
    'font-style', 'font-weight', 'height', 'line-height', 'margin', 'padding', 'text-align',
    'vertical-align', 'width'}

# Absolute URLs may only use these schemes, so javascript: and data: URLs are removed
URL_SCHEMES = {'http', 'https', 'mailto'}

def sanitize_statement(html: str, problem_url: str) -> str:
    """ Return the given statement HTML sanitized. problem_url is the URL of the problem page,
    e.g. '/problem/CI0112/hello', used to rewrite the relative URLs of the statement """
    if not html:
        return ''
    return nh3.clean(html, tags=TAGS, clean_content_tags=CLEAN_CONTENT_TAGS,
        attributes=ATTRIBUTES, filter_style_properties=STYLE_PROPERTIES, url_schemes=URL_SCHEMES,
        url_relative=lambda url: rewrite_relative_url(url, problem_url), id_prefix=ID_PREFIX)

def rewrite_relative_url(url: str, problem_url: str):
    """ Return the URL that browsers must use for the given relative URL of a statement, or None
    to remove it. Statements refer to files of their folder, e.g. 'img/diagram.svg', but the
    problem page is /problem/<course>/<problem>, where browsers would resolve that URL to
    /problem/<course>/img/diagram.svg. They are served from /problem/<course>/<problem>/files/ """
    # Links to sections of the statement point to the prefixed ids
    if url.startswith('#'):
        return f'#{ID_PREFIX}{url[1:]}'
    # URLs such as //host/path go to other sites with the scheme of the page, they are removed
    # because their scheme is not checked
    if url.startswith('//'):
        return None
    # Absolute paths (/course/CI0112) refer to pages of this site, they are kept as they are
    if url.startswith('/'):
        return url
    # Paths relative to the problem folder. urljoin resolves ./ and ../ as browsers do. A path
    # that goes out of files/ is just another URL of this site, and the files route only serves
    # images inside the problem folder anyway
    return urllib.parse.urljoin(f'{problem_url}/files/', url)
