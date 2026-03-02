from __future__ import annotations

import queue
import threading
import time
from typing import Any

try:
    import pygame
except Exception:  # pragma: no cover - optional runtime dependency
    pygame = None


class ControllerInput:
    def __init__(self, action_queue: "queue.Queue[str]", controller_settings: dict[str, Any], logger: Any) -> None:
        self.action_queue = action_queue
        self.settings = controller_settings
        self.logger = logger
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_action_ts: dict[str, float] = {}

    def start(self) -> None:
        if pygame is None:
            self.logger.warning("pygame missing: Xbox controller input disabled")
            return
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

    def _loop(self) -> None:
        assert pygame is not None
        try:
            pygame.init()
            pygame.joystick.init()
            deadzone = float(self.settings.get("deadzone", 0.45))
            button_map = self.settings.get("button_map", {})

            self.logger.info("Controller input service started")

            while self._running:
                if pygame.joystick.get_count() <= 0:
                    time.sleep(0.5)
                    continue
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
                time.sleep(0.02)
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

