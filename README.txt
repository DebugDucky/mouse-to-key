Mouse-to-W/Shift Controller

This program lets you walk and sprint in VR using a treadmill and a computer mouse.
When you place a mouse on a treadmill belt, the program translates the mouse’s upward movement into holding the W key (walk forward).
If your movement speed passes a configurable threshold, it also holds Shift (sprint).

The program includes a GUI with sliders and big W/Shift indicators so you can tune it easily and see whether the keys are being pressed, even while you’re walking on the treadmill.

Features

Mouse → Keyboard
Upward mouse movement = hold W
Faster movement = hold Shift (sprint)
Timeout system: releases keys if no movement is detected.
GUI control panel (Tkinter):
Adjust Timeout, Pixel Threshold, Smoothing, Sprint ON/OFF thresholds.
Live speed readout (smoothed pixels/second).
Big on-screen W and Shift buttons that light up green when pressed.
Always-on-top window option so the indicators stay visible.
Safe stop/quit: automatically releases keys when you stop the program.

Requirements

Python 3.9 or newer
pynput for keyboard/mouse control

Install dependencies:

pip install pynput
Tkinter is included with most Python distributions by default.


▶Usage

Place a mouse on your treadmill (optical sensor facing the belt).

Run the program:
mouse-to-key.py


Use the GUI:

Press Start to begin listening.
Adjust sliders until walking and sprinting feel natural.
Watch the W and Shift indicators — they turn green when pressed.
Press Stop to pause or Quit to exit.



Settings:

Timeout (s): How long (seconds) after last movement before releasing keys.
Pixel Threshold (px): Ignores tiny jitters (e.g., belt vibration).
Smoothing α (0–1): Exponential smoothing factor for speed.
Lower = smoother, more stable.
Higher = faster response, but can flicker.
Sprint ON (px/s): Smoothed speed needed to press Shift.
Sprint OFF (px/s): Smoothed speed below which Shift is released.
This hysteresis prevents flickering — ON should be set higher than OFF.

Indicators

W button = lights green while W is being pressed.
Shift button = lights green while Shift is being pressed.
These are designed to be big and visible from a treadmill.

Notes

Some VR games may require running this script as Administrator for key presses to register.
Key presses are sent system-wide — don’t use while typing or browsing!
Adjust thresholds based on your treadmill speed and mouse DPI.

License

MIT License — free to use, modify, and share.