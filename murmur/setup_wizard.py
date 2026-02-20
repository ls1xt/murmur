# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingImports=false, reportUnusedImport=false
"""
First-run setup wizard for murmur.

Prompts for API key (and optionally keyterms) when no API key is configured.
Shows a customtkinter GUI dialog when a display is available, falls back to
a terminal prompt otherwise.
"""

from __future__ import annotations

import os

from murmur.config import DictationConfig


def _has_display() -> bool:
    """Return True if a graphical display is available."""
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _customtkinter_available() -> bool:
    """Return True if customtkinter can be imported."""
    try:
        import customtkinter  # noqa: F401  # type: ignore[import-untyped]

        return True
    except ImportError:
        return False


def _show_gui_dialog(config: DictationConfig) -> bool:  # type: ignore[return]
    """Show the GUI setup dialog. Returns True if setup completed."""
    import customtkinter as ctk  # type: ignore[import-untyped]

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Murmur Setup")
    root.geometry("480x320")
    root.resizable(False, False)

    ctk.CTkLabel(
        root,
        text="Welcome to Murmur",
        font=ctk.CTkFont(size=20, weight="bold"),
    ).pack(pady=(24, 4))
    ctk.CTkLabel(
        root,
        text="Enter your AssemblyAI API key to get started.",
        font=ctk.CTkFont(size=13),
    ).pack(pady=(0, 16))

    ctk.CTkLabel(root, text="AssemblyAI API key *", anchor="w").pack(fill="x", padx=32)
    api_key_var = ctk.StringVar(value=config.transcriber.api_key or "")
    api_key_entry = ctk.CTkEntry(
        root,
        textvariable=api_key_var,
        placeholder_text="Paste your key here",
        show="*",
        width=416,
    )
    api_key_entry.pack(padx=32, pady=(2, 12))

    ctk.CTkLabel(
        root,
        text="Custom vocabulary (optional — comma-separated)",
        anchor="w",
    ).pack(fill="x", padx=32)
    keyterms_var = ctk.StringVar(value=", ".join(config.transcriber.keyterms))
    ctk.CTkEntry(
        root,
        textvariable=keyterms_var,
        placeholder_text="e.g. PyTorch, kubectl, Kubernetes",
        width=416,
    ).pack(padx=32, pady=(2, 20))

    result: list[bool] = [False]

    def on_save() -> None:
        key = api_key_var.get().strip()
        if not key:
            return
        config.transcriber.api_key = key
        raw_keyterms = keyterms_var.get()
        config.transcriber.keyterms = [
            t.strip() for t in raw_keyterms.split(",") if t.strip()
        ]
        config.save()
        result[0] = True
        root.destroy()

    def on_cancel() -> None:
        root.destroy()

    btn_frame = ctk.CTkFrame(root, fg_color="transparent")
    btn_frame.pack(pady=(0, 8))
    ctk.CTkButton(
        btn_frame,
        text="Cancel",
        fg_color="transparent",
        hover_color="#333",
        command=on_cancel,
        width=100,
    ).pack(side="left", padx=8)
    ctk.CTkButton(
        btn_frame,
        text="Save & Start",
        command=on_save,
        width=140,
    ).pack(side="left", padx=8)

    root.mainloop()
    return result[0]


def _prompt_terminal(config: DictationConfig) -> bool:
    """Prompt for setup in the terminal. Returns True if setup completed."""
    print("\nMurmur Setup")
    print("=" * 40)
    print("AssemblyAI API key required.")
    print("Get a free key at: https://www.assemblyai.com/\n")
    try:
        key = input("API key: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled.")
        return False
    if not key:
        print("No key entered. Setup cancelled.")
        return False
    config.transcriber.api_key = key
    try:
        keyterms_raw = input(
            "Custom vocabulary terms (optional, comma-separated, press Enter to skip): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        keyterms_raw = ""
    if keyterms_raw:
        config.transcriber.keyterms = [
            t.strip() for t in keyterms_raw.split(",") if t.strip()
        ]
    config.save()
    return True


def prompt_setup(config: DictationConfig) -> bool:
    """
    Prompt user for API key (and optionally keyterms) when not configured.

    Returns True if setup completed (API key now set), False if user cancelled
    or input was empty.

    Strategy:
    - If DISPLAY or WAYLAND_DISPLAY env var is set AND customtkinter is importable:
      show GUI dialog
    - Otherwise: fall back to terminal prompt (input())
    """
    if _has_display() and _customtkinter_available():
        return _show_gui_dialog(config)
    return _prompt_terminal(config)
