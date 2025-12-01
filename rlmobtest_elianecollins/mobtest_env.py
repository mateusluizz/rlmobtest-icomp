#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr 29 17:16:49 2023

@author: eliane
"""

import csv

# from torch.utils.tensorboard import SummaryWriter
# writer = SummaryWriter()
import logging
import os
import random

# import timeit
import shutil

# import timeit
import string
import time
import xml.etree.ElementTree as ET

# from torch.utils.tensorboard import SummaryWriter
# writer = SummaryWriter()
from subprocess import call

import numpy as np
import torch
import torchvision.transforms as T
import uiautomator2 as u2
from matplotlib.pyplot import imread
from PIL import Image

from constants import TEST_CASES_PATH
from rlmobtest_elianecollins import conf

# import pandas as pd


FNULL = open(os.devnull, "w")


settings_reader = conf.ConfRead("settings.txt")
lines = settings_reader.read_setting()
apk = lines[0]
app_package = lines[1]
cov = lines[4]


class Action:
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
        test_case_path: str = TEST_CASES_PATH,
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
        self.test_case_path = test_case_path

    def execute(
        self,
        nametc,
    ):
        with open(f"{self.test_case_path}/{nametc}", "a", encoding="utf-8") as file:
            if self.action_type == "first":
                env.device.press("back")
                env._exec("adb shell am start -n " + env.first_activity)
                env.tc_action = []
                file.write("\n\nHome activity")
                print("Home activity")

            if self.action_type == "back":
                env.device.press("back")
                file.write("\n\nBack Pressed")
                print("Back Pressed")
                logging.debug("back pressed")
            if self.action_type == "home":
                env.device.press("home")
                file.write("\n\nHome Pressed")
                print("Home Pressed")
                logging.debug("home pressed")
            if self.action_type == "menu":
                env.device(scrollable=True).scroll.to(text="Menu")
                file.write("\n\nMenu Pressed")
                print("Menu Pressed")
                logging.debug("menu pressed")
            if self.action_type == "volume_up":
                env.device.press("volume_up")
                file.write("\n\nVolume Up Pressed")
                print("Volume Up Pressed")
                logging.debug("volume up pressed")
            if self.action_type == "volume_down":
                env.device.press("volume_down")
                file.write("\n\nVolume Down Pressed")
                print("Volume Down Pressed")
                logging.debug("volume down pressed")
            if self.action_type == "mute":
                env.device.press("volume_mute")
                file.write("\n\nVolume mute Pressed")
                print("Volume mute Pressed")
                logging.debug("volume mute pressed")
            if self.action_type == "rotate_l":
                env.device.set_orientation("l")
                file.write("\n\nRotate left Pressed")
                print("Rotate left Pressed")
                logging.debug("Rotate left pressed")
            if self.action_type == "rotate_r":
                env.device.set_orientation("r")  # Define a orientação para a direita
                file.write("\n\nRotate right Pressed")
                print("Rotate right Pressed")
                logging.debug("Rotate right pressed")

            if self.action_type == "scroll":
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
                        env.device.swipe(
                            0.8, 0.5, 0.2, 0.5
                        )  # Desliza da direita para a esquerda
                        file.write("\n\nScroll right " + self.elem)
                        logging.debug("Scroll right " + self.elem)
                        print("Scroll right " + self.elem)
                    if self.action_subtype == "left":
                        env.device.swipe(
                            0.2, 0.5, 0.8, 0.5
                        )  # Desliza da esquerda para a direita
                        file.write("\n\nScroll left " + self.elem)
                        logging.debug("Scroll left " + self.elem)
                        print("Scroll left " + self.elem)
                except Exception as e:
                    logging.debug("Error Scroll " + str(e))
                    print("Error Scroll " + str(e))
                    env._exec("adb shell am start -n " + self.activity)

            if self.action_type == "long-click":
                try:
                    if self.action_subtype == "center":
                        self.gui_object.long_click(duration=1.0)
                        file.write("\n\nLong click center " + self.elem)
                        logging.debug("Long click center " + self.elem)
                        print("Long click center " + self.elem)
                    if self.action_subtype == "topleft":
                        self.gui_object.long_click(
                            duration=1.0
                        )  # Não há suporte nativo para "corner"
                        file.write("\n\nLong click top left " + self.elem)
                        logging.debug("Long click top left " + self.elem)
                        print("Long click top left " + self.elem)
                    if self.action_subtype == "bottomright":
                        self.gui_object.long_click(duration=1.0)  # Mesma correção
                        file.write("\n\nLong click bottom right " + self.elem)
                        logging.debug("Long click bottom right " + self.elem)
                        print("Long click bottom right " + self.elem)
                except Exception as e:
                    logging.debug("Error long click " + str(e))
                    print("Error long click " + str(e))

            if self.action_type == "check":
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

            if self.action_type == "click":
                try:
                    self.gui_object.click()
                    file.write(f"\n\nClicked {self.elem}")
                    logging.debug(f"Click: {self.elem}")
                    print(f"Click: {self.elem}")
                except Exception as e:
                    logging.debug(f"Error click {str(e)}")
                    print(f"Error click {str(e)}")

                    # PAREI AQUI
            if self.action_type == "type":
                try:
                    if self.action_subtype == "tc_text":
                        if self.value:
                            self.gui_object.send_keys(self.value)
                            file.write(
                                f"\n\ntyped in {self.resourceid} value: {self.value}"
                            )
                            logging.debug(f"type: {self.resourceid} {self.value}")
                            print(f"type: {self.resourceid} {self.value}")

                    if self.action_subtype == "text_less1_start_size":
                        letters = string.ascii_letters
                        result_str = "".join(
                            random.choice(letters)
                            for _ in range(int(self.size_start) - 1)
                        )
                        self.gui_object.send_keys(result_str)
                        file.write(
                            f"\n\ntyped in {self.resourceid} value: {result_str}"
                        )
                        file.write(
                            f"\n\nExpected min size {self.size_start} Actual value: {result_str}"
                        )
                        logging.debug(f"type: {self.resourceid} {result_str}")
                        print(f"type: {self.resourceid} {result_str}")

                    if self.action_subtype == "text_start_size":
                        letters = string.ascii_letters
                        result_str = "".join(
                            random.choice(letters) for _ in range(int(self.size_start))
                        )
                        self.gui_object.send_keys(result_str)
                        file.write(
                            f"\n\ntyped in {self.resourceid} value: {result_str}"
                        )
                        logging.debug(f"type: {self.resourceid} {result_str}")
                        print(f"type: {self.resourceid} {result_str}")

                    if self.action_subtype == "text_greater_end_size":
                        letters = string.ascii_letters
                        result_str = "".join(
                            random.choice(letters)
                            for _ in range(int(self.size_end) + 1)
                        )
                        self.gui_object.send_keys(result_str)
                        file.write(
                            f"\n\ntyped in {self.resourceid} value: {result_str}"
                        )
                        file.write(
                            f"\n\nExpected max size {self.size_end} Actual value: {result_str}"
                        )
                        logging.debug(f"type: {self.resourceid} {result_str}")
                        print(f"type: {self.resourceid} {result_str}")

                    if self.action_subtype == "text_end_size":
                        letters = string.ascii_letters
                        result_str = "".join(
                            random.choice(letters) for _ in range(int(self.size_end))
                        )
                        self.gui_object.send_keys(result_str)
                        file.write(
                            f"\n\ntyped in {self.resourceid} value: {result_str}"
                        )
                        logging.debug(f"type: {self.resourceid} {result_str}")
                        print(f"type: {self.resourceid} {result_str}")

                    if self.action_subtype == "tc_number":
                        if self.value != "":
                            self.gui_object.send_keys(self.value)
                            file.write(
                                f"\n\ntyped in {self.resourceid} value: {self.value}"
                            )
                            logging.debug(f"type: {self.resourceid} {self.value}")
                            print(f"type: {self.resourceid} {self.value}")

                    if self.action_subtype == "number_less1_start_size":
                        number = string.digits
                        if int(self.size_start) == 1:
                            result_str = "0"
                        elif int(self.size_start) > 1:
                            result_str = "".join(
                                random.choice(number)
                                for _ in range(int(self.size_start) - 1)
                            )
                        self.gui_object.send_keys(result_str)
                        file.write(
                            f"\n\ntyped in {self.resourceid} value: {result_str}"
                        )
                        file.write(
                            f"\n\nExpected min size {self.size_start} Actual value: {result_str}"
                        )
                        logging.debug(f"type: {self.resourceid} {result_str}")
                        print(f"type: {self.resourceid} {result_str}")

                    if self.action_subtype == "number_start_size":
                        number = string.digits
                        result_str = "".join(
                            random.choice(number) for _ in range(int(self.size_start))
                        )
                        self.gui_object.send_keys(result_str)
                        file.write(
                            f"\n\ntyped in {self.resourceid} value: {result_str}"
                        )
                        logging.debug(f"type: {self.resourceid} {result_str}")
                        print(f"type: {self.resourceid} {result_str}")

                    if self.action_subtype == "number_end_size":
                        number = string.digits
                        result_str = "".join(
                            random.choice(number) for _ in range(int(self.size_end))
                        )
                        self.gui_object.send_keys(result_str)
                        file.write(
                            f"\n\ntyped in {self.resourceid} value: {result_str}"
                        )
                        logging.debug(f"type: {self.resourceid} {result_str}")
                        print(f"type: {self.resourceid} {result_str}")

                    if self.action_subtype == "number_greater_end_size":
                        number = string.digits
                        result_str = "".join(
                            random.choice(number) for _ in range(int(self.size_end) + 1)
                        )
                        self.gui_object.send_keys(result_str)
                        file.write(
                            f"\n\ntyped in {self.resourceid} value: {result_str}"
                        )
                        file.write(
                            f"\n\nExpected max size {self.size_end} Actual value: {result_str}"
                        )
                        logging.debug(f"type: {self.resourceid} {result_str}")
                        print(f"type: {self.resourceid} {result_str}")

                    if self.action_subtype == "textLarge":
                        letters = string.ascii_letters
                        result_str = "".join(random.choice(letters) for _ in range(100))
                        self.gui_object.send_keys(result_str)
                        file.write(f"\n\ntyped in {self.elem} value: {result_str}")
                        logging.debug(f"type: {self.elem} {result_str}")
                        print(f"type: {self.elem} {result_str}")

                    if self.action_subtype == "textSmall":
                        letters = string.ascii_letters
                        result_str = "".join(random.choice(letters) for _ in range(1))
                        self.gui_object.send_keys(result_str)
                        file.write(f"\n\ntyped in {self.elem} value: {result_str}")
                        logging.debug(f"type: {self.elem} {result_str}")
                        print(f"type: {self.elem} {result_str}")

                    if self.action_subtype == "textMedium":
                        letters = string.ascii_letters
                        result_str = "".join(random.choice(letters) for _ in range(10))
                        self.gui_object.send_keys(result_str)
                        file.write(f"\n\ntyped in {self.elem} value: {result_str}")
                        logging.debug(f"type: {self.elem} {result_str}")
                        print(f"type: {self.elem} {result_str}")

                    if self.action_subtype == "numberSmall":
                        letters = string.digits
                        result_str = "".join(random.choice(letters) for _ in range(1))
                        self.gui_object.send_keys(result_str)
                        file.write(f"\n\ntyped in {self.elem} value: {result_str}")
                        logging.debug(f"type: {self.elem} {result_str}")
                        print(f"type: {self.elem} {result_str}")

                    if self.action_subtype == "numberMedium":
                        letters = string.digits
                        result_str = "".join(random.choice(letters) for _ in range(2))
                        self.gui_object.send_keys(result_str)
                        file.write(f"\n\ntyped in {self.elem} value: {result_str}")
                        logging.debug(f"type: {self.elem} {result_str}")
                        print(f"type: {self.elem} {result_str}")

                    if self.action_subtype == "numberLarge":
                        letters = string.digits
                        result_str = "".join(random.choice(letters) for _ in range(20))
                        self.gui_object.send_keys(result_str)
                        file.write(f"\n\ntyped in {self.elem} value: {result_str}")
                        logging.debug(f"type: {self.elem} {result_str}")
                        print(f"type: {self.elem} {result_str}")

                    if self.action_subtype == "symbols":
                        letters = string.punctuation
                        result_symbols = "".join(
                            random.choice(letters) for _ in range(10)
                        )
                        self.gui_object.send_keys(result_symbols)
                        file.write(f"\n\ntyped in {self.elem} value: {result_symbols}")
                        logging.debug(f"type: {self.elem} {result_symbols}")
                        print(f"type: {self.elem} {result_symbols}")

                    if self.action_subtype == "mixed":
                        letters_and_digits = string.ascii_letters + string.digits
                        result_str = "".join(
                            random.choice(letters_and_digits) for _ in range(15)
                        )
                        self.gui_object.send_keys(result_str)
                        file.write(f"\n\ntyped in {self.elem} value: {result_str}")
                        logging.debug(f"type: {self.elem} {result_str}")
                        print(f"type: {self.elem} {result_str}")

                except Exception as e:
                    logging.debug(f"Error edit {e}")
                    print(f"Error edit {e}")
                    env._exec(f"adb shell am start -n {self.activity}")


resize = T.Compose(
    [T.ToPILImage(), T.Resize(38, interpolation=Image.Resampling.BICUBIC), T.ToTensor()]
)


# PAREI AQUI
class AndroidEnv:
    def __init__(self, app, app_package):
        self.app = app
        self.app_package = app_package
        self.device = u2.connect()
        self.tc_action = []
        self.first_activity = ""
        self.nametc = "start.txt"
        # self.screen_size = screen_size
        self._exec("ng ng-cp lib/org.jacoco.ant-0.8.5-nodeps.jar")
        self._exec("ng ng-cp ")
        self._exec("adb forward tcp:8981 tcp:8981")
        self.edittexts = []
        self.buttons = []
        self.activities_req = []
        self.test_case_path: str = (TEST_CASES_PATH,)

    def reset(self):
        open("std.txt", "w").close()
        self._exec(f"adb shell am force-stop {self.app_package}")
        # self._exec("adb shell pm clear {self.app_package}")
        self._exec(f"adb shell monkey -p {self.app_package} 1")
        activity = self._get_activity()
        self.first_activity = activity
        return self._get_screen(), self._get_actions(activity)

    def install_app(self):
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
        self._exec(f"adb shell monkey -p {self.app_package} 1")

    def _create_tcfile(self, activity):
        timestr = time.strftime("%Y%m%d-%H%M%S")
        x = list(activity)
        bar = "/"
        if bar in x:
            act = activity.split(bar)
            namefile = "TC_" + act[1] + "_" + timestr + ".txt"
        else:
            act = activity
            namefile = "TC_" + act + "_" + timestr + ".txt"

        if not os.path.exists(f"{self.test_case_path}/{namefile}"):
            with open(f"{self.test_case_path}/{namefile}", "w+") as file:
                file.write(f"Test Case{activity}")

        return namefile

    def _get_activity(self):
        try:
            with open("std.txt", "w", encoding="utf-8") as file:
                # proc = subprocess.Popen(['adb logcat | grep --line-buffered ActivityInfo > std.txt'], stdout=subprocess.PIPE, shell=True)
                self._exec(
                    "adb shell dumpsys activity recents | grep 'ActivityRecord' > std.txt"
                )
                for line in file.readlines():
                    if self.app_package in line:
                        x = line.split(",")
                        break
                act = x[-1]
                act = act.split(" ")
                for content in enumerate(act):
                    if self.app_package in content:
                        activityname = content
                        break
                indices = [i for i, s in enumerate(act) if self.app_package in s]
                if len(indices) == 0:
                    activityname = "outapp"
                else:
                    activityname = act[indices[0]]
        except Exception:
            activityname = "home"
        return activityname

    def step(self, action):
        self.tc_action.append(action)

        crash = False

        self._get_foreground()
        action.execute(self.nametc)
        if cov == "yes":
            self._get_current_coverage()
        # print("Coverage: ",coverage)
        # logging.debug("coverage:"+ str(coverage))
        # done = coverage >= 0.9

        file_crash = self.get_crash()
        file_error = self.get_errors()

        activity = self._get_activity()

        if activity == "outapp":
            self.device.press("back")
            self._get_foreground()
            activity = self._get_activity()

        if file_crash != "":
            filesizec = os.path.getsize("crashes/" + file_crash)
            if filesizec > 0:
                crash = True
                file = open(f"{self.test_case_path}{self.nametc}", mode="a")
                file.write("\n\nGot Crash, see crashes/" + file_crash)
                print("crash == true")
                self.copy_coverage()
                logging.debug("crash == true")

        if file_error != "":
            filesizerr = os.path.getsize("errors/" + file_error)
            if filesizerr > 0:
                file = open(f"{self.test_case_path}{self.nametc}", mode="a")
                file.write("\n\nGot Error, see errors/" + file_error)
                logging.debug("error:" + file_error)
                print("errors == true")

        return self._get_screen(), self._get_actions(activity), crash, activity

    @staticmethod
    def _exec(command):
        call(command, shell=True, stdout=FNULL)

    def _get_actions(self, activity):
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
        xml = self.device.dump_hierarchy()
        tree = ET.fromstring(xml)
        empty = []
        probBack = 0.05
        editText = tree.findall('.//node[@class="android.widget.EditText"]')
        scrollable = tree.findall('.//node[@scrollable="true"]')
        longclicable = tree.findall('.//node[@long-clickable="true"]')
        clickable = tree.findall('.//node[@clickable="true"]')
        checkable = tree.findall('.//node[@checkable="true"]')
        # listview =  tree.findall('.//node[@class="android.widget.ListView"]')
        if self.tc_action != empty:
            for tc in enumerate(self.tc_action):
                if activity == tc[1].activity:
                    action_tc.append(
                        tc[1].elem
                        + ","
                        + tc[1].action_type
                        + ","
                        + tc[1].action_subtype
                    )
                    if tc[1].action_type == "EditText" or tc[1].action_type == "type":
                        action_text.append(tc[1].elem)

        if self.edittexts != empty:
            for row in self.edittexts:
                if activity in row:
                    edits.append(row)

        if editText != empty:  # noqa: PLR1702
            last_class = []
            for edt in editText:
                resourceid = edt.attrib["resource-id"]
                contentdesc = edt.attrib["content-desc"]
                classname = edt.attrib["class"]
                package = edt.attrib["package"]
                bounds = edt.attrib["bounds"]
                elem = (
                    classname
                    + " "
                    + resourceid
                    + " "
                    + contentdesc
                    + " bounds:"
                    + bounds
                )
                appended = False

                if package == app_package:
                    if elem not in action_text:
                        if resourceid != "":
                            gui_obj = self.device(resourceId=resourceid)
                            if edits != empty:
                                for row in edits:
                                    if resourceid in row:
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
                                        if row[4] == "text":
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
                                                    "tc_text",
                                                    row[8],
                                                    row[9],
                                                    row[10],
                                                    row[11],
                                                    elem,
                                                )
                                            )
                                            if int(row[5]) > 1:
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
                                                        "text_less1_start_size",
                                                        row[8],
                                                        row[9],
                                                        row[10],
                                                        row[11],
                                                        elem,
                                                    )
                                                )
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
                                                    "text_start_size",
                                                    row[8],
                                                    row[9],
                                                    row[10],
                                                    row[11],
                                                    elem,
                                                )
                                            )
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
                                                    "text_greater_end_size",
                                                    row[8],
                                                    row[9],
                                                    row[10],
                                                    row[11],
                                                    elem,
                                                )
                                            )
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
                                                    "text_end_size",
                                                    row[8],
                                                    row[9],
                                                    row[10],
                                                    row[11],
                                                    elem,
                                                )
                                            )
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
                                                    "numberMedium",
                                                    row[8],
                                                    row[9],
                                                    row[10],
                                                    row[11],
                                                    elem,
                                                )
                                            )
                                            appended = True
                                        elif row[4] == "number":
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
                                                    "tc_number",
                                                    row[8],
                                                    row[9],
                                                    row[10],
                                                    row[11],
                                                    elem,
                                                )
                                            )
                                            if int(row[5]) > 1:
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
                                                        "number_less1_start_size",
                                                        row[8],
                                                        row[9],
                                                        row[10],
                                                        row[11],
                                                        elem,
                                                    )
                                                )
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
                                                    "number_start_size",
                                                    row[8],
                                                    row[9],
                                                    row[10],
                                                    row[11],
                                                    elem,
                                                )
                                            )
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
                                                    "number_greater_end_size",
                                                    row[8],
                                                    row[9],
                                                    row[10],
                                                    row[11],
                                                    elem,
                                                )
                                            )
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
                                                    "number_end_size",
                                                    row[8],
                                                    row[9],
                                                    row[10],
                                                    row[11],
                                                    elem,
                                                )
                                            )
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
                                                    "textMedium",
                                                    row[8],
                                                    row[9],
                                                    row[10],
                                                    row[11],
                                                    elem,
                                                )
                                            )
                                            appended = True

                            else:
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
                                        "textSmall",
                                        "",
                                        "",
                                        "",
                                        "",
                                        elem,
                                    )
                                )
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
                                        "textLarge",
                                        "",
                                        "",
                                        "",
                                        "",
                                        elem,
                                    )
                                )
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
                                        "textMedium",
                                        "",
                                        "",
                                        "",
                                        "",
                                        elem,
                                    )
                                )
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
                                        "numberSmall",
                                        "",
                                        "",
                                        "",
                                        "",
                                        elem,
                                    )
                                )
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
                                        "numberMedium",
                                        "",
                                        "",
                                        "",
                                        "",
                                        elem,
                                    )
                                )
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
                                        "numberLarge",
                                        "",
                                        "",
                                        "",
                                        "",
                                        elem,
                                    )
                                )
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
                                appended = True

                        if contentdesc != "" and not appended:
                            gui_obj = self.device(description=contentdesc)

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
                                    "textSmall",
                                    "",
                                    "",
                                    "",
                                    "",
                                    elem,
                                )
                            )
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
                                    "textLarge",
                                    "",
                                    "",
                                    "",
                                    "",
                                    elem,
                                )
                            )
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
                                    "textMedium",
                                    "",
                                    "",
                                    "",
                                    "",
                                    elem,
                                )
                            )
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
                                    "numberSmall",
                                    "",
                                    "",
                                    "",
                                    "",
                                    elem,
                                )
                            )
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
                                    "numberMedium",
                                    "",
                                    "",
                                    "",
                                    "",
                                    elem,
                                )
                            )
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
                                    "numberLarge",
                                    "",
                                    "",
                                    "",
                                    "",
                                    elem,
                                )
                            )
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
                            appended = True

                        if not resourceid and not contentdesc and not appended:
                            gui_obj = self.device(className="android.widget.EditText")
                            if classname not in last_class:
                                last_class.append(classname)
                                if len(gui_obj) > 1:
                                    for gui in gui_obj:
                                        count_child = gui.info["childCount"]
                                        if count_child > 0:
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
                                                    "textSmall",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                                    "textLarge",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                                    "textMedium",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                                    "numberSmall",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                                    "numberMedium",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                                    "numberLarge",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                            appended = True
                                        else:
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
                                                    "textSmall",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                                    "textLarge",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                                    "textMedium",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                                    "numberSmall",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                                    "numberMedium",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                                    "numberLarge",
                                                    "",
                                                    "",
                                                    "",
                                                    "",
                                                    elem,
                                                )
                                            )
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
                                            appended = True
                                else:
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
                                            "textSmall",
                                            "",
                                            "",
                                            "",
                                            "",
                                            elem,
                                        )
                                    )
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
                                            "textLarge",
                                            "",
                                            "",
                                            "",
                                            "",
                                            elem,
                                        )
                                    )
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
                                            "textMedium",
                                            "",
                                            "",
                                            "",
                                            "",
                                            elem,
                                        )
                                    )
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
                                            "numberSmall",
                                            "",
                                            "",
                                            "",
                                            "",
                                            elem,
                                        )
                                    )
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
                                            "numberMedium",
                                            "",
                                            "",
                                            "",
                                            "",
                                            elem,
                                        )
                                    )
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
                                            "numberLarge",
                                            "",
                                            "",
                                            "",
                                            "",
                                            elem,
                                        )
                                    )
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
                                    appended = True
        if longclicable != empty:  # noqa: PLR1702
            last_class = []
            for clk in longclicable:
                text = clk.attrib["text"]
                resourceid = clk.attrib["resource-id"]
                contentdesc = clk.attrib["content-desc"]
                classname = clk.attrib["class"]
                package = clk.attrib["package"]
                bounds = clk.attrib["bounds"]
                appended = False
                elem = (
                    classname
                    + " "
                    + resourceid
                    + " "
                    + contentdesc
                    + " "
                    + text
                    + " bounds:"
                    + bounds
                )

                if package == app_package and classname != "android.widget.EditText":
                    # if elem_tc not in action_tc:
                    if text != "":
                        gui_obj = self.device(text=text)
                        for gui in gui_obj:
                            count_child = gui.info["childCount"]
                            # if gui_obj.count==1:
                            if count_child > 0:
                                elem_tc = elem + "," + "long-click" + "," + "center"
                                if elem_tc not in action_tc:
                                    actions.append(
                                        Action(
                                            gui.child(),
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

                                # elem_tc = elem+","+"long-click"+","+'topleft'
                                # if elem_tc not in action_tc:
                                #     actions.append(Action(gui.child(), activity, 'longclickable', "",resourceid,"long-click","","","",'topleft',"","","",elem))
                                #     appended = True

                                # elem_tc = elem+","+"long-click"+","+'bottomright'
                                # if elem_tc not in action_tc:
                                #     actions.append(Action(gui.child(), activity, 'longclickable', "",resourceid,"long-click","","","",'bottomright',"","","",elem))
                                #     appended = True
                            else:
                                elem_tc = elem + "," + "long-click" + "," + "center"
                                if elem_tc not in action_tc:
                                    actions.append(
                                        Action(
                                            gui,
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

                                # elem_tc = elem+","+"long-click"+","+'bottomright'
                                # if elem_tc not in action_tc:
                                #     actions.append(Action(gui, activity, 'longclickable', "",resourceid,"long-click","","","",'bottomright',"","","",elem))
                                #     appended = True

                                # elem_tc = elem+","+"long-click"+","+'topleft'
                                # if elem_tc not in action_tc:
                                #     actions.append(Action(gui, activity, 'longclickable', "",resourceid,"long-click","","","",'topleft',"","","",elem))
                                #     appended = True

                    if resourceid and not appended:
                        gui_obj = self.device(resourceId=resourceid)
                        count_child = gui_obj.info["childCount"]
                        # if gui_obj.count==0:
                        if count_child > 0:
                            elem_tc = elem + "," + "long-click" + "," + "center"
                            if elem_tc not in action_tc:
                                actions.append(
                                    Action(
                                        gui_obj.child(),
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

                            # elem_tc = elem+","+"long-click"+","+'topleft'
                            # if elem_tc not in action_tc:
                            #     actions.append(Action(gui_obj.child(), activity, 'longclickable', "",resourceid,"long-click","","","",'topleft',"","","",elem))
                            #     appended = True

                            # elem_tc = elem+","+"long-click"+","+'bottomright'
                            # if elem_tc not in action_tc:
                            #     actions.append(Action(gui_obj, activity, 'longclickable', "",resourceid,"long-click","","","",'bottomright',"","","",elem))
                            #     appended = True

                    if not resourceid and not contentdesc and not text and not appended:
                        gui_obj = self.device(longClickable=True)
                        if classname not in last_class:
                            last_class.append(classname)
                            if len(gui_obj) > 1:
                                for gui in gui_obj:
                                    count_child = gui.info["childCount"]
                                    if count_child > 0:
                                        elem_tc = (
                                            elem + "," + "long-click" + "," + "center"
                                        )
                                        if elem_tc not in action_tc:
                                            actions.append(
                                                Action(
                                                    gui.child(),
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

                                        # elem_tc = elem+","+"long-click"+","+'topleft'
                                        # if elem_tc not in action_tc:
                                        #     actions.append(Action(gui.child(), activity, 'longclickable', "",resourceid,"long-click","","","",'topleft',"","","",elem))
                                        #     appended = True

                                        # elem_tc = elem+","+"long-click"+","+'bottomright'
                                        # if elem_tc not in action_tc:
                                        #     actions.append(Action(gui, activity, 'longclickable', "",resourceid,"long-click","","","",'bottomright',"","","",elem))
                                        #     appended = True
                            else:
                                elem_tc = elem + "," + "long-click" + "," + "center"
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
                                    appended = True

                                # elem_tc = elem+","+"long-click"+","+'bottomright'
                                # if elem_tc not in action_tc:
                                #     actions.append(Action(gui_obj, activity, 'longclickable', "",resourceid,"long-click","","","",'bottomright',"","","",elem))
                                #     appended = True

                                # elem_tc = elem+","+"long-click"+","+'topleft'
                                # if elem_tc not in action_tc:
                                #     actions.append(Action(gui_obj, activity, 'longclickable', "",resourceid,"long-click","","","",'topleft',"","","",elem))
                                #     appended = True

        if clickable != empty:  # noqa: PLR1702
            last_class = []
            for cl in clickable:
                text = cl.attrib["text"]
                resourceid = cl.attrib["resource-id"]
                contentdesc = cl.attrib["content-desc"]
                classname = cl.attrib["class"]
                package = cl.attrib["package"]
                bounds = cl.attrib["bounds"]
                appended = False
                # if (classname != "android.widget.Button") and (classname != "android.widget.ImageButton"):
                elem = (
                    classname
                    + " "
                    + resourceid
                    + " "
                    + contentdesc
                    + " "
                    + text
                    + " bounds:"
                    + bounds
                )
                elem_tc = elem + "," + "click" + "," + "click"
                if package == app_package and classname != "android.widget.EditText":
                    if (elem_tc not in action_tc) or (resourceid in self.buttons):
                        if text:
                            gui_obj = self.device(text=text)
                            for gui in gui_obj:
                                count_child = gui.info["childCount"]
                                # if gui_obj.count==0:
                                if count_child > 0:
                                    actions.append(
                                        Action(
                                            gui.child(),
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
                                else:
                                    actions.append(
                                        Action(
                                            gui,
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
                            count_child = gui_obj.info["childCount"]
                            # if gui_obj.count==0:
                            if count_child > 0:
                                actions.append(
                                    Action(
                                        gui_obj.child(),
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
                            else:
                                actions.append(
                                    Action(
                                        gui_obj,
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
                            count_child = gui_obj.info["childCount"]
                            # if gui_obj.count==0:
                            if count_child > 0:
                                actions.append(
                                    Action(
                                        gui_obj.child(),
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
                            else:
                                actions.append(
                                    Action(
                                        gui_obj,
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

                        if (
                            not resourceid
                            and not contentdesc
                            and not text
                            and not appended
                        ):
                            gui_obj = self.device(clickable=True)
                            if classname not in last_class:
                                last_class.append(classname)
                                # print(gui_obj.info)
                                if len(gui_obj) > 1:
                                    for gui in gui_obj:
                                        count_child = gui.info["childCount"]
                                        if count_child > 0:
                                            actions.append(
                                                Action(
                                                    gui.child(),
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
                                        else:
                                            actions.append(
                                                Action(
                                                    gui,
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
                                else:
                                    actions.append(
                                        Action(
                                            gui_obj,
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

        if scrollable != empty:  # noqa: PLR1702
            last_class = []
            for sr in scrollable:
                text = sr.attrib["text"]
                resourceid = sr.attrib["resource-id"]
                contentdesc = sr.attrib["content-desc"]
                classname = sr.attrib["class"]
                package = sr.attrib["package"]
                bounds = sr.attrib["bounds"]
                elem = (
                    classname
                    + " "
                    + resourceid
                    + " "
                    + contentdesc
                    + " "
                    + text
                    + " bounds:"
                    + bounds
                )

                if package == app_package:
                    gui_obj = self.device(className=classname, scrollable=True)
                    if classname not in last_class:
                        last_class.append(classname)
                        for gui in gui_obj:
                            elem_tc = elem + "," + "scroll" + "," + "up"
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
                                        "up",
                                        "",
                                        "",
                                        "",
                                        "",
                                        elem,
                                    )
                                )
                            elem_tc = elem + "," + "scroll" + "," + "down"
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
                                        "down",
                                        "",
                                        "",
                                        "",
                                        "",
                                        elem,
                                    )
                                )
                            elem_tc = elem + "," + "scroll" + "," + "right"
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
                                        "right",
                                        "",
                                        "",
                                        "",
                                        "",
                                        elem,
                                    )
                                )
                            elem_tc = elem + "," + "scroll" + "," + "left"
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
                                        "left",
                                        "",
                                        "",
                                        "",
                                        "",
                                        elem,
                                    )
                                )

        if checkable != empty:  # noqa: PLR1702
            for check in checkable:
                text = check.attrib["text"]
                resourceid = check.attrib["resource-id"]
                contentdesc = check.attrib["content-desc"]
                classname = check.attrib["class"]
                package = check.attrib["package"]
                bounds = check.attrib["bounds"]
                elem = (
                    classname
                    + " "
                    + resourceid
                    + " "
                    + contentdesc
                    + " "
                    + text
                    + " bounds:"
                    + bounds
                )
                elem_tc = elem + "," + "check" + "," + "check"
                appended = False
                if package == app_package:
                    if elem_tc not in action_tc:
                        if resourceid:
                            gui_obj = self.device(resourceId=resourceid)
                            actions.append(
                                Action(
                                    gui_obj,
                                    activity,
                                    self.nametc,
                                    "checkacle",
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
                        if (
                            not resourceid
                            and not contentdesc
                            and not text
                            and not appended
                        ):
                            gui_obj = self.device(className=classname, clickable=True)
                            if classname not in last_class:
                                last_class.append(classname)
                                for gui in gui_obj:
                                    count_child = gui.info["childCount"]
                                    if count_child > 0:
                                        actions.append(
                                            Action(
                                                gui_obj.child(),
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
                                    else:
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
        # device actions
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
                        resourceid,
                        dev,
                        "",
                        "",
                        "",
                        dev,
                        "",
                        "",
                        "",
                        "",
                        elem,
                    )
                )
                # actions.append(Action(gui_obj,activity, 'home', "",resourceid,"home","","","",'home',"","","",elem))
                # actions.append(Action(gui_obj,activity, 'menu', "",resourceid,"menu","","","",'menu',"","","",elem))
                # actions.append(Action(gui_obj,activity, 'volume_up', "",resourceid,"volume_up","","","",'volume_up',"","","",elem))
                # actions.append(Action(gui_obj,activity, 'rotate_l', "",resourceid,"rotate_l","","","",'rotate_l',"","","",elem))
                # actions.append(Action(gui_obj,activity, 'mute', "",resourceid,"mute","","","",'mute',"","","",elem))
            except Exception as e:
                print(e)

        # dev = random.choice(device_actions)
        if actions == []:
            # self._exec("adb shell am start -n "+self.first_activity)
            try:
                gui_obj = self.device()
                # dev = random.choice(device_actions)
                actions.append(
                    Action(
                        gui_obj,
                        activity,
                        self.nametc,
                        "first",
                        "",
                        resourceid,
                        "first",
                        "",
                        "",
                        "",
                        "first",
                        "",
                        "",
                        "",
                        "",
                        elem,
                    )
                )
            except Exception as e:
                print(e)

        return actions

    def _get_screen(self):
        self.device.screenshot("state.png")
        timestr = time.strftime("%Y%m%d-%H%M%S")
        img_name = "states/state_" + timestr + ".png"
        shutil.copy("state.png", img_name)
        if os.path.exists(f"{self.test_case_path}{self.nametc}"):
            file = open(f"{self.test_case_path}{self.nametc}", mode="a")
            file.write("  Screen: " + img_name)
        img = imread("state.png")
        return self._image_to_torch(img)

    @staticmethod
    def _image_to_torch(image):
        # img_resized = misc.imresize(image, size=0.1)
        screen_transposed = image.transpose((2, 0, 1))
        screen_scaled = np.ascontiguousarray(screen_transposed, dtype=np.float32) / 255
        torch_img = torch.from_numpy(screen_scaled)
        return resize(torch_img).unsqueeze(0).to(d)

    def _get_current_coverage(self):
        # start_time = timeit.default_timer()
        try:
            call("adb pull /sdcard/coverage.ec  ", shell=True, stdout=FNULL)
            # generate_report_cmd = f'java -cp lib/org.jacoco.ant-0.8.5-nodeps.jar:. ReportGenerator "{APP_UNDER_TEST_ROOT}"'
            # call(generate_report_cmd, shell=True, stdout=FNULL)
            # self._exec(generate_report_cmd)
        except Exception:
            print("Phone Not connected")
            logging.debug("Phone Not connected")
            self.copy_coverage()

    # df = pd.read_csv("report.csv")
    # missed, covered = df[['LINE_MISSED', 'LINE_COVERED']].sum()
    # print(f"Complete in {timeit.default_timer() - start_time} seconds")
    # logging.debug(f"Complete in {timeit.default_timer() - start_time} seconds")
    # return covered / (missed + covered)

    @staticmethod
    def copy_coverage():
        if cov == "yes":
            timestr = time.strftime("%Y%m%d-%H%M%S")
            try:
                shutil.copy("coverage.ec", "coverage/coverage_" + timestr + ".ec")
                # shutil.copy("report.csv","report_"+timestr+".csv")
                # print("Coverage Copy Ok")
            except Exception:
                print("Failed Coverage")

    def get_requirements(self):
        with open("req.csv", encoding="utf-8") as csvfile:
            spamreader = csv.reader(csvfile)
            for row in spamreader:
                if "edittext" in row:
                    self.edittexts.append(row)
                if "button" in row:
                    self.buttons.append(row[2])
                self.activities_req.append(row)
        # return self.edittexts, self.buttons

    def get_happypath(self, action):
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
        reward = 0
        save = "Save"
        ok = "Ok"
        edit = "Edit"
        if action.action_subtype == "click":
            if (
                action.text == save
                or action.text == save.upper()
                or action.text == save.lower()
            ):
                reward = 20
            if (
                action.text == ok
                or action.text == ok.lower()
                or action.text == ok.upper()
            ):
                reward = 20
            if (
                action.text == edit
                or action.text == edit.lower()
                or action.text == edit.upper()
            ):
                reward = 20
        return reward

    def get_crash(self):
        timestr = time.strftime("%Y%m%d-%H%M%S")
        previous_line = self.get_lines("crashes/crash.txt")
        crash_command = f'adb shell logcat -d | grep "AndroidRuntime: java.lang.RuntimeException: Unable to start activity ComponentInfo" | grep "{self.app_package}"> crashes/crash.txt'
        try:
            call(crash_command, shell=True, stdout=FNULL)
            actual_line = self.get_lines("crashes/crash.txt")
            new_filecrash = ""
            filesize = os.path.getsize("crashes/crash.txt")
            if filesize > 0:
                if actual_line > previous_line:
                    new_filecrash = "crash_" + timestr + ".txt"
                    shutil.copy("crashes/crash.txt", "crashes/" + new_filecrash)
        except Exception:
            print("Not Executed")
        return new_filecrash

    def get_errors(self):
        timestr = time.strftime("%Y%m%d-%H%M%S")
        previous_line = self.get_lines("errors/errors.txt")
        errors_command = f'adb shell logcat -s -d "System.err" "*:E" | grep "{self.app_package}"> errors/errors.txt'
        try:
            call(errors_command, shell=True, stdout=FNULL)
            actual_line = self.get_lines("errors/errors.txt")
            new_filerr = ""
            filesize = os.path.getsize("errors/errors.txt")
            if filesize > 0:
                if actual_line > previous_line:
                    new_filerr = "error_" + timestr + ".txt"
                    shutil.copy("errors/errors.txt", "errors/" + new_filerr)
        except Exception:
            print("Not executed")
        return new_filerr

    def get_lines(self, txt):
        with open(txt, encoding="utf-8") as f:
            line_count = 0
            for _ in f:
                line_count += 1
        return line_count


d = torch.device("cuda" if torch.cuda.is_available() else "cpu")
env = AndroidEnv(apk, app_package)
