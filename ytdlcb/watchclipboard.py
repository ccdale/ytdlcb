#!/usr/bin/env python3
"""Watches the system clipboard for youtube urls: GUI version."""
import os
import pyperclip  # type: ignore
from pyperclip import waitForNewPaste
import PySimpleGUIQt as sg  # type: ignore

# import PySimpleGUI as sg
import queue
import subprocess
import threading
import time
import sys

from ccaconfig.config import ccaConfig  # type: ignore

# import ytdlcb

appname = "ytdlcb"

sg.theme("DarkGreen2")

cbstatus = ""
faileddl = []


def notifyQSize(qsize):
    items = "item" if qsize == 1 else "items"
    msg = f"{qsize} {items} on download Queue"
    notify("Clipboard Watcher", msg)


def notify(title, message):
    cmd = ["notify-send", f"{title}", f"{message}"]
    subprocess.run(cmd)


def getUrl(cfg, url):
    try:
        global cbstatus, faileddl
        cbstatus = f"downloading {url}"
        notify("Clipboard Watcher", cbstatus)
        os.chdir(cfg["incoming"])
        # cmd = [cfg["youtubedl"], "--cookies", "/home/chris/src/ytdlcb/cookies.txt", url]
        cmd = [cfg["youtubedl"], url]
        res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        if res.returncode == 0:
            cbstatus = f"{url} downloaded successfully"
        else:
            cbstatus = f"Failed {url}: {res.stederr.decode()}"
            faileddl.append(url)
        notify("Clipboard Watcher", cbstatus)
    except Exception as e:
        cbstatus = f"Exception in getUrl: {e}: {res}"
        notify("Clipboard Watcher Error", cbstatus)
        with open("failedurls", "a") as ofp:
            ofp.write(f"{url}\n")


def doYouTube(cfg, Q):
    global cbstatus
    try:
        while True:
            if Q.empty():
                time.sleep(1)
            else:
                iurl = Q.get()
                if iurl == "STOP":
                    # print("STOP found")
                    Q.task_done()
                    break
                tmp = iurl.split("&")
                url = tmp[0]
                getUrl(cfg, url)
                Q.task_done()
                qsize = f"{Q.qsize()} items on the Queue."
                notify("Clipboard Watcher", qsize)
        # print("doYoutTube Child is exiting")
    except Exception as e:
        cbstatus = f"Exception in doYouTube: {e}"
        notify("Clipboard Watcher", cbstatus)
        sys.exit(1)


def updateYoutubedl(cfg):
    layout = [[sg.Text("Checking for an updated youtube-dl")]]
    win = sg.Window("Please wait ...", layout)
    win.Finalize()
    cmd = [cfg["youtubedl"], "-U"]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    stderr = res.stderr.decode().strip()
    stdout = res.stdout.decode().strip()
    msg = ""
    if len(stderr) > 0:
        msg += f" stderr: {stderr}"
    if len(stdout) > 0:
        msg += f" {stdout}"
    win.close()
    sg.popup_timed(msg, auto_close_duration=10)
    return msg


def watchClipBoard(cfg, Q, ev):
    global cbstatus
    cbstatus = f"Watching clipboard: {Q.qsize()} items on Q"
    thread = threading.Thread(target=doYouTube, args=[cfg, Q])
    thread.start()
    while True:
        try:
            txt = waitForNewPaste(1)
        except pyperclip.PyperclipTimeoutException:
            if ev.is_set():
                # print("watcher Stop found")
                # print("putting stop on q")
                Q.put("STOP")
                break
            continue
        if txt.startswith("https://www.youtube.com/watch"):
            Q.put(txt)
            notifyQSize(Q.qsize())
        elif txt.startswith("https://youtu.be/"):
            Q.put(txt)
            notifyQSize(Q.qsize())
        # elif txt.startswith("https://www.itv.com/hub/"):
        #     Q.put(txt)
        #     notifyQSize(Q.qsize())
    # print("waiting for child to exit")
    thread.join()
    # print("doYouTube child has exited")


def saveQ(Q, fn):
    qlist = []
    while not Q.empty():
        qlist.append(Q.get())
    with open(fn, "w") as ofp:
        for cn, line in enumerate(qlist):
            ofp.write(f"{line}\n")
    return cn


def loadQ(Q, fn):
    cn = 0
    if os.path.exists(fn):
        with open(fn, "r") as ifp:
            ilines = ifp.readlines()
            # print(ilines)
            # sys.exit(0)
            lines = [line.strip() for line in ilines]
            for cn, line in enumerate(lines):
                Q.put(line)
    return cn


def main():
    global cbstatus, faileddl
    notify("COOKIES", "Don't forget to update /home/chris/src/ytdlcb/cookies.txt")
    userd = os.environ.get("HOME", os.path.expanduser("~"))
    defd = {
        "incoming": "/".join([userd]),
        "youtubedl": "/".join([userd, "bin/youtube-dl"]),
        "savedqueue": "/".join([userd, ".config/ytdlcb.save"]),
    }
    cf = ccaConfig(appname=appname, defaultd=defd)
    cfg = cf.envOverride()

    # ### restore this line when building package
    # updateYoutubedl(cfg)
    # ### end of restore this line

    Q = queue.Queue()

    ev = threading.Event()
    ev.clear()
    fred = threading.Thread(target=watchClipBoard, name="watcher", args=[cfg, Q, ev])
    fred.start()

    menu_def = [
        "BLANK",
        ["&Status", "---", "&Load Queue", "Save &Queue", "---", "E&xit"],
    ]
    tray = sg.SystemTray(
        menu=menu_def,
        filename=r"images/ytdlcb.png",
        tooltip="Youtube-dl clipboard watcher",
    )

    while True:  # The event loop
        menu_item = tray.read()
        # print(menu_item)
        if menu_item == "Exit":
            # print("Setting stop")
            ev.set()
            break
        elif menu_item == "Status":
            qsize = f"{Q.qsize()} items on the Queue."
            sg.popup(qsize, cbstatus)
        elif menu_item == "Load Queue":
            lqs = loadQ(Q, cfg["savedqueue"])
            msg = f"{lqs} items loaded onto Queue"
            sg.popup(msg)
        elif menu_item == "Save Queue":
            sqs = saveQ(Q, cfg["savedqueue"])
            msg = f"{sqs} items saved from Queue"
            sg.popup(msg, "Quitting now")
            ev.set()
            break
    # print("waiting for watcher to stop")
    fred.join()
    # print("watcher has stopped")
    del tray


if __name__ == "__main__":
    main()
