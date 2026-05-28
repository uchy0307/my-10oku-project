@echo off
chcp 65001 > nul
title cloudflared tunnel (uchy-pc)
echo === Named tunnel: uchy-pc -> pc.uchy0307.uk ===
cloudflared tunnel run uchy-pc
