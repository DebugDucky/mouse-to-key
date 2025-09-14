import time
import threading
import tkinter as tk
from tkinter import ttk
from pynput import mouse, keyboard

kb = keyboard.Controller()

# ----------------------------
# Shared state (guard with lock)
# ----------------------------
state_lock = threading.Lock()
holding_w = False
holding_shift = False
running = False

last_y = None
last_event_time = 0.0
last_move_time = 0.0

# smoothed speed (px/s)
speed_ema = 0.0
current_speed = 0.0

# ----------------------------
# Tunables
# ----------------------------
TIMEOUT = 0.30             # seconds of no forward motion -> release W/Shift
PIX_THRESHOLD = 2           # ignore tiny jitters (px)
SPRINT_ON = 90.0            # px/s to engage Shift
SPRINT_OFF = 60.0           # px/s to disengage Shift (must be < SPRINT_ON)
SMOOTH_ALPHA = 0.25         # 0..1 (higher = more reactive, lower = smoother)
MAX_DY_PER_EVENT = 50       # cap per event px to avoid spikes
MIN_DT = 0.01               # clamp min dt between events (s)
IGNORE_FIRST_MS = 120       # only right after Start, not every event

# NEW: only suppress sprint until this timestamp (set on Start)
sprint_enable_time = 0.0

listener = None
timeout_thread = None

def press_w():
    global holding_w
    if not holding_w:
        kb.press('w')
        holding_w = True
        print("Pressing W")

def release_w():
    global holding_w
    if holding_w:
        kb.release('w')
        holding_w = False
        print("Releasing W")

def press_shift():
    global holding_shift
    if not holding_shift:
        kb.press(keyboard.Key.shift)
        holding_shift = True
        print("Pressing Shift (sprint)")

def release_shift():
    global holding_shift
    if holding_shift:
        kb.release(keyboard.Key.shift)
        holding_shift = False
        print("Releasing Shift")

def on_move(x, y):
    global last_y, last_event_time, last_move_time, speed_ema, current_speed

    now = time.time()
    with state_lock:
        if not running:
            return

        if last_y is None:
            last_y = y
            last_event_time = now
            last_move_time = now
            return

        dt = max(now - last_event_time, MIN_DT)
        dy = y - last_y
        last_y = y
        last_event_time = now

        # Only treat upward motion (negative dy) as "forward".
        if dy < -PIX_THRESHOLD:
            dy_use = min(abs(dy), MAX_DY_PER_EVENT)
            inst_speed = dy_use / dt  # px/s for this event

            # Exponential moving average to smooth spikes
            speed_ema = (SMOOTH_ALPHA * inst_speed) + ((1.0 - SMOOTH_ALPHA) * speed_ema)
            current_speed = speed_ema

            # Hold W while moving forward
            press_w()

            # >>> FIX: allow sprint toggling while W is held (no need to stop)
            if now >= sprint_enable_time:
                if speed_ema >= SPRINT_ON:
                    press_shift()
                elif speed_ema <= SPRINT_OFF:
                    release_shift()
            # <<<

            last_move_time = now
        else:
            # No forward movement -> decay EMA gently
            speed_ema *= 0.9
            current_speed = max(speed_ema, 0.0)

def timeout_loop():
    while True:
        with state_lock:
            if not running:
                # ensure keys are up while stopped
                release_shift()
                release_w()
            else:
                # Release after inactivity
                if holding_w and (time.time() - last_move_time) > TIMEOUT:
                    print("Timeout -> releasing keys")
                    release_shift()
                    release_w()
        time.sleep(0.05)

# ----------------------------
# GUI
# ----------------------------
class WalkerGUI:
    def __init__(self, root):
        self.root = root
        root.title("VR Walker Tuner")

        # Always on top option
        self.always_on_top = tk.BooleanVar(value=True)
        root.wm_attributes("-topmost", True)

        pad = {'padx': 8, 'pady': 6}

        # Vars bound to sliders
        self.timeout_var = tk.DoubleVar(value=TIMEOUT)
        self.pix_var = tk.IntVar(value=PIX_THRESHOLD)
        self.on_var = tk.DoubleVar(value=SPRINT_ON)
        self.off_var = tk.DoubleVar(value=SPRINT_OFF)
        self.alpha_var = tk.DoubleVar(value=SMOOTH_ALPHA)
        self.speed_readout = tk.StringVar(value="0.0 px/s")

        # Title
        ttk.Label(root, text="Mouse → W + Shift (Smoothed + Hysteresis)",
                  font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=4, **pad)

        # Row: Always on top
        aot = ttk.Checkbutton(root, text="Always on top", variable=self.always_on_top, command=self._toggle_aot)
        aot.grid(row=1, column=0, sticky="w", **pad)

        # Timeout
        ttk.Label(root, text="Timeout (s)").grid(row=2, column=0, sticky="w", **pad)
        self.timeout_scale = ttk.Scale(root, from_=0.05, to=1.5, orient="horizontal",
                                       variable=self.timeout_var, command=self._on_timeout)
        self.timeout_scale.grid(row=2, column=1, sticky="ew", **pad)
        self.timeout_label = ttk.Label(root, text=f"{self.timeout_var.get():.2f} s")
        self.timeout_label.grid(row=2, column=2, sticky="e", **pad)

        # Pixel threshold
        ttk.Label(root, text="Pixel Threshold (px)").grid(row=3, column=0, sticky="w", **pad)
        self.pix_scale = ttk.Scale(root, from_=0, to=20, orient="horizontal",
                                   variable=self.pix_var, command=self._on_pix)
        self.pix_scale.grid(row=3, column=1, sticky="ew", **pad)
        self.pix_label = ttk.Label(root, text=f"{self.pix_var.get():.0f} px")
        self.pix_label.grid(row=3, column=2, sticky="e", **pad)

        # EMA smoothing
        ttk.Label(root, text="Smoothing α (0–1)").grid(row=4, column=0, sticky="w", **pad)
        self.alpha_scale = ttk.Scale(root, from_=0.05, to=0.9, orient="horizontal",
                                     variable=self.alpha_var, command=self._on_alpha)
        self.alpha_scale.grid(row=4, column=1, sticky="ew", **pad)
        self.alpha_label = ttk.Label(root, text=f"{self.alpha_var.get():.2f}")
        self.alpha_label.grid(row=4, column=2, sticky="e", **pad)

        # Sprint On
        ttk.Label(root, text="Sprint ON (px/s)").grid(row=5, column=0, sticky="w", **pad)
        self.on_scale = ttk.Scale(root, from_=20, to=5000, orient="horizontal",
                                  variable=self.on_var, command=self._on_on)
        self.on_scale.grid(row=5, column=1, sticky="ew", **pad)
        self.on_label = ttk.Label(root, text=f"{self.on_var.get():.0f} px/s")
        self.on_label.grid(row=5, column=2, sticky="e", **pad)

        # Sprint Off
        ttk.Label(root, text="Sprint OFF (px/s)").grid(row=6, column=0, sticky="w", **pad)
        self.off_scale = ttk.Scale(root, from_=10, to=4800, orient="horizontal",
                                   variable=self.off_var, command=self._on_off)
        self.off_scale.grid(row=6, column=1, sticky="ew", **pad)
        self.off_label = ttk.Label(root, text=f"{self.off_var.get():.0f} px/s")
        self.off_label.grid(row=6, column=2, sticky="e", **pad)

        # Start/Stop/ Quit
        self.start_btn = ttk.Button(root, text="Start", command=self.start)
        self.stop_btn = ttk.Button(root, text="Stop", command=self.stop, state="disabled")
        self.quit_btn = ttk.Button(root, text="Quit", command=self.quit)
        self.start_btn.grid(row=7, column=0, **pad)
        self.stop_btn.grid(row=7, column=1, **pad)
        self.quit_btn.grid(row=7, column=2, **pad)

        # Speed readout
        ttk.Label(root, text="Smoothed Speed:").grid(row=8, column=0, sticky="w", **pad)
        ttk.Label(root, textvariable=self.speed_readout, font=("Segoe UI", 11, "bold")).grid(row=8, column=1, sticky="w", **pad)

        # Big indicators
        self.w_button = tk.Label(root, text="W", font=("Segoe UI", 28, "bold"),
                                 width=4, height=2, relief="raised", bg="lightgrey")
        self.w_button.grid(row=9, column=0, columnspan=1, **pad)

        self.shift_button = tk.Label(root, text="Shift", font=("Segoe UI", 28, "bold"),
                                     width=6, height=2, relief="raised", bg="lightgrey")
        self.shift_button.grid(row=9, column=1, columnspan=2, **pad)

        root.columnconfigure(1, weight=1)

        # Update loops
        self._update_readout()
        self._update_keys()

        root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---------- GUI callbacks ----------
    def _toggle_aot(self):
        self.root.wm_attributes("-topmost", bool(self.always_on_top.get()))

    def _on_timeout(self, _=None):
        global TIMEOUT
        TIMEOUT = float(self.timeout_var.get())
        self.timeout_label.config(text=f"{TIMEOUT:.2f} s")

    def _on_pix(self, _=None):
        global PIX_THRESHOLD
        PIX_THRESHOLD = int(self.pix_var.get())
        self.pix_label.config(text=f"{PIX_THRESHOLD} px")

    def _on_alpha(self, _=None):
        global SMOOTH_ALPHA
        SMOOTH_ALPHA = float(self.alpha_var.get())
        self.alpha_label.config(text=f"{SMOOTH_ALPHA:.2f}")

    def _on_on(self, _=None):
        global SPRINT_ON, SPRINT_OFF
        SPRINT_ON = float(self.on_var.get())
        if float(self.off_var.get()) >= SPRINT_ON:
            self.off_var.set(max(10.0, SPRINT_ON - 5.0))
            SPRINT_OFF = float(self.off_var.get())
        self.on_label.config(text=f"{SPRINT_ON:.0f} px/s")

    def _on_off(self, _=None):
        global SPRINT_OFF
        SPRINT_OFF = float(self.off_var.get())
        if SPRINT_OFF >= float(self.on_var.get()):
            SPRINT_OFF = max(10.0, float(self.on_var.get()) - 5.0)
            self.off_var.set(SPRINT_OFF)
        self.off_label.config(text=f"{SPRINT_OFF:.0f} px/s")

    def _update_readout(self):
        with state_lock:
            spd = current_speed
        self.speed_readout.set(f"{spd:.1f} px/s")
        self.root.after(100, self._update_readout)

    def _update_keys(self):
        with state_lock:
            w_on = holding_w
            shift_on = holding_shift
        self.w_button.config(bg="green" if w_on else "lightgrey")
        self.shift_button.config(bg="green" if shift_on else "lightgrey")
        self.root.after(100, self._update_keys)

    # ---------- Control ----------
    def start(self):
        global running, listener, timeout_thread
        global last_y, last_event_time, last_move_time, speed_ema, current_speed, sprint_enable_time
        with state_lock:
            if running:
                return
            running = True
            # Reset trackers
            last_y = None
            last_event_time = time.time()
            last_move_time = time.time()
            speed_ema = 0.0
            current_speed = 0.0
            # >>> only suppress sprint right after Start <<<
            sprint_enable_time = time.time() + (IGNORE_FIRST_MS / 1000.0)

        if listener is None or not listener.running:
            listener = mouse.Listener(on_move=on_move)
            listener.daemon = True
            listener.start()

        if not (timeout_thread and timeout_thread.is_alive()):
            self._spawn_timeout_thread()

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    def _spawn_timeout_thread(self):
        global timeout_thread
        timeout_thread = threading.Thread(target=timeout_loop, daemon=True)
        timeout_thread.start()

    def stop(self):
        global running
        with state_lock:
            running = False
            release_shift()
            release_w()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def quit(self):
        self.stop()
        # small delay to ensure key-up sent
        self.root.after(60, self.root.destroy)

def main():
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    app = WalkerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
