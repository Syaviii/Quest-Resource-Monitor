# Quest Monitor

real-time performance tracking for quest 3 + pc during game dev + usb and wireless adb support.

## What it does

monitors cpu, ram, temp, battery, disk, network on both your pc and quest 3 at the same time. useful if you're optimizing a vr game and need to see what's happening on the headset while you're running it.

logs everything so you can review sessions later. supports usb or wireless adb (wireless requires sideloading the adb package on quest).

## how wireless works

1. plug in quest via usb
2. app runs `adb tcpip 5555` and such automatically
3. app finds the quest's ip and connects wirelessly
4. unplug usb, stay wireless (if the wireless adb package is installed or been setup on your device)

if you don't have the wireless package sideloaded, just use usb, preferably the link cable

## Features

- real-time metrics (cpu, ram, disk, temp, battery, network)
- usb or wireless adb (auto-switches)
- record data for analysis
- export recordings to csv/json
- configurable polling rate
- unique dark theme

## What's not done yet/known issues

- electron app isnt fully setup and packaged yet!!!
- gpu monitoring (alot of cases to cover and no clear way to monitor the quest's gpu yet)
- thermal breakdown (no clear way to monitor the thermal zones yet)
- wireless adb drops and can have issues reconnecting after being left idle (Issue due to how the quest sleeps, no fix but can try to make reconnection stable)
- network stats are fucked up!!!
- quest storage stats are not implemented yet as for some reason theres no clear way to mount or monitor it?

## tech stack

**backend:**
- flask 
- sqlite 
- psutil 
- adb 
- few tested setups needed specificy quest's adb drivers: [found here](https://developers.meta.com/horizon/downloads/package/oculus-adb-drivers/)

**frontend:**
- vanilla js 
- chart.js 
- electron 

## performance

- polling every 10 seconds by default (configurable)
- metrics are cached, api calls are instant
- database cleanup runs automatically (old data deleted after 48 hours)
- 50mb disk space for 48 hours of data

## Future maybes

- screen streaming and recording?
- app specific usage metrics
- support other devices (not just quest tracking)
- gpu metrics if a nonhacky way shows up
- compare exported data
- alerts/thresholds


