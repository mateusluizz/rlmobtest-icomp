#!/usr/bin/env python3
"""
Android environment for RL-based mobile app testing.
"""

import csv
import logging
import os
import random
import shutil
import string
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from subprocess import call

import numpy as np
import torch
import torchvision.transforms as T
import uiautomator2 as u2
import matplotlib
matplotlib.use("Agg")
from matplotlib.pyplot import imread
from PIL import Image
from uiautomator2.exceptions import UiObjectNotFoundError

from rlmobtest.constants.paths import (
    CONFIG_PATH,
    COVERAGE_PATH,
    CRASHES_PATH,
    ERRORS_PATH,
    INPUTS_BASE,
    SCREENSHOTS_PATH,
    TEST_CASES_PATH,
)

FNULL = open(os.devnull, "w", encoding="utf-8")

# Image resize transform
resize = T.Compose(
    [T.ToPILImage(), T.Resize(38, interpolation=Image.Resampling.BICUBIC), T.ToTensor()]
)

# Device for PyTorch
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def safe_get_child_count(gui_obj, device_ref):
    """
    Safely get child count from UI object.
    Returns 0 and presses back if element not found.
    """
    try:
        return gui_obj.info["childCount"]
    except UiObjectNotFoundError:
        logging.debug("UiObjectNotFoundError - pressing back")
        device_ref.press("back")
        return 0


class Action:
    """Represents an action that can be performed on an Android UI element."""

    def __init__(
        self,
        gui_object,
        activity,
        nametc,
        field,
        field_type,
        resourceid,
        action_type,
        size_start,
        size_end,
        value,
        action_subtype,
        result_activity,
        result_elem,
        result_text,
        text,
        elem,
        test_case_path=None,
    ):
        self.gui_object = gui_object
        self.activity = activity
        self.nametc = nametc
        self.field = field
        self.field_type = field_type
        self.resourceid = resourceid
        self.action_type = action_type
        self.size_start = size_start
        self.size_end = size_end
        self.value = value
        self.result_activity = result_activity
        self.action_subtype = action_subtype
        self.result_elem = result_elem
        self.result_text = result_text
        self.elem = elem
        self.text = text
        self.test_case_path = test_case_path if test_case_path else str(TEST_CASES_PATH)

    def _check_element_exists(self):
        """Verifica se o elemento GUI ainda existe na tela."""
        try:
            if self.gui_object is not None:
                return self.gui_object.exists
        except Exception:
            pass
        return False

    def _execute_with_timeout(self, func, env, timeout=30):
        """Executa uma ação com timeout. Retorna True se sucesso, False se timeout."""
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func)
                future.result(timeout=timeout)
                return True
        except FuturesTimeoutError:
            print(f"   ⏰ ACTION TIMEOUT: {self.action_type} took longer than {timeout}s")
            logging.debug(f"Action timeout: {self.action_type} after {timeout}s")
            # Força retorno à home do app
            print("   🏠 Forcing return to app home...")
            env._return_to_app_home()
            return False
        except Exception as e:
            logging.debug(f"Error in action with timeout: {e}")
            return False

    def execute(self, nametc, env):
        """Execute the action on the device."""
        # Use env.test_case_path (correct path) instead of self.test_case_path (legacy)
        test_case_path = env.test_case_path
        os.makedirs(test_case_path, exist_ok=True)
        with open(f"{test_case_path}/{nametc}", "a", encoding="utf-8") as file:
            try:
                if self.action_type == "first":
                    env.device.press("back")
                    env._exec("adb shell am start -n " + env.first_activity)
                    env.tc_action = []
                    file.write("\n\nHome activity")
                    print("Home activity")

                elif self.action_type == "back":
                    env.device.press("back")
                    file.write("\n\nBack Pressed")
                    print("Back Pressed")
                    logging.debug("back pressed")

                elif self.action_type == "home":
                    env.device.press("home")
                    file.write("\n\nHome Pressed")
                    print("Home Pressed")
                    logging.debug("home pressed")

                elif self.action_type == "menu":
                    env.device(scrollable=True).scroll.to(text="Menu")
                    file.write("\n\nMenu Pressed")
                    print("Menu Pressed")
                    logging.debug("menu pressed")

                elif self.action_type == "volume_up":
                    env.device.press("volume_up")
                    file.write("\n\nVolume Up Pressed")
                    print("Volume Up Pressed")
                    logging.debug("volume up pressed")

                elif self.action_type == "volume_down":
                    env.device.press("volume_down")
                    file.write("\n\nVolume Down Pressed")
                    print("Volume Down Pressed")
                    logging.debug("volume down pressed")

                elif self.action_type == "mute":
                    env.device.press("volume_mute")
                    file.write("\n\nVolume mute Pressed")
                    print("Volume mute Pressed")
                    logging.debug("volume mute pressed")

                elif self.action_type == "rotate_l":
                    env.device.set_orientation("l")
                    file.write("\n\nRotate left Pressed")
                    print("Rotate left Pressed")
                    logging.debug("Rotate left pressed")

                elif self.action_type == "rotate_r":
                    env.device.set_orientation("r")
                    file.write("\n\nRotate right Pressed")
                    print("Rotate right Pressed")
                    logging.debug("Rotate right pressed")

                elif self.action_type == "scroll":
                    self._execute_scroll(file, env)

                elif self.action_type == "long-click":
                    if self._check_element_exists():
                        success = self._execute_with_timeout(
                            lambda: self._execute_long_click(file), env
                        )
                        if not success:
                            file.write(f"\n\n⏰ Timeout on long-click: {self.elem}")
                    else:
                        file.write(f"\n\n⚠️ Element not found: {self.elem}")
                        print(f"   ⚠️ Element not found for long-click: {self.elem[:50]}")

                elif self.action_type == "check":
                    if self._check_element_exists():
                        success = self._execute_with_timeout(lambda: self._execute_check(file), env)
                        if not success:
                            file.write(f"\n\n⏰ Timeout on check: {self.elem}")
                    else:
                        file.write(f"\n\n⚠️ Element not found: {self.elem}")
                        print(f"   ⚠️ Element not found for check: {self.elem[:50]}")

                elif self.action_type == "click":
                    if self._check_element_exists():
                        success = self._execute_with_timeout(lambda: self._execute_click(file), env)
                        if not success:
                            file.write(f"\n\n⏰ Timeout on click: {self.elem}")
                    else:
                        file.write(f"\n\n⚠️ Element not found: {self.elem}")
                        print(f"   ⚠️ Element not found for click: {self.elem[:50]}")

                elif self.action_type == "type":
                    if self._check_element_exists():
                        success = self._execute_with_timeout(
                            lambda: self._execute_type(file, env), env
                        )
                        if not success:
                            file.write(f"\n\n⏰ Timeout on type: {self.elem}")
                    else:
                        file.write(f"\n\n⚠️ Element not found: {self.elem}")
                        print(f"   ⚠️ Element not found for type: {self.elem[:50]}")

            except Exception as e:
                error_msg = str(e)
                if "UiObjectNotFoundError" in error_msg or "UiObjectNotFoundException" in error_msg:
                    file.write(f"\n\n⚠️ Element disappeared: {self.elem}")
                    print(f"   ⚠️ Element disappeared during action: {self.action_type}")
                    logging.debug(f"UiObjectNotFoundError: {self.elem}")
                else:
                    file.write(f"\n\n❌ Error executing {self.action_type}: {error_msg}")
                    print(f"   ❌ Error: {error_msg[:80]}")
                    logging.debug(f"Action error: {e}")

    def _execute_scroll(self, file, env):
        """Execute scroll action."""
        try:
            if self.action_subtype == "down":
                env.device(scrollable=True).scroll.toEnd()
                file.write("\n\nScroll down " + self.elem)
                logging.debug("Scroll down " + self.elem)
                print("Scroll down " + self.elem)
            if self.action_subtype == "up":
                env.device(scrollable=True).scroll.toBeginning()
                file.write("\n\nScroll up " + self.elem)
                logging.debug("Scroll up " + self.elem)
                print("Scroll up " + self.elem)
            if self.action_subtype == "right":
                env.device.swipe(0.8, 0.5, 0.2, 0.5)
                file.write("\n\nScroll right " + self.elem)
                logging.debug("Scroll right " + self.elem)
                print("Scroll right " + self.elem)
            if self.action_subtype == "left":
                env.device.swipe(0.2, 0.5, 0.8, 0.5)
                file.write("\n\nScroll left " + self.elem)
                logging.debug("Scroll left " + self.elem)
                print("Scroll left " + self.elem)
        except Exception as e:
            logging.debug("Error Scroll " + str(e))
            print("Error Scroll " + str(e))
            env._exec("adb shell am start -n " + self.activity)

    def _execute_long_click(self, file):
        """Execute long click action."""
        try:
            if self.action_subtype == "center":
                self.gui_object.long_click(duration=1.0)
                file.write("\n\nLong click center " + self.elem)
                logging.debug("Long click center " + self.elem)
                print("Long click center " + self.elem)
            if self.action_subtype == "topleft":
                self.gui_object.long_click(duration=1.0)
                file.write("\n\nLong click top left " + self.elem)
                logging.debug("Long click top left " + self.elem)
                print("Long click top left " + self.elem)
            if self.action_subtype == "bottomright":
                self.gui_object.long_click(duration=1.0)
                file.write("\n\nLong click bottom right " + self.elem)
                logging.debug("Long click bottom right " + self.elem)
                print("Long click bottom right " + self.elem)
        except Exception as e:
            logging.debug("Error long click " + str(e))
            print("Error long click " + str(e))

    def _execute_check(self, file):
        """Execute check action."""
        try:
            if self.action_subtype == "check":
                if not self.gui_object.info.get("checked", False):
                    self.gui_object.click()
                    file.write("\n\nChecked " + self.elem)
                logging.debug("Check " + self.elem)
                print("Check " + self.elem)
        except Exception as e:
            logging.debug("Error check " + str(e))
            print("Error check " + str(e))

    def _execute_click(self, file):
        """Execute click action."""
        try:
            self.gui_object.click()
            file.write(f"\n\nClicked {self.elem}")
            logging.debug(f"Click: {self.elem}")
            print(f"Click: {self.elem}")
        except Exception as e:
            logging.debug(f"Error click {str(e)}")
            print(f"Error click {str(e)}")

    def _execute_type(self, file, env):
        """Execute type action."""
        try:
            if self.action_subtype == "tc_text":
                if self.value:
                    self.gui_object.send_keys(self.value)
                    file.write(f"\n\ntyped in {self.resourceid} value: {self.value}")
                    logging.debug(f"type: {self.resourceid} {self.value}")
                    print(f"type: {self.resourceid} {self.value}")

            elif self.action_subtype == "text_less1_start_size":
                result_str = self._generate_text(int(self.size_start) - 1)
                self._type_and_log(file, result_str, self.resourceid)
                file.write(f"\n\nExpected min size {self.size_start} Actual value: {result_str}")

            elif self.action_subtype == "text_start_size":
                result_str = self._generate_text(int(self.size_start))
                self._type_and_log(file, result_str, self.resourceid)

            elif self.action_subtype == "text_greater_end_size":
                result_str = self._generate_text(int(self.size_end) + 1)
                self._type_and_log(file, result_str, self.resourceid)
                file.write(f"\n\nExpected max size {self.size_end} Actual value: {result_str}")

            elif self.action_subtype == "text_end_size":
                result_str = self._generate_text(int(self.size_end))
                self._type_and_log(file, result_str, self.resourceid)

            elif self.action_subtype == "tc_number":
                if self.value != "":
                    self.gui_object.send_keys(self.value)
                    file.write(f"\n\ntyped in {self.resourceid} value: {self.value}")
                    logging.debug(f"type: {self.resourceid} {self.value}")
                    print(f"type: {self.resourceid} {self.value}")

            elif self.action_subtype == "number_less1_start_size":
                if int(self.size_start) == 1:
                    result_str = "0"
                else:
                    result_str = self._generate_number(int(self.size_start) - 1)
                self._type_and_log(file, result_str, self.resourceid)
                file.write(f"\n\nExpected min size {self.size_start} Actual value: {result_str}")

            elif self.action_subtype == "number_start_size":
                result_str = self._generate_number(int(self.size_start))
                self._type_and_log(file, result_str, self.resourceid)

            elif self.action_subtype == "number_end_size":
                result_str = self._generate_number(int(self.size_end))
                self._type_and_log(file, result_str, self.resourceid)

            elif self.action_subtype == "number_greater_end_size":
                result_str = self._generate_number(int(self.size_end) + 1)
                self._type_and_log(file, result_str, self.resourceid)
                file.write(f"\n\nExpected max size {self.size_end} Actual value: {result_str}")

            elif self.action_subtype == "textLarge":
                result_str = self._generate_text(100)
                self._type_and_log(file, result_str, self.elem)

            elif self.action_subtype == "textSmall":
                result_str = self._generate_text(1)
                self._type_and_log(file, result_str, self.elem)

            elif self.action_subtype == "textMedium":
                result_str = self._generate_text(10)
                self._type_and_log(file, result_str, self.elem)

            elif self.action_subtype == "numberSmall":
                result_str = self._generate_number(1)
                self._type_and_log(file, result_str, self.elem)

            elif self.action_subtype == "numberMedium":
                result_str = self._generate_number(2)
                self._type_and_log(file, result_str, self.elem)

            elif self.action_subtype == "numberLarge":
                result_str = self._generate_number(20)
                self._type_and_log(file, result_str, self.elem)

            elif self.action_subtype == "symbols":
                result_str = "".join(random.choice(string.punctuation) for _ in range(10))
                self.gui_object.send_keys(result_str)
                file.write(f"\n\ntyped in {self.elem} value: {result_str}")
                logging.debug(f"type: {self.elem} {result_str}")
                print(f"type: {self.elem} {result_str}")

            elif self.action_subtype == "mixed":
                letters_and_digits = string.ascii_letters + string.digits
                result_str = "".join(random.choice(letters_and_digits) for _ in range(15))
                self._type_and_log(file, result_str, self.elem)

        except Exception as e:
            logging.debug(f"Error edit {e}")
            print(f"Error edit {e}")
            env._exec(f"adb shell am start -n {self.activity}")

    def _generate_text(self, length):
        """Generate random text of specified length."""
        return "".join(random.choice(string.ascii_letters) for _ in range(length))

    def _generate_number(self, length):
        """Generate random number string of specified length."""
        return "".join(random.choice(string.digits) for _ in range(length))

    def _type_and_log(self, file, value, identifier):
        """Type value and log it."""
        self.gui_object.send_keys(value)
        file.write(f"\n\ntyped in {identifier} value: {value}")
        logging.debug(f"type: {identifier} {value}")
        print(f"type: {identifier} {value}")


class AndroidEnv:
    """Android environment for RL-based mobile app testing."""

    # Classes de UI que indicam dialogs/pickers problemáticos
    DIALOG_CLASSES = [
        "android.widget.DatePicker",
        "android.widget.TimePicker",
        "android.widget.CalendarView",
        "android.widget.NumberPicker",
        "android.app.DatePickerDialog",
        "android.app.TimePickerDialog",
    ]

    # Textos de botões para confirmar/cancelar dialogs
    DIALOG_CONFIRM_TEXTS = [
        "OK",
        "Ok",
        "ok",
        "SET",
        "Set",
        "DONE",
        "Done",
        "CONFIRM",
        "Confirm",
    ]
    DIALOG_CANCEL_TEXTS = ["CANCEL", "Cancel", "cancel", "CANCELAR", "Cancelar"]

    def __init__(
        self,
        app,
        app_package,
        coverage_enabled: bool = False,
        max_same_activity: int = 15,
        max_escape_attempts: int = 3,
        max_time_same_activity: int = 120,
        # Optional output paths (use defaults if not provided)
        test_case_path=None,
        screenshots_path=None,
        crashes_path=None,
        errors_path=None,
        coverage_path=None,
    ):
        self.app = str(INPUTS_BASE / "apks" / app)
        self.app_package = app_package
        self.coverage_enabled = coverage_enabled
        self.device = u2.connect()
        self.tc_action = []
        self.first_activity = ""
        self.nametc = "start.txt"
        if self.coverage_enabled:
            self._exec("adb forward tcp:8981 tcp:8981")
        self.edittexts = []
        self.buttons = []
        self.activities_req = []
        # Use provided paths or defaults
        self.test_case_path = str(test_case_path) if test_case_path else str(TEST_CASES_PATH)
        self.screenshots_path = str(screenshots_path) if screenshots_path else str(SCREENSHOTS_PATH)
        self.crashes_path = str(crashes_path) if crashes_path else str(CRASHES_PATH)
        self.errors_path = str(errors_path) if errors_path else str(ERRORS_PATH)
        self.coverage_path = str(coverage_path) if coverage_path else str(COVERAGE_PATH)
        # Controle de stuck/escape por steps
        self.stuck_counter = 0
        self.last_activity = ""
        self.same_activity_count = 0
        self.max_same_activity = (
            max_same_activity  # Steps na mesma activity antes de tentar escapar
        )
        self.escape_attempts = 0  # Tentativas de escape consecutivas
        self.max_escape_attempts = max_escape_attempts  # Máximo antes de voltar para home
        # Controle de stuck/escape por tempo
        self.activity_start_time = time.time()
        self.max_time_same_activity = (
            max_time_same_activity  # Segundos na mesma activity antes de forçar escape
        )
        # Timeout para operações UI (em segundos)
        self.ui_timeout = 30

    def _run_with_timeout(self, func, timeout=None, default=None):
        """Executa uma função com timeout. Retorna default se timeout ocorrer."""
        if timeout is None:
            timeout = self.ui_timeout
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func)
                return future.result(timeout=timeout)
        except FuturesTimeoutError:
            print(f"   ⏰ TIMEOUT: Operation took longer than {timeout}s")
            logging.debug("Timeout after %ds", timeout)
            return default
        except Exception as e:
            logging.debug("Error in _run_with_timeout: {%s}", e)
            return default

    def reset(self):
        """Reset the environment."""
        open("std.txt", "w").close()
        self._exec(f"adb shell am force-stop {self.app_package}")
        self._exec(f"adb shell monkey -p {self.app_package} 1")
        activity = self._get_activity()
        self.first_activity = activity
        return self._get_screen(), self._get_actions(activity)

    def install_app(self):
        """Install the app on the device."""
        try:
            self._exec(f"adb install -t {self.app} ")
            self._exec(
                f"adb shell pm grant {self.app_package} android.permission.READ_EXTERNAL_STORAGE"
            )
            self._exec(
                f"adb shell pm grant {self.app_package} android.permission.WRITE_EXTERNAL_STORAGE"
            )
        except Exception:
            print("Error when try to install")
            logging.debug("Error when try to install app")

    def _get_foreground(self):
        """Bring the app to foreground."""
        self._exec(f"adb shell monkey -p {self.app_package} 1")

    def _create_tcfile(self, activity):
        """Create a test case file for the given activity."""
        timestr = time.strftime("%Y%m%d-%H%M%S")
        x = list(activity)
        bar = "/"
        if bar in x:
            act = activity.split(bar)
            namefile = "TC_" + act[1] + "_" + timestr + ".txt"
        else:
            act = activity
            namefile = "TC_" + act + "_" + timestr + ".txt"

        filepath = f"{self.test_case_path}/{namefile}"
        if not os.path.exists(filepath):
            os.makedirs(self.test_case_path, exist_ok=True)
            with open(filepath, "w+") as file:
                file.write(f"Test Case{activity}")

        return namefile

    def _get_activity(self):
        """Get the current activity name."""
        try:
            # Execute ADB command and write to file
            self._exec("adb shell dumpsys activity recents | grep 'ActivityRecord' > std.txt")

            # Read the file
            with open("std.txt", "r", encoding="utf-8") as file:
                lines = file.readlines()

            activityname = "outapp"
            for line in lines:
                if self.app_package in line:
                    parts = line.split(",")
                    if parts:
                        act_part = parts[-1].split()
                        for item in act_part:
                            if self.app_package in item:
                                activityname = item
                                break
                    break

        except Exception as e:
            logging.debug(f"Error getting activity: {e}")
            activityname = "outapp"

        return activityname

    def step(self, action):
        """Execute one step in the environment."""
        self.tc_action.append(action)
        crash = False

        self._get_foreground()

        # Verifica se está em dialog ANTES de executar a ação
        is_dialog, dialog_type = self._detect_dialog()
        if is_dialog:
            print(f"   📅 Detected {dialog_type} before action, escaping...")
            self._escape_dialog()

        action.execute(self.nametc, self)

        if self.coverage_enabled:
            self._get_current_coverage()

        file_crash = self.get_crash()
        file_error = self.get_errors()

        activity = self._get_activity()

        # Verifica se está preso na mesma activity
        self._check_stuck(activity)

        if activity == "outapp":
            self.device.press("back")
            self._get_foreground()
            activity = self._get_activity()

        if file_crash != "":
            crash_file_path = f"{self.crashes_path}/{file_crash}"
            if os.path.exists(crash_file_path):
                filesizec = os.path.getsize(crash_file_path)
                if filesizec > 0:
                    crash = True
                    with open(
                        f"{self.test_case_path}/{self.nametc}",
                        mode="a",
                        encoding="utf-8",
                    ) as file:
                        file.write(f"\n\nGot Crash, see crashes/{file_crash}")
                    print("crash == true")
                    self.copy_coverage()
                    logging.debug("crash == true")

        if file_error != "":
            error_file_path = f"{self.errors_path}/{file_error}"
            if os.path.exists(error_file_path):
                filesizerr = os.path.getsize(error_file_path)
                if filesizerr > 0:
                    with open(
                        f"{self.test_case_path}/{self.nametc}",
                        mode="a",
                        encoding="utf-8",
                    ) as file:
                        file.write(f"\n\nGot Error, see errors/{file_error}")
                    logging.debug("error: %s", file_error)
                    print("errors == true")

        return self._get_screen(), self._get_actions(activity), crash, activity

    def _detect_dialog(self):
        """Detecta se está em um dialog/picker problemático."""
        try:
            xml = self.device.dump_hierarchy()

            # Verifica se há classes de dialog problemáticas
            for dialog_class in self.DIALOG_CLASSES:
                if dialog_class in xml:
                    return True, "dialog_class"

            # Verifica se há muitos NumberPickers (comum em DatePicker)
            if xml.count("NumberPicker") >= 2:
                return True, "number_pickers"

            # Verifica se há CalendarView
            if "CalendarView" in xml or "calendar" in xml.lower():
                return True, "calendar"

        except Exception as e:
            logging.debug(f"Error detecting dialog: {e}")

        return False, None

    def _escape_dialog(self):
        """Tenta escapar de um dialog/picker."""
        try:
            # Primeira tentativa: clicar em OK/Done/Confirm
            for text in self.DIALOG_CONFIRM_TEXTS:
                btn = self.device(text=text)
                if btn.exists:
                    btn.click()
                    print(f"   🔓 Escaped dialog by clicking '{text}'")
                    logging.debug(f"Escaped dialog: clicked {text}")
                    time.sleep(0.5)
                    return True

            # Segunda tentativa: clicar em Cancel
            for text in self.DIALOG_CANCEL_TEXTS:
                btn = self.device(text=text)
                if btn.exists:
                    btn.click()
                    print(f"   🔓 Escaped dialog by clicking '{text}'")
                    logging.debug(f"Escaped dialog: clicked {text}")
                    time.sleep(0.5)
                    return True

            # Terceira tentativa: pressionar Back
            self.device.press("back")
            print("   🔓 Escaped dialog by pressing Back")
            logging.debug("Escaped dialog: pressed back")
            time.sleep(0.5)
            return True

        except Exception as e:
            logging.debug(f"Error escaping dialog: {e}")

        return False

    def _check_stuck(self, activity):
        """Verifica se está preso na mesma tela por muito tempo (steps ou segundos)."""
        current_time = time.time()
        time_in_activity = current_time - self.activity_start_time

        if activity == self.last_activity:
            self.same_activity_count += 1
        else:
            self.same_activity_count = 0
            self.last_activity = activity
            self.escape_attempts = 0  # Reset escape attempts quando muda de activity
            self.activity_start_time = current_time  # Reset timer quando muda de activity

        # Verifica stuck por TEMPO (prioridade mais alta)
        if time_in_activity >= self.max_time_same_activity:
            print(
                f"   ⏰ TIME LIMIT: Stuck in {activity} for {time_in_activity:.0f}s (max: {self.max_time_same_activity}s)"
            )
            print("   🏠 Forcing return to app home due to time limit...")
            self._return_to_app_home()
            self.escape_attempts = 0
            self.same_activity_count = 0
            self.activity_start_time = time.time()  # Reset timer
            return True

        # Verifica stuck por STEPS
        if self.same_activity_count >= self.max_same_activity:
            self.escape_attempts += 1
            print(
                f"   ⚠️ Stuck in {activity} for {self.same_activity_count} steps, {time_in_activity:.0f}s (attempt {self.escape_attempts}/{self.max_escape_attempts})"
            )

            # Se já tentou escapar muitas vezes, volta para home do app
            if self.escape_attempts >= self.max_escape_attempts:
                print("   🏠 Too many escape attempts, returning to app home...")
                self._return_to_app_home()
                self.escape_attempts = 0
                self.same_activity_count = 0
                self.activity_start_time = time.time()  # Reset timer
                return True

            # Verifica se está em dialog
            is_dialog, dialog_type = self._detect_dialog()
            if is_dialog:
                print(f"   📅 Detected {dialog_type}, attempting escape...")
                self._escape_dialog()
            else:
                # Tenta pressionar back para sair
                self.device.press("back")
                print("   🔙 Pressed back to escape stuck state")

            self.same_activity_count = 0
            return True

        return False

    def _return_to_app_home(self):
        """Força o retorno para a tela inicial do app."""
        try:
            # Método 1: Force stop e reiniciar o app
            print("   🔄 Force stopping and restarting app...")
            self._exec(f"adb shell am force-stop {self.app_package}")
            time.sleep(0.5)

            # Reinicia o app
            self._exec(f"adb shell monkey -p {self.app_package} 1")
            time.sleep(1)

            # Atualiza first_activity se necessário
            activity = self._get_activity()
            if self.first_activity == "":
                self.first_activity = activity

            # Limpa ações do test case atual
            self.tc_action = []

            os.makedirs(self.test_case_path, exist_ok=True)
            with open(f"{self.test_case_path}/{self.nametc}", mode="a") as file:
                file.write("\n\n🏠 Returned to app home (stuck recovery)")

            logging.debug("Returned to app home due to stuck state")
            print(f"   ✅ App restarted at: {activity}")

        except Exception as e:
            logging.debug(f"Error returning to app home: {e}")
            print(f"   ❌ Error returning to home: {e}")
            # Fallback: múltiplos backs
            for _ in range(5):
                self.device.press("back")
                time.sleep(0.3)

    @staticmethod
    def _exec(command):
        """Execute a shell command."""
        call(command, shell=True, stdout=FNULL)

    def _get_actions(self, activity):
        """Get available actions for the current screen."""
        device_actions = [
            "home",
            "back",
            "volume_up",
            "volume_down",
            "mute",
            "rotate_l",
            "rotate_r",
            "menu",
        ]
        actions = []
        action_tc = []
        action_text = []
        edits = []

        try:
            xml = self.device.dump_hierarchy()
            tree = ET.fromstring(xml)
        except Exception as e:
            logging.debug(f"Error getting UI hierarchy: {e}")
            print("   ⚠️ Error getting UI hierarchy, returning empty actions")
            return actions

        empty = []
        probBack = 0.05

        editText = tree.findall('.//node[@class="android.widget.EditText"]')
        scrollable = tree.findall('.//node[@scrollable="true"]')
        longclicable = tree.findall('.//node[@long-clickable="true"]')
        clickable = tree.findall('.//node[@clickable="true"]')
        checkable = tree.findall('.//node[@checkable="true"]')

        if self.tc_action != empty:
            for tc in enumerate(self.tc_action):
                if activity == tc[1].activity:
                    action_tc.append(
                        tc[1].elem + "," + tc[1].action_type + "," + tc[1].action_subtype
                    )
                    if tc[1].action_type == "EditText" or tc[1].action_type == "type":
                        action_text.append(tc[1].elem)

        if self.edittexts != empty:
            for row in self.edittexts:
                if activity in row:
                    edits.append(row)

        # Process EditText elements
        if editText != empty:
            self._process_edit_text(editText, activity, action_text, edits, actions, empty)

        # Process long-clickable elements
        if longclicable != empty:
            self._process_long_clickable(longclicable, activity, action_tc, actions)

        # Process clickable elements
        if clickable != empty:
            self._process_clickable(clickable, activity, action_tc, actions)

        # Process scrollable elements
        if scrollable != empty:
            self._process_scrollable(scrollable, activity, action_tc, actions)

        # Process checkable elements
        if checkable != empty:
            self._process_checkable(checkable, activity, action_tc, actions)

        # Add device actions with probability
        context = round(random.random(), 2)
        if context < probBack:
            print("context device")
            dev = random.choice(device_actions)
            try:
                gui_obj = self.device()[1]
                actions.append(
                    Action(
                        gui_obj,
                        activity,
                        self.nametc,
                        dev,
                        "",
                        "",
                        dev,
                        "",
                        "",
                        "",
                        dev,
                        "",
                        "",
                        "",
                        "",
                        "",
                    )
                )
            except Exception as e:
                print(e)

        # If no actions available, add first action
        if actions == []:
            try:
                gui_obj = self.device()
                actions.append(
                    Action(
                        gui_obj,
                        activity,
                        self.nametc,
                        "first",
                        "",
                        "",
                        "first",
                        "",
                        "",
                        "",
                        "first",
                        "",
                        "",
                        "",
                        "",
                        "",
                    )
                )
            except Exception as e:
                print(e)

        return actions

    def _process_edit_text(self, editText, activity, action_text, edits, actions, empty):
        """Process EditText elements and add corresponding actions."""
        last_class = []
        for edt in editText:
            resourceid = edt.attrib["resource-id"]
            contentdesc = edt.attrib["content-desc"]
            classname = edt.attrib["class"]
            package = edt.attrib["package"]
            bounds = edt.attrib["bounds"]
            elem = f"{classname} {resourceid} {contentdesc} bounds:{bounds}"
            appended = False

            if package == self.app_package:
                if elem not in action_text:
                    if resourceid != "":
                        gui_obj = self.device(resourceId=resourceid)
                        self._add_edit_text_actions(
                            gui_obj, activity, resourceid, elem, edits, actions, empty
                        )
                        appended = True

                    if contentdesc != "" and not appended:
                        gui_obj = self.device(description=contentdesc)
                        self._add_default_text_actions(gui_obj, activity, resourceid, elem, actions)
                        appended = True

                    if not resourceid and not contentdesc and not appended:
                        gui_obj = self.device(className="android.widget.EditText")
                        if classname not in last_class:
                            last_class.append(classname)
                            self._add_default_text_actions(
                                gui_obj, activity, resourceid, elem, actions
                            )

    def _add_edit_text_actions(self, gui_obj, activity, resourceid, elem, edits, actions, empty):
        """Add actions for EditText with requirements."""
        if edits != empty:
            for row in edits:
                if resourceid in row:
                    # Add symbols action
                    actions.append(
                        Action(
                            gui_obj,
                            activity,
                            self.nametc,
                            "EditText",
                            "",
                            resourceid,
                            "type",
                            "",
                            "",
                            "",
                            "symbols",
                            "",
                            "",
                            "",
                            "",
                            elem,
                        )
                    )
                    # Add specific actions based on field type
                    if row[4] == "text":
                        self._add_text_field_actions(gui_obj, activity, row, elem, actions)
                    elif row[4] == "number":
                        self._add_number_field_actions(gui_obj, activity, row, elem, actions)
        else:
            self._add_default_text_actions(gui_obj, activity, resourceid, elem, actions)

    def _add_text_field_actions(self, gui_obj, activity, row, elem, actions):
        """Add actions for text fields."""
        subtypes = [
            "tc_text",
            "text_start_size",
            "text_greater_end_size",
            "text_end_size",
            "numberMedium",
        ]
        if int(row[5]) > 1:
            subtypes.insert(1, "text_less1_start_size")
        for subtype in subtypes:
            actions.append(
                Action(
                    gui_obj,
                    activity,
                    self.nametc,
                    row[1],
                    row[4],
                    row[2],
                    row[3],
                    row[5],
                    row[6],
                    row[7],
                    subtype,
                    row[8],
                    row[9],
                    row[10],
                    row[11],
                    elem,
                )
            )

    def _add_number_field_actions(self, gui_obj, activity, row, elem, actions):
        """Add actions for number fields."""
        subtypes = [
            "tc_number",
            "number_start_size",
            "number_greater_end_size",
            "number_end_size",
            "textMedium",
        ]
        if int(row[5]) > 1:
            subtypes.insert(1, "number_less1_start_size")
        for subtype in subtypes:
            actions.append(
                Action(
                    gui_obj,
                    activity,
                    self.nametc,
                    row[1],
                    row[4],
                    row[2],
                    row[3],
                    row[5],
                    row[6],
                    row[7],
                    subtype,
                    row[8],
                    row[9],
                    row[10],
                    row[11],
                    elem,
                )
            )

    def _add_default_text_actions(self, gui_obj, activity, resourceid, elem, actions):
        """Add default text input actions."""
        subtypes = [
            "textSmall",
            "textLarge",
            "textMedium",
            "numberSmall",
            "numberMedium",
            "numberLarge",
            "symbols",
        ]
        for subtype in subtypes:
            actions.append(
                Action(
                    gui_obj,
                    activity,
                    self.nametc,
                    "EditText",
                    "",
                    resourceid,
                    "type",
                    "",
                    "",
                    "",
                    subtype,
                    "",
                    "",
                    "",
                    "",
                    elem,
                )
            )

    def _process_long_clickable(self, longclicable, activity, action_tc, actions):
        """Process long-clickable elements."""
        last_class = []
        for clk in longclicable:
            text = clk.attrib["text"]
            resourceid = clk.attrib["resource-id"]
            contentdesc = clk.attrib["content-desc"]
            classname = clk.attrib["class"]
            package = clk.attrib["package"]
            bounds = clk.attrib["bounds"]
            appended = False
            elem = f"{classname} {resourceid} {contentdesc} {text} bounds:{bounds}"

            if package == self.app_package and classname != "android.widget.EditText":
                elem_tc = f"{elem},long-click,center"
                if text != "":
                    gui_obj = self.device(text=text)
                    for gui in gui_obj:
                        count_child = safe_get_child_count(gui, self.device)
                        if elem_tc not in action_tc:
                            target = gui.child() if count_child > 0 else gui
                            actions.append(
                                Action(
                                    target,
                                    activity,
                                    self.nametc,
                                    "longclickable",
                                    "",
                                    resourceid,
                                    "long-click",
                                    "",
                                    "",
                                    "",
                                    "center",
                                    "",
                                    "",
                                    "",
                                    "",
                                    elem,
                                )
                            )
                            appended = True

                if resourceid and not appended:
                    gui_obj = self.device(resourceId=resourceid)
                    if elem_tc not in action_tc:
                        count_child = safe_get_child_count(gui_obj, self.device)
                        target = gui_obj.child() if count_child > 0 else gui_obj
                        actions.append(
                            Action(
                                target,
                                activity,
                                self.nametc,
                                "longclickable",
                                "",
                                resourceid,
                                "long-click",
                                "",
                                "",
                                "",
                                "center",
                                "",
                                "",
                                "",
                                "",
                                elem,
                            )
                        )
                        appended = True

                if not resourceid and not contentdesc and not text and not appended:
                    gui_obj = self.device(longClickable=True)
                    if classname not in last_class:
                        last_class.append(classname)
                        if elem_tc not in action_tc:
                            actions.append(
                                Action(
                                    gui_obj,
                                    activity,
                                    self.nametc,
                                    "longclickable",
                                    "",
                                    resourceid,
                                    "long-click",
                                    "",
                                    "",
                                    "",
                                    "center",
                                    "",
                                    "",
                                    "",
                                    "",
                                    elem,
                                )
                            )

    def _process_clickable(self, clickable, activity, action_tc, actions):
        """Process clickable elements."""
        last_class = []
        for cl in clickable:
            text = cl.attrib["text"]
            resourceid = cl.attrib["resource-id"]
            contentdesc = cl.attrib["content-desc"]
            classname = cl.attrib["class"]
            package = cl.attrib["package"]
            bounds = cl.attrib["bounds"]
            appended = False
            elem = f"{classname} {resourceid} {contentdesc} {text} bounds:{bounds}"
            elem_tc = f"{elem},click,click"

            if package == self.app_package and classname != "android.widget.EditText":
                if (elem_tc not in action_tc) or (resourceid in self.buttons):
                    if text:
                        gui_obj = self.device(text=text)
                        for gui in gui_obj:
                            count_child = safe_get_child_count(gui, self.device)
                            target = gui.child() if count_child > 0 else gui
                            actions.append(
                                Action(
                                    target,
                                    activity,
                                    self.nametc,
                                    "clickable",
                                    "",
                                    resourceid,
                                    "click",
                                    "",
                                    "",
                                    "",
                                    "click",
                                    "",
                                    "",
                                    "",
                                    text,
                                    elem,
                                )
                            )
                            appended = True

                    if resourceid and not appended:
                        gui_obj = self.device(resourceId=resourceid)
                        count_child = safe_get_child_count(gui_obj, self.device)
                        target = gui_obj.child() if count_child > 0 else gui_obj
                        actions.append(
                            Action(
                                target,
                                activity,
                                self.nametc,
                                "clickable",
                                "",
                                resourceid,
                                "click",
                                "",
                                "",
                                "",
                                "click",
                                "",
                                "",
                                "",
                                text,
                                elem,
                            )
                        )
                        appended = True

                    if contentdesc and not appended:
                        gui_obj = self.device(description=contentdesc)
                        count_child = safe_get_child_count(gui_obj, self.device)
                        target = gui_obj.child() if count_child > 0 else gui_obj
                        actions.append(
                            Action(
                                target,
                                activity,
                                self.nametc,
                                "clickable",
                                "",
                                resourceid,
                                "click",
                                "",
                                "",
                                "",
                                "click",
                                "",
                                "",
                                "",
                                text,
                                elem,
                            )
                        )
                        appended = True

                    if not resourceid and not contentdesc and not text and not appended:
                        gui_obj = self.device(clickable=True)
                        if classname not in last_class:
                            last_class.append(classname)
                            for gui in gui_obj:
                                count_child = safe_get_child_count(gui, self.device)
                                target = gui.child() if count_child > 0 else gui
                                actions.append(
                                    Action(
                                        target,
                                        activity,
                                        self.nametc,
                                        "clickable",
                                        "",
                                        resourceid,
                                        "click",
                                        "",
                                        "",
                                        "",
                                        "click",
                                        "",
                                        "",
                                        "",
                                        text,
                                        elem,
                                    )
                                )

    def _process_scrollable(self, scrollable, activity, action_tc, actions):
        """Process scrollable elements."""
        last_class = []
        for sr in scrollable:
            text = sr.attrib["text"]
            resourceid = sr.attrib["resource-id"]
            contentdesc = sr.attrib["content-desc"]
            classname = sr.attrib["class"]
            package = sr.attrib["package"]
            bounds = sr.attrib["bounds"]
            elem = f"{classname} {resourceid} {contentdesc} {text} bounds:{bounds}"

            if package == self.app_package:
                gui_obj = self.device(className=classname, scrollable=True)
                if classname not in last_class:
                    last_class.append(classname)
                    for direction in ["up", "down", "right", "left"]:
                        elem_tc = f"{elem},scroll,{direction}"
                        if elem_tc not in action_tc:
                            actions.append(
                                Action(
                                    gui_obj,
                                    activity,
                                    self.nametc,
                                    "scrollable",
                                    "",
                                    resourceid,
                                    "scroll",
                                    "",
                                    "",
                                    "",
                                    direction,
                                    "",
                                    "",
                                    "",
                                    "",
                                    elem,
                                )
                            )

    def _process_checkable(self, checkable, activity, action_tc, actions):
        """Process checkable elements."""
        last_class = []
        for check in checkable:
            text = check.attrib["text"]
            resourceid = check.attrib["resource-id"]
            contentdesc = check.attrib["content-desc"]
            classname = check.attrib["class"]
            package = check.attrib["package"]
            bounds = check.attrib["bounds"]
            elem = f"{classname} {resourceid} {contentdesc} {text} bounds:{bounds}"
            elem_tc = f"{elem},check,check"
            appended = False

            if package == self.app_package:
                if elem_tc not in action_tc:
                    if resourceid:
                        gui_obj = self.device(resourceId=resourceid)
                        actions.append(
                            Action(
                                gui_obj,
                                activity,
                                self.nametc,
                                "checkable",
                                "",
                                resourceid,
                                "check",
                                "",
                                "",
                                "",
                                "check",
                                "",
                                "",
                                "",
                                text,
                                elem,
                            )
                        )
                        appended = True

                    if contentdesc and not appended:
                        gui_obj = self.device(description=contentdesc)
                        actions.append(
                            Action(
                                gui_obj,
                                activity,
                                self.nametc,
                                "checkable",
                                "",
                                resourceid,
                                "check",
                                "",
                                "",
                                "",
                                "check",
                                "",
                                "",
                                "",
                                text,
                                elem,
                            )
                        )
                        appended = True

                    if text and not appended:
                        gui_obj = self.device(text=text)
                        actions.append(
                            Action(
                                gui_obj,
                                activity,
                                self.nametc,
                                "checkable",
                                "",
                                resourceid,
                                "check",
                                "",
                                "",
                                "",
                                "check",
                                "",
                                "",
                                "",
                                text,
                                elem,
                            )
                        )
                        appended = True

                    if not resourceid and not contentdesc and not text and not appended:
                        gui_obj = self.device(className=classname, clickable=True)
                        if classname not in last_class:
                            last_class.append(classname)
                            actions.append(
                                Action(
                                    gui_obj,
                                    activity,
                                    self.nametc,
                                    "checkable",
                                    "",
                                    resourceid,
                                    "check",
                                    "",
                                    "",
                                    "",
                                    "check",
                                    "",
                                    "",
                                    "",
                                    text,
                                    elem,
                                )
                            )

    def _get_screen(self):
        """Capture the current screen."""
        self.device.screenshot("state.png")
        timestr = time.strftime("%Y%m%d-%H%M%S")
        img_name = f"{self.screenshots_path}/state_{timestr}.png"
        shutil.copy("state.png", img_name)

        tc_file_path = f"{self.test_case_path}/{self.nametc}"
        if os.path.exists(tc_file_path):
            with open(tc_file_path, mode="a") as file:
                file.write(f"\n  Screen: {img_name}")

        img = imread("state.png")
        return self._image_to_torch(img)

    @staticmethod
    def _image_to_torch(image):
        """Convert image to PyTorch tensor."""
        screen_transposed = image.transpose((2, 0, 1))
        screen_scaled = np.ascontiguousarray(screen_transposed, dtype=np.float32) / 255
        torch_img = torch.from_numpy(screen_scaled)
        return resize(torch_img).unsqueeze(0).to(device)

    def _get_current_coverage(self):
        """Get current code coverage by triggering broadcast dump then pulling .ec file."""
        try:
            # Explicit broadcast (required for Android 8+)
            call(
                f"adb shell am broadcast "
                f"-n {self.app_package}/.CoverageReceiver "
                f"-a {self.app_package}.DUMP_COVERAGE",
                shell=True, stdout=FNULL, stderr=FNULL,
            )
            # Pull from app-internal storage via run-as (works on all Android versions)
            call(
                f"adb exec-out run-as {self.app_package} cat files/coverage.ec > coverage.ec",
                shell=True, stdout=FNULL, stderr=FNULL,
            )
        except Exception:
            print("Phone Not connected")
            logging.debug("Phone Not connected")
            self.copy_coverage()

    def copy_coverage(self):
        """Copy coverage file with timestamp."""
        if self.coverage_enabled:
            timestr = time.strftime("%Y%m%d-%H%M%S")
            try:
                shutil.copy("coverage.ec", f"{self.coverage_path}/coverage_{timestr}.ec")
            except Exception:
                print("Failed Coverage")

    def get_requirements(self, req_file: str | None = None):
        """Load requirements from CSV file."""
        if req_file is None:
            req_file = str(CONFIG_PATH / "requirements.csv")
        with open(req_file, encoding="utf-8") as csvfile:
            spamreader = csv.reader(csvfile)
            for row in spamreader:
                if "edittext" in row:
                    self.edittexts.append(row)
                if "button" in row:
                    self.buttons.append(row[2])
                self.activities_req.append(row)

    def get_happypath(self, action):
        """Calculate reward for happy path."""
        reward = 0
        for line in self.activities_req:
            if action.activity == line[0]:
                reward = 10
                break
        if action.action_subtype == "tc_text":
            reward = 20
        elif action.action_subtype in {
            "text_start_size",
            "text_end_size",
            "number_start_size",
            "number_end_size",
        }:
            reward = 5
        if action.action_subtype == "click":
            for line in self.buttons:
                if action.resourceid == line:
                    reward = 50
                    break
        return reward

    @staticmethod
    def verify_action(action):
        """Verify action and return reward."""
        reward = 0
        save = "Save"
        ok = "Ok"
        edit = "Edit"
        if action.action_subtype == "click":
            if action.text in (save, save.upper(), save.lower()):
                reward = 20
            if action.text in (ok, ok.lower(), ok.upper()):
                reward = 20
            if action.text in (edit, edit.lower(), edit.upper()):
                reward = 20
        return reward

    def get_crash(self):
        """Check for crashes."""
        timestr = time.strftime("%Y%m%d-%H%M%S")
        crash_txt = f"{self.crashes_path}/crash.txt"
        previous_line = self.get_lines(crash_txt)
        crash_command = f'adb shell logcat -d | grep "AndroidRuntime: java.lang.RuntimeException: Unable to start activity ComponentInfo" | grep "{self.app_package}"> {crash_txt}'
        new_filecrash = ""
        try:
            call(crash_command, shell=True, stdout=FNULL)
            actual_line = self.get_lines(crash_txt)
            filesize = os.path.getsize(crash_txt)
            if filesize > 0:
                if actual_line > previous_line:
                    new_filecrash = f"crash_{timestr}.txt"
                    shutil.copy(crash_txt, f"{self.crashes_path}/{new_filecrash}")
        except Exception:
            print("Not Executed")
        return new_filecrash

    def get_errors(self):
        """Check for errors."""
        timestr = time.strftime("%Y%m%d-%H%M%S")
        errors_txt = f"{self.errors_path}/errors.txt"
        previous_line = self.get_lines(errors_txt)
        errors_command = (
            f'adb shell logcat -s -d "System.err" "*:E" | grep "{self.app_package}"> {errors_txt}'
        )
        new_filerr = ""
        try:
            call(errors_command, shell=True, stdout=FNULL)
            actual_line = self.get_lines(errors_txt)
            filesize = os.path.getsize(errors_txt)
            if filesize > 0:
                if actual_line > previous_line:
                    new_filerr = f"error_{timestr}.txt"
                    shutil.copy(errors_txt, f"{self.errors_path}/{new_filerr}")
        except Exception:
            print("Not executed")
        return new_filerr

    @staticmethod
    def get_lines(txt):
        """Count lines in a file."""
        try:
            with open(txt, encoding="utf-8") as f:
                line_count = 0
                for _ in f:
                    line_count += 1
            return line_count
        except FileNotFoundError:
            return 0
