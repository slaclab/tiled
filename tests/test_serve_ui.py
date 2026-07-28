import json
import re

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.status import HTTP_200_OK

from tiled.server.app import build_app

# Stand-ins for the index.html shipped by web-frontend's build, for one
# vendored by a third party that knows nothing of Tiled's template variables,
# and for one built by a web-frontend that has drifted out of sync.
TILED_INDEX_HTML = (
    "<html><head>"
    '<base href="{{ tiled_runtime_base }}" />'
    '<script type="application/json" id="tiled-runtime-config">'
    "{{ tiled_runtime_config }}</script>"
    '</head><body><script src="./assets/app.js"></script></body></html>'
)
VENDORED_INDEX_HTML = (
    '<html><head></head><body><script src="./assets/app.js"></script></body></html>'
)
DRIFTED_INDEX_HTML = (
    '<html><head><base href="{{ tiled_runtime_base }}" /></head><body></body></html>'
)


@pytest.fixture
def serve_ui(tmp_path, monkeypatch):
    """Serve `index_html` as the UI distribution and report what a browser gets."""
    (tmp_path / "ui").mkdir()
    (tmp_path / "templates").mkdir()
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "default_ui_settings.yml").write_text(
        "api_url: /api/v1\nspecs: []\nstructure_families: {}\n"
    )
    monkeypatch.setattr("tiled.server.app.SHARE_TILED_PATH", tmp_path)
    monkeypatch.delenv("TILED_UI_SETTINGS", raising=False)

    async def serve(
        index_html=TILED_INDEX_HTML,
        *,
        configured_root_path="",
        request_root_path="",
        path="/ui/browse/deep/path",
    ):
        (tmp_path / "ui" / "index.html").write_text(index_html)
        app = build_app({}, server_settings={"root_path": configured_root_path})
        transport = ASGITransport(app=app, root_path=request_root_path)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            index = await client.get(path)
            settings = await client.get("/tiled-ui-settings")
        assert index.status_code == HTTP_200_OK
        assert settings.status_code == HTTP_200_OK
        return index.text, settings.json()

    return serve


def base_href(html):
    (href,) = re.findall(r'<base href="([^"]*)"', html)
    return href


def runtime_config(html):
    (payload,) = re.findall(
        r'id="tiled-runtime-config">(.*?)</script>', html, re.DOTALL
    )
    return json.loads(payload)


@pytest.mark.parametrize(
    "request_root_path,configured_root_path,expected",
    [
        pytest.param("", "", "", id="unmounted"),
        pytest.param("/", "", "", id="trailing-slash-stripped"),
        pytest.param("/tenant/ui/tiled", "", "/tenant/ui/tiled", id="from-request"),
        pytest.param("", "/configured", "/configured", id="from-server-settings"),
        pytest.param("/mounted", "/configured", "/mounted", id="request-wins"),
    ],
)
@pytest.mark.asyncio
async def test_ui_uses_runtime_root_path(
    serve_ui, request_root_path, configured_root_path, expected
):
    html, settings = await serve_ui(
        configured_root_path=configured_root_path, request_root_path=request_root_path
    )

    assert base_href(html) == f"{expected}/ui/"
    assert runtime_config(html) == {
        "root_path": expected,
        "api_url": f"{expected}/api/v1",
    }
    assert settings["api_url"] == f"{expected}/api/v1"
    # Asset URLs stay relative, to be resolved against <base>.
    assert 'src="./assets/app.js"' in html


@pytest.mark.asyncio
async def test_vendored_ui_is_served_verbatim(serve_ui):
    html, _ = await serve_ui(
        VENDORED_INDEX_HTML,
        configured_root_path="/tiled",
        request_root_path="/tiled",
        path="/ui/",
    )

    assert html == VENDORED_INDEX_HTML


@pytest.mark.asyncio
async def test_ui_declaring_only_some_template_variables_is_rejected(serve_ui):
    with pytest.raises(RuntimeError, match="drifted out of sync"):
        await serve_ui(DRIFTED_INDEX_HTML)
