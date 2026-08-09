#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_kuwagata_revision_v2 as build  # type: ignore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pc", "mobile"), required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--voicevox-url", default="http://127.0.0.1:50021")
    parser.add_argument("--fps", type=int, default=24)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    assets, videos = build.load_assets(args.assets)

    mobile = args.mode == "mobile"
    size = build.MOBILE_SIZE if mobile else build.PC_SIZE
    label = "Mobile_720x1280" if mobile else "PC_1280x720"
    silent = args.work / f"revision_{args.mode}_silent.mp4"
    build.render_video(size, silent, assets, videos, args.fps)

    music = args.work / "music_sfx.wav"
    build.make_music(music)
    clips = build.synthesize_voice(args.work / "voice", args.voicevox_url)
    mixed = args.work / "mixed_audio.m4a"
    build.mix_audio(music, clips, mixed)

    final = args.output / f"Kuwagata_Expedition_Revised_v5_{label}.mp4"
    build.mux(silent, mixed, final)
    qa = {args.mode: build.verify_video(final, size)}
    build.make_contact_sheet(
        final,
        args.output / f"Kuwagata_Expedition_Revised_v5_{args.mode.upper()}_Contact.jpg",
        mobile,
    )
    build.make_srt(args.output / "Kuwagata_Expedition_Revised_v5_JP.srt")
    build.write_credits(args.output / "Kuwagata_Expedition_Revised_v5_Credits.txt")
    (args.output / f"Kuwagata_Expedition_Revised_v5_{args.mode.upper()}_QA.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
