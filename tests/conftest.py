# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import pytest


@pytest.fixture
def sample_article_html() -> str:
    return '''
    <html><body>
    <div id="js_content">
        <p>First paragraph</p>
        <p><img data-src="https://mmbiz.qpic.cn/image1.jpg" /></p>
        <p>Second paragraph</p>
        <p><img data-src="https://mmbiz.qpic.cn/image2.jpg" /></p>
    </div>
    </body></html>
    '''


@pytest.fixture
def sample_rich_media_html() -> str:
    return '''
    <html><body>
    <div class="rich_media_content" id="js_content">
        <section>Article content here</section>
        <p><img data-src="https://mmbiz.qpic.cn/pic1.png" /></p>
    </div>
    </body></html>
    '''


@pytest.fixture
def sample_empty_html() -> str:
    return '<html><body><div>No content here</div></body></html>'


@pytest.fixture
def sample_full_article_html() -> str:
    """Article HTML with meta tags for title/author/publish_time extraction."""
    return '''
    <html><head>
    <meta property="og:title" content="Test Article Title" />
    <meta property="og:article:author" content="Test Author" />
    </head><body>
    <script>var publish_time = "1700000000"</script>
    <div id="js_content">
        <p>Content paragraph</p>
        <p><img data-src="https://mmbiz.qpic.cn/img1.jpg" /></p>
    </div>
    </body></html>
    '''
