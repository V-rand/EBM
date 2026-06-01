import pytest


@pytest.mark.asyncio
async def test_web_read_pdf_uses_local_fallback_without_mineru_token(monkeypatch):
    monkeypatch.delenv("MINERU_API_TOKEN", raising=False)
    monkeypatch.delenv("MINERU_API_KEY", raising=False)

    from agent_os.tools import web

    monkeypatch.setattr(web, "_mineru", lambda: None)
    monkeypatch.setattr(web, "_read_provider_order", lambda: [])
    monkeypatch.setattr(web, "_extract_pdf_markdown_from_url", lambda url, timeout_seconds=30.0: "PDF body")

    result = await web.handle_web_read("https://example.com/case.pdf")

    assert result.success
    assert result.data["content"] == "PDF body"
    assert result.data["parser"] == "pymupdf4llm"


@pytest.mark.asyncio
async def test_web_read_pdf_downloads_and_parses_remote_pdf(tmp_path, monkeypatch):
    import functools
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    import fitz

    monkeypatch.setattr("agent_os.tools.web._mineru", lambda: None)
    monkeypatch.setattr("agent_os.tools.web._read_provider_order", lambda: [])

    pdf_path = tmp_path / "case.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Remote PDF Evidence 2026")
    doc.save(pdf_path)
    doc.close()

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        from agent_os.tools.web import handle_web_read

        result = await handle_web_read(f"http://127.0.0.1:{server.server_port}/case.pdf")

        assert result.success
        assert "Remote PDF Evidence 2026" in result.data["content"]
        assert result.data["parser"] == "pymupdf4llm"
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_web_read_pdf_falls_through_to_firecrawl_after_mineru_and_local_pdf_fail(monkeypatch):
    from agent_os.tools import web
    from agent_os.tools.registry import ToolResult

    class Mineru:
        pass

    monkeypatch.setattr(web, "_mineru", lambda: Mineru())
    monkeypatch.setattr(web, "_exec_mineru", lambda mc, url: _async_result(ToolResult.fail("mineru failed")))
    monkeypatch.setattr(web, "_extract_pdf_markdown_from_url", _raise_pdf_error)
    monkeypatch.setattr(web, "_read_provider_order", lambda: ["firecrawl"])
    monkeypatch.setattr(web, "_try_firecrawl", lambda url: _async_result({
        "status": "success",
        "content": "Firecrawl PDF markdown",
        "parser": "firecrawl",
    }))

    result = await web.handle_web_read("https://example.com/case.pdf")

    assert result.success
    assert result.data["content"] == "Firecrawl PDF markdown"
    assert result.data["parser"] == "firecrawl"


async def _async_result(value):
    return value


def _raise_pdf_error(*args, **kwargs):
    raise RuntimeError("local pdf parser failed")
