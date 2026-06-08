# Output provenance (Phase 3 M2)

Every audio file this tool generates carries a recoverable provenance marker in
its container metadata, identifying it as AI voice-converted by this tool. This
is a non-negotiable safeguard (`CLAUDE.md`) — there is no toggle.

## Marker

The documented, stable token (`PROVENANCE_MARKER`) is:

```
AI voice-converted by VoiceBuilder
```

It is embedded as literal UTF-8 inside standard container tags, alongside the
app version:

| Tag (logical) | WAV (RIFF INFO) | FLAC (Vorbis) | Value |
|---|---|---|---|
| comment | `ICMT` | `COMMENT` | `AI voice-converted by VoiceBuilder v<version>. Synthetic audio…` |
| encoded_by | `ISFT` | `ENCODED_BY` | `VoiceBuilder <version>` |

`<version>` is `voiceconv.__version__`.

## Where it's written

All generated files pass through a single `AudioEncoder.encode()` chokepoint:

- **`FfmpegEncoder`** (production, `audio/_codec.py`): injects
  `ffmpeg_metadata_args()` (`-metadata comment=… -metadata encoded_by=…`). ffmpeg
  writes a RIFF `LIST/INFO` chunk for WAV and Vorbis comments for FLAC.
- **`StdlibWavEncoder`** (ffmpeg-free fallback, `services/_audio_encoder.py`):
  appends a `LIST/INFO` chunk via `append_info_chunk()`; audio frames unchanged.

The Preview **Export** action is a byte copy (`shutil.copy2`), so provenance
written at encode time survives export with no extra work.

## Verifying

`audio/_provenance.file_has_provenance(path)` returns whether a file carries the
marker. Because the marker is stored verbatim, the check is a byte scan and works
for WAV and FLAC without ffmpeg/ffprobe.

## Limitation

Container metadata can be **stripped by re-encoding** the file in another tool.
This metadata marker is the guaranteed baseline; a durable signal-domain
watermark is evaluated separately in Phase 3 M4. We do not overclaim: provenance
is asserted at the metadata layer, not against an adversary who re-encodes.

## Tests

`tests/audio/test_provenance.py` — stdlib encoder embeds the marker, output is
still a valid WAV with identical frames, a plain WAV reports *no* provenance,
provenance survives an export copy; FfmpegEncoder WAV/FLAC cases guarded by
ffmpeg availability.
