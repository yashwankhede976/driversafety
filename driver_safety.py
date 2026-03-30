"""
Driver Safety App  (with Twilio SMS Alert)
==========================================
Timeline:
  3 sec  closed eyes  →  continuous beep alarm
  10 sec closed eyes  →  SMS sent to ALERT_TO number
  Eyes open           →  alarm stops, SMS flag resets

Controls:  Q / ESC to quit
"""

import cv2
import time
import threading
import winsound
import os
from twilio.rest import Client

# ─────────────────────────────────────────────────────────────
#  Twilio credentials  (keep these private – don't share code)
# ─────────────────────────────────────────────────────────────
#TWILIO_SID   = "*****************" #your twlio key 
#TWILIO_TOKEN = "********************"  #your twlio key 
#TWILIO_FROM  = "+125*******"     # your Twilio phone number
#ALERT_TO     = "+91**********"    # your verified mobile number


# ─────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────
ALARM_SECONDS   = 3     # beep alarm starts after this many seconds
SMS_SECONDS     = 5     # SMS sent after this many seconds
BEEP_FREQ       = 1000  # Hz
BEEP_DURATION   = 400   # ms per beep
BEEP_PAUSE      = 100   # ms between beeps
MIN_EYE_AREA    = 300   # px² – ignore tiny false detections

# ─────────────────────────────────────────────────────────────
#  Load Haar cascades bundled with OpenCV
# ─────────────────────────────────────────────────────────────
_DATA          = os.path.join(os.path.dirname(cv2.__file__), "data")
FACE_CASCADE   = cv2.CascadeClassifier(os.path.join(_DATA, "haarcascade_frontalface_default.xml"))
EYE_CASCADE    = cv2.CascadeClassifier(os.path.join(_DATA, "haarcascade_eye.xml"))

if FACE_CASCADE.empty() or EYE_CASCADE.empty():
    raise RuntimeError("Cascade files not found. Check OpenCV installation.")


# ─────────────────────────────────────────────────────────────
#  Continuous beep alarm thread
# ─────────────────────────────────────────────────────────────
class AlarmThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            winsound.Beep(BEEP_FREQ, BEEP_DURATION)
            self._stop.wait(BEEP_PAUSE / 1000.0)

    def stop(self):
        self._stop.set()


# ─────────────────────────────────────────────────────────────
#  Send SMS via Twilio (runs on a background thread)
# ─────────────────────────────────────────────────────────────
def send_sms_alert(closed_secs):
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        msg = client.messages.create(
            body=(
                f"⚠️ DRIVER DROWSINESS ALERT!\n"
                f"Eyes were closed for {closed_secs:.0f} seconds.\n"
                f"Please pull over and take a break immediately."
            ),
            from_=TWILIO_FROM,
            to=ALERT_TO,
        )
        print(f"✅ SMS sent! SID: {msg.sid}")
    except Exception as e:
        print(f"❌ SMS failed: {e}")


# ─────────────────────────────────────────────────────────────
#  Eye detection inside face ROI
# ─────────────────────────────────────────────────────────────
def detect_eyes(face_gray):
    eyes = EYE_CASCADE.detectMultiScale(
        face_gray,
        scaleFactor=1.1,
        minNeighbors=6,
        minSize=(30, 30),
        flags=cv2.CASCADE_SCALE_IMAGE,
    )
    if len(eyes) == 0:
        return []
    return [e for e in eyes if e[2] * e[3] >= MIN_EYE_AREA]


# ─────────────────────────────────────────────────────────────
#  HUD overlay
# ─────────────────────────────────────────────────────────────
def draw_hud(frame, eyes_open, closed_secs, alarm_on, sms_sent):
    h, w = frame.shape[:2]

    # Top dark banner
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 85), (15, 15, 15), -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    # Main status text
    if alarm_on:
        label = "⚠  WAKE UP! EYES CLOSED!"
        color = (0, 0, 255)
    elif eyes_open:
        label = "Eyes Open  —  Safe"
        color = (0, 220, 80)
    else:
        label = f"Eyes Closed  {closed_secs:.1f}s"
        color = (0, 165, 255)

    cv2.putText(frame, label, (12, 58),
                cv2.FONT_HERSHEY_DUPLEX, 1.3, color, 2, cv2.LINE_AA)

    # SMS badge (top-right)
    if sms_sent:
        cv2.rectangle(frame, (w - 175, 8), (w - 8, 42), (0, 120, 0), -1)
        cv2.putText(frame, "SMS SENT", (w - 166, 33),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
    else:
        cv2.rectangle(frame, (w - 175, 8), (w - 8, 42), (40, 40, 40), -1)
        cv2.putText(frame, f"SMS @ {SMS_SECONDS}s", (w - 166, 33),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (140, 140, 140), 1, cv2.LINE_AA)

    # Flashing red border during alarm
    if alarm_on and int(time.time() * 3) % 2 == 0:
        cv2.rectangle(frame, (0, 0), (w, h), (0, 0,230), 8)

    # Bottom progress bar (counts toward alarm)
    if not eyes_open and not alarm_on:
        ratio     = min(closed_secs / ALARM_SECONDS, 1.0)
        bar_w     = int(w * ratio)
        bar_color = (0, int(200 * (1 - ratio)), 200) if ratio < 0.5 else (0, 0, 220)
        cv2.rectangle(frame, (0, h - 28), (bar_w, h - 8), bar_color, -1)
        remaining = max(0, ALARM_SECONDS - closed_secs)
        cv2.putText(frame, f"Alarm in {remaining:.1f}s",
                    (10, h - 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 200, 200), 1, cv2.LINE_AA)

    # Quit hint
    cv2.putText(frame, "Q / ESC to quit",
                (10, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 100, 100), 1, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────
#  Main loop
# ─────────────────────────────────────────────────────────────
def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS,          30)

    print("Driver Safety App started.")
    print(f"  Beep alarm  →  eyes closed >= {ALARM_SECONDS}s")
    print(f"  SMS alert   →  eyes closed >= {SMS_SECONDS}s  →  {ALERT_TO}")
    print("Press  Q  or  ESC  to quit.\n")

    eyes_closed_since = None
    alarm_thread      = None
    alarm_active      = False
    sms_sent          = False

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame grab failed.")
            break

        frame = cv2.flip(frame, 1)
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray  = cv2.equalizeHist(gray)

        # ── Detect face + eyes ────────────────────────────────
        faces = FACE_CASCADE.detectMultiScale(
            gray,
            scaleFactor=1.2,
            minNeighbors=5,
            minSize=(120, 120),
        )

        eyes_detected = False

        for (fx, fy, fw, fh) in faces:
            cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (100, 200, 255), 2)

            eye_gray  = gray [fy : fy + fh // 2, fx : fx + fw]
            eye_color = frame[fy : fy + fh // 2, fx : fx + fw]

            eyes = detect_eyes(eye_gray)
            if len(eyes) >= 1:
                eyes_detected = True
                for (ex, ey, ew, eh) in eyes:
                    cv2.circle(eye_color,
                               (ex + ew // 2, ey + eh // 2),
                               ew // 2, (0, 255, 100), 2)

        # ── State machine ─────────────────────────────────────
        now = time.time()

        if eyes_detected:
            # ── Eyes OPEN → reset everything ──────────────────
            eyes_closed_since = None
            sms_sent          = False          # allow SMS to fire again next time

            if alarm_active:
                alarm_thread.stop()
                alarm_thread = None
                alarm_active = False
                print("Eyes opened — alarm cleared.")

        else:
            # ── Eyes CLOSED → advance timer ───────────────────
            if eyes_closed_since is None:
                eyes_closed_since = now

            closed_duration = now - eyes_closed_since

            # Beep alarm at ALARM_SECONDS
            if closed_duration >= ALARM_SECONDS and not alarm_active:
                print(f"Eyes closed {closed_duration:.1f}s — starting beep alarm!")
                alarm_thread = AlarmThread()
                alarm_thread.start()
                alarm_active = True

            # SMS alert at SMS_SECONDS
            if closed_duration >= SMS_SECONDS and not sms_sent:
                print(f"Eyes closed {closed_duration:.1f}s — sending SMS to {ALERT_TO} ...")
                sms_sent = True   # set flag first to avoid duplicate sends
                threading.Thread(
                    target=send_sms_alert,
                    args=(closed_duration,),
                    daemon=True
                ).start()

        # ── Draw HUD ──────────────────────────────────────────
        closed_secs = (now - eyes_closed_since) if eyes_closed_since else 0.0
        draw_hud(frame, eyes_detected, closed_secs, alarm_active, sms_sent)

        cv2.imshow("Driver Safety Monitor", frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            break

    # Cleanup
    if alarm_active and alarm_thread:
        alarm_thread.stop()

    cap.release()
    cv2.destroyAllWindows()
    print("Bye!")


if __name__ == "__main__":
    main()
