from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

VIDEO_ID = sys.argv[1] if len(sys.argv) > 1 else "wWYOgTFZ-FY"
START = int(sys.argv[2]) if len(sys.argv) > 2 else 0
DURATION = int(sys.argv[3]) if len(sys.argv) > 3 else 30
OUT = Path(sys.argv[4] if len(sys.argv) > 4 else "youtube_browser_capture")
OUT.mkdir(parents=True, exist_ok=True)


async def main() -> None:
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
        )
        page = await context.new_page()
        errors: list[str] = []
        page.on("console", lambda msg: errors.append(f"console:{msg.type}:{msg.text}"))
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))
        url = (
            f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}"
            f"?autoplay=1&mute=1&controls=0&rel=0&modestbranding=1&playsinline=1&start={START}"
        )
        print("OPEN", url, flush=True)
        response = await page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        print("STATUS", response.status if response else None, flush=True)
        await page.wait_for_timeout(10_000)
        await page.screenshot(path=str(OUT / "initial.png"), full_page=True)
        title = await page.title()
        body = (await page.locator("body").inner_text())[:4000]
        print("TITLE", title, flush=True)
        print("BODY", body[:1000], flush=True)

        # Start playback through the player API or a synthetic click.
        try:
            await page.mouse.click(640, 360)
        except Exception as exc:
            errors.append(f"click:{exc}")
        await page.wait_for_timeout(2_000)
        try:
            result = await page.evaluate(
                """
                () => {
                  const v = document.querySelector('video');
                  if (!v) return {found:false};
                  v.muted = true;
                  v.currentTime = Math.max(v.currentTime || 0, %d);
                  const p = v.play();
                  return {found:true, paused:v.paused, readyState:v.readyState, duration:v.duration};
                }
                """ % START
            )
            print("VIDEO", json.dumps(result), flush=True)
        except Exception as exc:
            errors.append(f"video-eval:{exc}")
        await page.wait_for_timeout(DURATION * 1000)
        try:
            state = await page.evaluate(
                """
                () => {
                  const v = document.querySelector('video');
                  return v ? {currentTime:v.currentTime, paused:v.paused, readyState:v.readyState, duration:v.duration} : {found:false};
                }
                """
            )
        except Exception as exc:
            state = {"error": str(exc)}
        await page.screenshot(path=str(OUT / "final.png"), full_page=True)
        video_obj = page.video
        await context.close()
        if video_obj:
            saved = await video_obj.path()
            target = OUT / "capture.webm"
            Path(saved).replace(target)
            print("CAPTURE", target, target.stat().st_size, flush=True)
        await browser.close()
        (OUT / "diagnostics.json").write_text(
            json.dumps({"url": url, "title": title, "body": body, "state": state, "errors": errors}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    asyncio.run(main())
