#!/usr/bin/env python3
"""سكربت عامل للتفريغ الصوتي بمحرك faster-whisper في بيئة منفصلة.
يُستدعى كعملية فرعية (subprocess) ويخرج نتيجته كـ JSON على stdout."""
import argparse
import json
import sys

def main():
    parser = argparse.ArgumentParser(description="Zajel Media Transcribe Worker")
    parser.add_argument("audio_path", help="Path to audio file")
    parser.add_argument("--lang", default=None, help="Language code (e.g. ar, en)")
    parser.add_argument("--model", default="small", help="Whisper model name (tiny, base, small, medium, large)")
    parser.add_argument("--compute_type", default="int8", help="Compute type (default: int8)")
    args = parser.parse_args()

    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        sys.stderr.write(f"faster-whisper is not installed: {e}\n")
        sys.exit(2)

    try:
        model = WhisperModel(args.model, compute_type=args.compute_type)
        kwargs = {"vad_filter": True}
        if args.lang:
            kwargs["language"] = args.lang

        segments, info = model.transcribe(args.audio_path, **kwargs)

        seg_out = []
        text_parts = []
        for s in segments:
            txt = s.text.strip()
            seg_out.append({
                "start": round(s.start, 2),
                "end": round(s.end, 2),
                "text": txt
            })
            if txt:
                text_parts.append(txt)

        result = {
            "language": getattr(info, "language", args.lang or "unknown"),
            "duration": round(getattr(info, "duration", 0.0), 2),
            "segments": seg_out,
            "text": " ".join(text_parts)
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)
    except Exception as exc:
        sys.stderr.write(f"Transcribe error: {exc}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
