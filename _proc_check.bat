@echo off
tasklist /FI "IMAGENAME eq python.exe" > C:\Users\user\Documents\10oku-project\_proc_check.txt 2>&1
echo --- cmd: >> C:\Users\user\Documents\10oku-project\_proc_check.txt
tasklist /FI "IMAGENAME eq cmd.exe" >> C:\Users\user\Documents\10oku-project\_proc_check.txt 2>&1
echo --- voicevox: >> C:\Users\user\Documents\10oku-project\_proc_check.txt
tasklist /FI "IMAGENAME eq voicevox.exe" >> C:\Users\user\Documents\10oku-project\_proc_check.txt 2>&1
echo --- engine: >> C:\Users\user\Documents\10oku-project\_proc_check.txt
tasklist /FI "IMAGENAME eq voicevox_engine.exe" >> C:\Users\user\Documents\10oku-project\_proc_check.txt 2>&1
echo --- run-py: >> C:\Users\user\Documents\10oku-project\_proc_check.txt
tasklist /FI "IMAGENAME eq run_pipeline_night.py" >> C:\Users\user\Documents\10oku-project\_proc_check.txt 2>&1
