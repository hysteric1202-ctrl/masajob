from __future__ import annotations

import asyncio
import contextlib
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.async_api import async_playwright

VIDEO_ID = sys.argv[1] if len(sys.argv) > 1 else "wWYOgTFZ-FY"
START = int(sys.argv[2]) if len(sys.argv) > 2 else 0
DURATION = int(sys.argv[3]) if len(sys.argv) > 3 else 35
OUT = Path(sys.argv[4] if len(sys.argv) > 4 else "youtube_iframe_capture")
OUT.mkdir(parents=True, exist_ok=True)

HTML = f"""<!doctype html>
<html lang='ja'>
<head>
<meta charset='utf-8'>
<meta name='referrer' content='strict-origin-when-cross-origin'>
<style>
html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#000}}
iframe{{position:absolute;inset:0;width:100%;height:100%;border:0}}
</style>
</head>
<body>
<iframe id='yt' allow='autoplay; encrypted-media; picture-in-picture' allowfullscreen
 src='https://www.youtube-nocookie.com/embed/{VIDEO_ID}?autoplay=1&mute=1&controls=0&rel=0&modestbranding=1&playsinline=1&start={START}&enablejsapi=1&origin=http://127.0.0.1:8765'></iframe>
</body></html>"""
(OUT / "index.html").write_text(HTML, encoding="utf-8")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        pass


def start_server() -> tuple[socketserver.TCPServer, threading.Thread]:
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(OUT), **kwargs)
    server = socketserver.TCPServer(("127.0.0.1", 8765), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


async def main() -> None:
    server, _thread = start_server()
    diagnostics: dict[str, object] = {"video_id": VIDEO_ID, "start": START, "duration": DURATION}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--autoplay-policy=no-user-gesture-required",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                record_video_dir=str(OUT),
                record_video_size={"width": 1280, "height": 720},
                locale="ja-JP",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
                ),
                extra_http_headers={"Accept-Language": "ja,en-US;q=0.9,en;q=0.8"},
            )
            page = await context.new_page()
            console: list[str] = []
            page.on("console", lambda msg: console.append(f"{msg.type}:{msg.text}"))
            page.on("pageerror", lambda exc: console.append(f"pageerror:{exc}"))
            response = await page.goto("http://127.0.0.1:8765/index.html", wait_until="domcontentloaded", timeout=120_000)
            diagnostics["wrapper_status"] = response.status if response else None
            await page.wait_for_timeout(12_000)
            await page.screenshot(path=str(OUT / "initial.png"), full_page=True)

            yt_frame = next((f for f in page.frames if "youtube" in f.url), None)
            diagnostics["frame_urls"] = [f.url for f in page.frames]
            diagnostics["yt_frame_found"] = bool(yt_frame)
            frame_text = ""
            state: object = None
            if yt_frame:
                try:
                    frame_text = (await yt_frame.locator("body").inner_text())[:3000]
                except Exception as exc:
                    frame_text = f"body error: {exc}"
                # Click central play area, then operate video element when present.
                with contextlib.suppress(Exception):
                    await page.mouse.click(640, 360)
                await page.wait_for_timeout(2_000)
                try:
                    state = await yt_frame.evaluate(
                        f"""
                        () => {{
                          const v = document.querySelector('video');
                          if (!v) return {{found:false}};
                          v.muted = true;
                          if (Number.isFinite(v.duration) && {START} < v.duration) v.currentTime = {START};
                          v.play().catch(()=>{{}});
                          return {{found:true, currentTime:v.currentTime, paused:v.paused, readyState:v.readyState, duration:v.duration}};
                        }}
                        """
                    )
                except Exception as exc:
                    state = {"error": str(exc)}
            diagnostics["frame_text"] = frame_text
            diagnostics["initial_state"] = state
            await page.wait_for_timeout(DURATION * 1000)
            if yt_frame:
                try:
                    state = await yt_frame.evaluate(
                        """
                        () => {
                          const v = document.querySelector('video');
                          return v ? {found:true,currentTime:v.currentTime,paused:v.paused,readyState:v.readyState,duration:v.duration} : {found:false};
                        }
                        """
                    )
                except Exception as exc:
                    state = {"error": str(exc)}
            diagnostics["final_state"] = state
            diagnostics["console"] = console
            await page.screenshot(path=str(OUT / "final.png"), full_page=True)
            video_obj = page.video
            await context.close()
            if video_obj:
                saved = await video_obj.path()
                target = OUT / "capture.webm"
                Path(saved).replace(target)
                diagnostics["capture_size"] = target.stat().st_size
            await browser.close()
    finally:
        server.shutdown()
        server.server_close()
    (OUT / "diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
