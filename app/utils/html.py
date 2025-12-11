import html


def html_escape(s: str | None) -> str:
    """安全转义 HTML 文本，避免 XSS。"""
    if s is None:
        return ""
    return html.escape(str(s), quote=True)

