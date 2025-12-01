#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr 29 19:20:52 2023

@author: eliane
"""

#import pandas as pd


class ConfRead:
    
    def __init__(self, settingsfile):
        self.settingsfile = settingsfile
        
        
    def read_setting(self):
       try:
           with open(self.settingsfile, "r") as f1:
               for line in f1:

                   if "APK NAME:" in line:
                       temp =str(line).split(":")
                       temp1 = temp[1].split("\n")
                       app = temp1[0]
                   if "PACKAGE:" in line:
                       temp = str(line).split(":")
                       temp1=temp[1].split("\n")
                       app_package = temp1[0]
                   if "RESOLUTION:" in line:
                       temp = str(line).split(":")
                       temp1 = str(temp[1]).split("x")
                       temp2 = temp1[1].split("\n")
                       wid = temp1[0]
                       hei = temp2[0]
                   if "COVERAGE:" in line:
                       temp = str(line).split(":")
                       temp1=temp[1].split("\n")
                       cov = temp1[0]
                   if "REQUIREMENT:" in line:
                       temp = str(line).split(":")
                       temp1=temp[1].split("\n")
                       req = temp1[0]
                   if "TIME:" in line:
                      temp = str(line).split(":")
                      temp1=temp[1].split("\n")
                      time_exec = temp1[0]
           return(app, app_package,wid,hei,cov,req,time_exec)
       
       except FileNotFoundError:
           print("File Settings not found at root path")
    


