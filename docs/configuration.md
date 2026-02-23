# Murmur Configuration Reference

Config is stored at `~/.config/murmur/config.json`. The daemon hot-reloads it on
the next keypress — no restart needed.

```bash
murmur config                          # view all settings
murmur config --key KEY --value VALUE  # set a value
```

See [`examples/config.json`](../examples/config.json) for a complete real-world setup.

---

## Hotkey bindings

Each binding is independent and fully configurable. Add as many as you like under
`hotkey.bindings`:

| Field | Default | Description |
|---|---|---|
| `modifiers` | `[]` | Modifier keys (e.g. `["KEY_LEFTCTRL", "KEY_LEFTMETA"]`) |
| `trigger` | — | Trigger key (e.g. `"KEY_F12"`) |
| `mode` | `"push_to_talk"` | `push_to_talk` (hold to record), `toggle` (press to start/stop) |
| `destination` | `"type"` | `type` (keystroke into active app), `clipboard` (copy to clipboard), `tmux:SESSION:WINDOW.PANE` (send to tmux pane; falls back to clipboard with a notification if the pane is unavailable) |
| `language` | `null` | Language override for this binding (e.g. `"de"`, `"en_au"`) |
| `append_enter` | `false` | Send Return keystroke after injection |
| `suppress` | `false` | Swallow the key event (prevents it reaching other apps) |

> [!TIP]
> Push-to-talk works best with dedicated keys (F-keys, mouse buttons). Using
> a letter key as a push-to-talk trigger will type that letter while held. Use
> `toggle` mode instead for modifier+letter combos.

On macOS, `KEY_LEFTALT` is automatically remapped to `KEY_LEFTMETA` (Cmd) at
load time — the same config works on both platforms.

### Hotkey advanced settings

```json
{
  "hotkey": {
    "backend": "auto",
    "evdev_device": "/dev/input/event3",
    "push_to_talk_debounce_ms": 300,
    "stop_on_keypress": true
  }
}
```

| Field | Default | Description |
|---|---|---|
| `backend` | `"auto"` | `"evdev"` (Linux), `"pynput"` (macOS), `"auto"` |
| `evdev_device` | `null` | Pin to a specific `/dev/input/eventN` device |
| `push_to_talk_debounce_ms` | `300` | Ignore key-repeat events shorter than this |
| `stop_on_keypress` | `true` | Stop toggle recording when any non-modifier key is pressed |

---

## Transcriber settings

```json
{
  "transcriber": {
    "language": "en",
    "keyterms": ["kubectl", "PyTorch"],
    "inject_partials": false,
    "reconnect_attempts": 5,
    "reconnect_delay_ms": 1000,
    "mic_device": null,
    "format_turns": true,
    "end_of_turn_confidence_threshold": 0.4,
    "min_end_of_turn_silence_when_confident": 400,
    "max_turn_silence": 1280
  }
}
```

| Field | Default | Description |
|---|---|---|
| `language` | `"en"` | Default language (overridden per-binding) |
| `keyterms` | `[]` | Words to boost in transcription accuracy |
| `inject_partials` | `false` | Stream partial transcripts as you speak (may produce corrections) |
| `reconnect_attempts` | `5` | WebSocket reconnect retries on unexpected drop |
| `reconnect_delay_ms` | `1000` | Initial delay between reconnect attempts (doubles each try) |
| `mic_device` | `null` | Mic device index or name (`murmur list-mics` to find) |
| `format_turns` | `true` | Apply punctuation and casing formatting |
| `end_of_turn_confidence_threshold` | `0.4` | AssemblyAI end-of-turn sensitivity |
| `min_end_of_turn_silence_when_confident` | `400` | Silence (ms) before committing a turn |
| `max_turn_silence` | `1280` | Max silence (ms) before forcing a turn end |

**Supported languages:** 90+ via AssemblyAI — `en`, `en_au`, `en_uk`, `en_us`,
`de`, `fr`, `es`, `it`, `pt`, `nl`, `ja`, `zh`, `ko`, `ru`, `ar`, `hi`, and
[many more](https://www.assemblyai.com/docs/speech-to-text/streaming).

If no language is set, murmur reads `$LANG`/`$LC_ALL` from your environment as a fallback.

### Selecting a microphone

```bash
murmur list-mics                                              # show all input devices with index
murmur config --key transcriber.mic_device --value 2         # select by index
murmur config --key transcriber.mic_device --value "Scarlett Solo"  # or by name
```

---

## Injector settings

```json
{
  "injector": {
    "trailing_space": true,
    "key_delay": 1,
    "inject_strategy": "clipboard"
  }
}
```

| Field | Default | Description |
|---|---|---|
| `trailing_space` | `true` | Append a space after each injected turn |
| `key_delay` | `1` | Milliseconds between keystrokes (increase for slow apps) |
| `inject_strategy` | `"clipboard"` | `"ydotool"`, `"clipboard"`, or `"clipboard-fallback"` |

---

## Feedback settings

```json
{
  "feedback": {
    "audio_enabled": true,
    "start_hz": 440.0,
    "stop_hz": 880.0,
    "start_duration_ms": 100,
    "stop_duration_ms": 100,
    "amplitude": 0.3
  }
}
```

| Field | Default | Description |
|---|---|---|
| `audio_enabled` | `true` | Enable start/stop beeps |
| `start_hz` | `440.0` | Start beep pitch in Hz |
| `stop_hz` | `880.0` | Stop beep pitch in Hz |
| `start_duration_ms` | `100` | Start beep duration; set to `0` to disable |
| `stop_duration_ms` | `100` | Stop beep duration; set to `0` to disable |
| `amplitude` | `0.3` | Beep volume (0.0–1.0) |

---

## Environment variables

| Variable | Description |
|---|---|
| `ASSEMBLYAI_API_KEY` | AssemblyAI API key (overrides config file) |
| `MURMUR_LOG_LEVEL` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `MURMUR_MIC_DEVICE` | Microphone device index or name |
| `MURMUR_NOTIFY_LEVEL` | Desktop notification level (`off`, `errors`, `verbose`) |
| `MURMUR_INJECT_STRATEGY` | Injection backend (`ydotool`, `clipboard`, `clipboard-fallback`) |
| `DICTATION_HOTKEY_BACKEND` | Hotkey backend override (`evdev`, `pynput`, `auto`) |
| `DICTATION_INJECTOR_BACKEND` | Injector backend override |

---

## Common config snippets

```bash
murmur config --key transcriber.api_key --value K                          # set API key
murmur config --key notify.level --value verbose                           # change notify level
murmur config --key transcriber.keyterms --value "PyTorch,kubectl"         # custom vocab
murmur config --key feedback.start_duration_ms --value 0                   # disable start beep
murmur config --key feedback.stop_duration_ms --value 200                  # longer stop beep
murmur config --key feedback.amplitude --value 0.1                         # quieter beeps
murmur config --key feedback.start_hz --value 440                          # start beep pitch (Hz)
murmur config --key feedback.stop_hz --value 880                           # stop beep pitch (Hz)
murmur config --key transcriber.mic_device --value 2                       # select mic by index
murmur config --key transcriber.reconnect_attempts --value 10              # WebSocket retry count
murmur config --key transcriber.reconnect_delay_ms --value 2000            # initial retry delay
murmur config --key injector.trailing_space --value false                  # no trailing space
murmur config --key injector.key_delay --value 5                           # ms between keystrokes
murmur config --key tray.enabled --value false                             # disable tray icon
murmur config --key log_level --value DEBUG                                # verbose logging
```
