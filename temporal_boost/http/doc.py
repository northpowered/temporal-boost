import pdoc
from pathlib import Path

from aiohttp import web


def _build_html_doc(*modules: Path | str) -> str:
    """
    Uses pdoc to build html documentation
    for *modules*`

    Returns:
        str: HTML static doc page
    """

    html: str = pdoc.pdoc(modules)
    return html


async def html_doc_handler(request):

    # pdoc.html("temporal_boost/core.py")

    modules = ["temporal_boost"]
    context = pdoc.Context()

    modules = [pdoc.Module(mod, context=context) for mod in modules]
    pdoc.link_inheritance(context)

    def recursive_htmls(mod):
        yield mod.name, mod.html()
        for submod in mod.submodules():
            yield from recursive_htmls(submod)

    for mod in modules:
        for module_name, html in recursive_htmls(mod):
            ...  # Process
    return web.Response(text=pdoc.html("temporal_boost"), content_type="text/html")
