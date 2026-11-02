"""
run.py – Launch driver_safety.py on macOS without modifying it.
Injects stub values for the Twilio variables that are commented out
in the original script, so the app starts cleanly without SMS support.
"""
import builtins

# Provide the Twilio globals that driver_safety.py expects
# (they are commented out in the original file)
builtins.TWILIO_SID   = ""
builtins.TWILIO_TOKEN = ""
builtins.TWILIO_FROM  = ""
builtins.ALERT_TO     = "(not configured)"

import driver_safety
driver_safety.main()
