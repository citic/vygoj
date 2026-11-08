""" Sanitizes the HTML written by course authors, such as problem statements and, in the future,
content pages. Course repositories are untrusted, and their HTML is shown inside the pages of the
site. Sanitizing keeps the formatting that Asciidoctor, Markdown, and hand-written HTML produce,
and the videos of the content folder, and removes everything that could run code in the site,
change the page, or send data to other sites (scripts, event handlers, forms, javascript: URLs) """
import urllib.parse

import nh3

# Prefix added to every id of the content, so its ids cannot collide with the ids of the page
# that JavaScript looks for, such as 'language' or 'run_button' (DOM clobbering). Asciidoctor
# ids are like '_section_title', and they become 'content__section_title'
ID_PREFIX = 'content_'

# The default tags of nh3 (formatting, lists, tables, images, links...), some old ones that
# hand-written statements use, and the ones of videos. Tags not listed are removed, but their text
# is kept
TAGS = nh3.ALLOWED_TAGS | {'address', 'font', 'source', 'track', 'video'}

# Tags removed with all their contents, because their text is not meant to be shown (e.g. the
# <title> of a statement written as a whole HTML document), or it is code (scripts and styles,
# which could change the whole page). Frames are not supported, so videos of video sites (e.g.
# video::id[youtube]) are removed. Inline SVG and MathML are not supported either; SVG images can
# be shown with <img>
CLEAN_CONTENT_TAGS = {'head', 'iframe', 'math', 'noscript', 'script', 'style', 'svg', 'template',
    'textarea', 'title'}

# Attributes allowed for each tag, '*' for all tags. Event handler attributes (onclick...) are
# never allowed. The URLs of videos are also checked by check_video_url()
ATTRIBUTES = {tag: set(names) for tag, names in nh3.ALLOWED_ATTRIBUTES.items()}
ATTRIBUTES['*'] = {'class', 'id', 'style', 'title'}
# Asciidoctor marks the language of source code blocks, e.g. <code data-lang="cpp">
ATTRIBUTES['code'] = {'data-lang'}
ATTRIBUTES['font'] = {'color'}
ATTRIBUTES['li'] = {'value'}
ATTRIBUTES['ol'] = ATTRIBUTES.get('ol', set()) | {'reversed', 'type'}
ATTRIBUTES['source'] = {'src', 'type'}
ATTRIBUTES['table'] = ATTRIBUTES.get('table', set()) | {'border', 'cellpadding', 'cellspacing'}
# Subtitles of videos
ATTRIBUTES['track'] = {'default', 'kind', 'label', 'src', 'srclang'}
ATTRIBUTES['video'] = {'height', 'loop', 'muted', 'playsinline', 'poster', 'src', 'width'}

# Attributes that the sanitizer sets, replacing the ones of the author. Videos always show their
# controls, and do not download the whole file before playing. Autoplay is not allowed
SET_ATTRIBUTES = {'video': {'controls': '', 'preload': 'metadata'}}

# CSS properties allowed in style attributes. Others, such as position, could place the content
# over the controls of the page to deceive students
STYLE_PROPERTIES = {'background-color', 'border', 'color', 'font-family', 'font-size',
    'font-style', 'font-weight', 'height', 'line-height', 'margin', 'padding', 'text-align',
    'vertical-align', 'width'}

# Absolute URLs may only use these schemes, so javascript: and data: URLs are removed
URL_SCHEMES = {'http', 'https', 'mailto'}

def sanitize_html(html: str, files_url: str) -> str:
    """ Return the given HTML sanitized. files_url is the URL where the files of the content are
    served, e.g. '/problem/CI0112/hello/files/', to rewrite the relative URLs of the content """
    if not html:
        return ''
    return nh3.clean(html, tags=TAGS, clean_content_tags=CLEAN_CONTENT_TAGS,
        attributes=ATTRIBUTES, set_tag_attribute_values=SET_ATTRIBUTES,
        attribute_filter=check_video_url, filter_style_properties=STYLE_PROPERTIES,
        url_schemes=URL_SCHEMES, url_relative=lambda url: rewrite_relative_url(url, files_url),
        id_prefix=ID_PREFIX)

def check_video_url(tag: str, attribute: str, value: str):
    """ Return the value of the given attribute, or None to remove it if it is the URL of a video
    of another site. Only the files of the content folder (relative URLs) may be played, as
    images, because the CSP of the pages allows media of this site only. nh3 calls this function
    before rewriting relative URLs """
    if tag in ('video', 'source', 'track') and attribute in ('src', 'poster'):
        is_absolute = bool(urllib.parse.urlsplit(value.strip()).scheme) or value.startswith('//')
        return None if is_absolute else value
    return value

def rewrite_relative_url(url: str, files_url: str):
    """ Return the URL that browsers must use for the given relative URL of the content, or None
    to remove it. Contents refer to files of their folder, e.g. 'img/diagram.svg', but problem
    pages are /problem/<course>/<problem>, where browsers would resolve that URL to
    /problem/<course>/img/diagram.svg. They are served from files_url instead """
    # Links to sections of the content point to the prefixed ids
    if url.startswith('#'):
        return f'#{ID_PREFIX}{url[1:]}'
    # URLs such as //host/path go to other sites with the scheme of the page, they are removed
    # because their scheme is not checked
    if url.startswith('//'):
        return None
    # Absolute paths (/course/CI0112) refer to pages of this site, they are kept as they are
    if url.startswith('/'):
        return url
    # Paths relative to the content folder. urljoin resolves ./ and ../ as browsers do. A path
    # that goes out of files_url is just another URL of this site, and the files route only
    # serves images and videos inside the content folder anyway
    return urllib.parse.urljoin(files_url, url)
