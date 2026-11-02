"""macOS stub for the Windows-only winsound module."""
import subprocess

def Beep(frequency=1000, duration=400):
    """Play a system sound as a stand-in for winsound.Beep on macOS."""
    try:
        subprocess.run(
            ["afplay", "/System/Library/Sounds/Ping.aiff"],
            timeout=1,
            capture_output=True,
        )
    except Exception:
        print("\a", end="", flush=True)  # terminal bell fallback
