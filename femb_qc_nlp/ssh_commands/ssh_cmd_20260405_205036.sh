#!/bin/bash
# FEMB QC SSH 命令序列
# 生成时间  : 2026-04-05 20:50:36
# WIB 地址  : root@192.168.121.123
# 基线电压  : 200mV
# 增益      : 14mV/fC
# 成形时间  : 2us
# 输出文件  : RMS_SE_200mVBL_14_0mVfC_2_0us_0x00.bin
# 本地目录  : ./data/20260405_205036
# ──────────────────────────────────────────────────────────

# ── Section 0: WIB 初始化 (time sync + startup) ──────────────
ssh root@192.168.121.123 "date -s '2026-04-06 00:50:36'"  # timeout=15s
ssh root@192.168.121.123 "cd /home/root/BNL_CE_WIB_SW_QC; python3 wib_startup.py"  # timeout=60s

# ── Section 1: FEMB 上电 ─────────────────────────────────────
ssh root@192.168.121.123 "cd /home/root/BNL_CE_WIB_SW_QC; python3 top_femb_powering.py off off off on"  # timeout=120s

# ── Section 2: 原子脚本 (coldata_reset → autocali → fe_cfg → align → acquire) ──
ssh root@192.168.121.123 "cd /home/root/BNL_CE_WIB_SW_QC; PYTHONPATH=/home/root/BNL_CE_WIB_SW_QC python3 /home/root/BNL_CE_WIB_SW_QC/atoms/wib_coldata_reset.py 3"  # timeout=30s
ssh root@192.168.121.123 "cd /home/root/BNL_CE_WIB_SW_QC; PYTHONPATH=/home/root/BNL_CE_WIB_SW_QC python3 /home/root/BNL_CE_WIB_SW_QC/atoms/wib_adc_autocali.py 3"  # timeout=120s
ssh root@192.168.121.123 "cd /home/root/BNL_CE_WIB_SW_QC; PYTHONPATH=/home/root/BNL_CE_WIB_SW_QC python3 /home/root/BNL_CE_WIB_SW_QC/atoms/wib_fe_configure.py 3 --snc 1 --sg0 0 --sg1 0 --st0 1 --st1 1"  # timeout=60s
ssh root@192.168.121.123 "cd /home/root/BNL_CE_WIB_SW_QC; PYTHONPATH=/home/root/BNL_CE_WIB_SW_QC python3 /home/root/BNL_CE_WIB_SW_QC/atoms/wib_data_align.py 3"  # timeout=30s
ssh root@192.168.121.123 "cd /home/root/BNL_CE_WIB_SW_QC; PYTHONPATH=/home/root/BNL_CE_WIB_SW_QC python3 /home/root/BNL_CE_WIB_SW_QC/atoms/wib_acquire.py 3 --samples 10 --output RMS_SE_200mVBL_14_0mVfC_2_0us_0x00.bin"  # timeout=120s

# ── Section 3: 拉取数据到本地 ───────────────────────────────────
scp -r root@192.168.121.123:/home/root/BNL_CE_WIB_SW_QC/QC/ ./data/20260405_205036

# ── Section 4: 清理 WIB 临时数据 ────────────────────────────────
ssh root@192.168.121.123 "rm -rf /home/root/BNL_CE_WIB_SW_QC/QC"

# ── Section 5: FEMB 下电 ─────────────────────────────────────
ssh root@192.168.121.123 "cd /home/root/BNL_CE_WIB_SW_QC; python3 top_femb_powering.py off off off off"  # timeout=60s
