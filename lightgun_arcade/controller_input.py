from __future__ import annotations

import ctypes
import os
import queue
import threading
import time
from typing import Any

try:
    import pygame
except Exception:  # pragma: no cover - optional runtime dependency
    pygame = None


XINPUT_GAMEPAD_DPAD_UP = 0x0001
XINPUT_GAMEPAD_DPAD_DOWN = 0x0002
XINPUT_GAMEPAD_DPAD_LEFT = 0x0004
XINPUT_GAMEPAD_DPAD_RIGHT = 0x0008
XINPUT_GAMEPAD_LEFT_SHOULDER = 0x0100
XINPUT_GAMEPAD_RIGHT_SHOULDER = 0x0200
XINPUT_GAMEPAD_A = 0x1000
XINPUT_GAMEPAD_B = 0x2000
ERROR_SUCCESS = 0


class _XInputGamepad(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class _XInputState(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_ulong), ("Gamepad", _XInputGamepad)]


class ControllerInput:
    def __init__(self, action_queue: "queue.Queue[str]", controller_settings: dict[str, Any], logger: Any) -> None:
        self.action_queue = action_queue
        self.settings = controller_settings
        self.logger = logger
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_action_ts: dict[str, float] = {}

        self._xinput = self._load_xinput()
        self._xinput_prev_buttons: int = 0
        self._xinput_user_index: int = 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _can_fire(self, action: str) -> bool:
        repeat_ms = int(self.settings.get("repeat_ms", 200))
        now = time.time()
        last = self._last_action_ts.get(action, 0.0)
        if (now - last) * 1000 < repeat_ms:
            return False
        self._last_action_ts[action] = now
        return True

    def _emit(self, action: str) -> None:
        if self._can_fire(action):
            self.action_queue.put(action)

    def _load_xinput(self) -> Any | None:
        if os.name != "nt":
            return None
        for dll_name in ["xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"]:
            try:
                lib = ctypes.WinDLL(dll_name)
                lib.XInputGetState.argtypes = [ctypes.c_uint, ctypes.POINTER(_XInputState)]
                lib.XInputGetState.restype = ctypes.c_uint
                self.logger.info("XInput loaded from %s", dll_name)
                return lib
            except Exception:
                continue
        self.logger.warning("XInput DLL not available")
        return None

    def _poll_xinput(self, deadzone: float, button_map: dict[str, Any]) -> bool:
        if self._xinput is None:
            return False

        state = _XInputState()
        active_index = None
        for idx in range(4):
            result = self._xinput.XInputGetState(idx, ctypes.byref(state))
            if result == ERROR_SUCCESS:
                active_index = idx
                break
        if active_index is None:
            self._xinput_prev_buttons = 0
            return False

        self._xinput_user_index = active_index
        buttons = int(state.Gamepad.wButtons)
        prev_buttons = self._xinput_prev_buttons
        self._xinput_prev_buttons = buttons

        if buttons & XINPUT_GAMEPAD_DPAD_UP:
            self._emit("up")
        if buttons & XINPUT_GAMEPAD_DPAD_DOWN:
            self._emit("down")
        if buttons & XINPUT_GAMEPAD_DPAD_LEFT:
            self._emit("left")
        if buttons & XINPUT_GAMEPAD_DPAD_RIGHT:
            self._emit("right")

        lx = float(state.Gamepad.sThumbLX) / 32767.0 if state.Gamepad.sThumbLX else 0.0
        ly = float(state.Gamepad.sThumbLY) / 32767.0 if state.Gamepad.sThumbLY else 0.0
        if ly > deadzone:
            self._emit("up")
        elif ly < -deadzone:
            self._emit("down")
        if lx > deadzone:
            self._emit("right")
        elif lx < -deadzone:
            self._emit("left")

        button_bit_map = {
            int(button_map.get("select", 0)): XINPUT_GAMEPAD_A,
            int(button_map.get("back", 1)): XINPUT_GAMEPAD_B,
            int(button_map.get("tab_next", 5)): XINPUT_GAMEPAD_RIGHT_SHOULDER,
            int(button_map.get("tab_prev", 4)): XINPUT_GAMEPAD_LEFT_SHOULDER,
        }
        action_map = {
            int(button_map.get("select", 0)): "select",
            int(button_map.get("back", 1)): "back",
            int(button_map.get("tab_next", 5)): "tab_next",
            int(button_map.get("tab_prev", 4)): "tab_prev",
        }
        for btn_idx, bit in button_bit_map.items():
            if (buttons & bit) and not (prev_buttons & bit):
                self._emit(action_map[btn_idx])

        return True

    def _loop(self) -> None:
        deadzone = float(self.settings.get("deadzone", 0.45))
        button_map = self.settings.get("button_map", {})
        pygame_ready = False
        if pygame is not None:
            try:
                pygame.init()
                pygame.joystick.init()
                pygame_ready = True
            except Exception as exc:
                self.logger.warning("pygame init failed: %s", exc)

        self.logger.info("Controller input service started")

        try:
            while self._running:
                handled = False

                if pygame_ready and pygame is not None:
                    try:
                        joystick_count = pygame.joystick.get_count()
                    except Exception as exc:
                        self.logger.warning("pygame joystick poll failed (%s); disabling pygame input", exc)
                        pygame_ready = False
                        joystick_count = 0

                    if joystick_count > 0:
                        try:
                            joy = pygame.joystick.Joystick(0)
                            joy.init()
                            for event in pygame.event.get():
                                if event.type == pygame.JOYHATMOTION:
                                    x, y = event.value
                                    if y == 1:
                                        self._emit("up")
                                    elif y == -1:
                                        self._emit("down")
                                    if x == 1:
                                        self._emit("right")
                                    elif x == -1:
                                        self._emit("left")
                                elif event.type == pygame.JOYAXISMOTION:
                                    if event.axis == 1:
                                        if event.value < -deadzone:
                                            self._emit("up")
                                        elif event.value > deadzone:
                                            self._emit("down")
                                    if event.axis == 0:
                                        if event.value > deadzone:
                                            self._emit("right")
                                        elif event.value < -deadzone:
                                            self._emit("left")
                                elif event.type == pygame.JOYBUTTONDOWN:
                                    if event.button == int(button_map.get("select", 0)):
                                        self._emit("select")
                                    elif event.button == int(button_map.get("back", 1)):
                                        self._emit("back")
                                    elif event.button == int(button_map.get("tab_next", 5)):
                                        self._emit("tab_next")
                                    elif event.button == int(button_map.get("tab_prev", 4)):
                                        self._emit("tab_prev")
                            handled = True
                        except Exception as exc:
                            # Some DirectInput backends fail with SetCooperativeLevel on specific windows.
                            self.logger.warning("pygame controller poll failed (%s); falling back to XInput only", exc)
                            pygame_ready = False

                if (not handled) and self._poll_xinput(deadzone, button_map):
                    handled = True

                time.sleep(0.02 if handled else 0.15)
        except Exception as exc:  # pragma: no cover - runtime safety
            self.logger.warning("Controller input failed: %s", exc)
        finally:
            try:
                if pygame is not None:
                    pygame.joystick.quit()
                    pygame.quit()
            except Exception:
                pass
            self.logger.info("Controller input service stopped")
