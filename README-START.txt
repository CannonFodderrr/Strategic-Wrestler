Strategic Wrestler — Start + auto-update
========================================

Put ALL of these in the SAME folder:

  indexSW.html
  update_and_serve.py
  Start Strategic Wrestler.bat        ← Windows
  Start Strategic Wrestler.command    ← Mac
  Start Strategic Wrestler.sh         ← Linux / Chromebook Linux
  version.txt                         ← optional; auto-created after update
  GITHUB-RELEASES-HOWTO.txt           ← how YOU publish updates

Server:  http://localhost:2231/indexSW.html


HOW UPDATES WORK
----------------
On start, the launcher asks GitHub for the latest Release on:
  CannonFodderrr/Strategic-Wrestler
If newer, it overwrites indexSW.html, then starts the server.

You must publish a GitHub Release and ATTACH indexSW.html
(see GITHUB-RELEASES-HOWTO.txt). Pushing only to main is not enough.


WINDOWS
-------
Double-click "Start Strategic Wrestler.bat"
Install Python 3 from python.org if needed (check "Add to PATH")
Keep the window open while using SW


MAC
---
chmod +x "Start Strategic Wrestler.command"
Double-click the .command file
Allow in Privacy & Security if blocked


CHROMEBOOK (Linux)
------------------
Enable Linux, copy folder into Linux files, Terminal:
  chmod +x "Start Strategic Wrestler.sh"
  ./Start\ Strategic\ Wrestler.sh


GOOGLE OAUTH
------------
Authorized JavaScript origin:
  http://localhost:2231


OFFLINE
-------
  python update_and_serve.py --offline
