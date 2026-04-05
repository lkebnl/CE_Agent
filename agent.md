# FEMB QC 自然语言驱动测试系统 — 项目需求文档

> **本文档供 Claude Code 阅读并直接生成代码。请按照文档中的规范、接口定义和执行顺序逐步实现。**

---

## 0. 项目背景与目标

### 0.1 系统概述

本项目为 DUNE 实验 FEMB（Front-End Mother Board）冷电子学质量控制（QC）系统构建一个**自然语言驱动的测试代码生成与分析平台**。

用户用中文或英文描述测试需求，系统自动：
1. 解析意图和参数
2. 生成 WIB 测试指令序列
3. 通过 SSH 远程控制 WIB 执行测试
4. 将数据 SCP 回传到 PC
5. 在 PC 本地执行分析并输出结果

### 0.2 物理系统架构

```
PC（Ubuntu，运行 Ollama + Qwen3:8b + 本项目代码）
    │
    │  SSH / SCP（已配置免密）
    ▼
WIB（192.168.121.123，无网络，运行现有 QC 脚本）
    │
    │  C库 ctypes / I2C / 寄存器
    ▼
FEMB 硬件（最多4块，Slot 0~3）
    │
    └── 每块 FEMB：8个 LArASIC 芯片，每芯片16通道，共128通道
```

### 0.3 LArASIC 芯片-通道-丝印映射（固定）

```
Chip 0 → U07 → 全局通道 ch000~ch015
Chip 1 → U17 → 全局通道 ch016~ch031
Chip 2 → U11 → 全局通道 ch032~ch047
Chip 3 → U03 → 全局通道 ch048~ch063
Chip 4 → U19 → 全局通道 ch064~ch079
Chip 5 → U23 → 全局通道 ch080~ch095
Chip 6 → U25 → 全局通道 ch096~ch111
Chip 7 → U21 → 全局通道 ch112~ch127
```

### 0.4 LArASIC 配置参数编码表（来自 Datasheet Table 6）

**基线电压 SNC：**
```
snc=0 → 900mV（感应模式）
snc=1 → 200mV（收集模式）
```

**增益 SG(0,1)：**
```
sg0=0, sg1=0 → 14 mV/fC
sg0=1, sg1=0 → 25 mV/fC
sg0=0, sg1=1 →  7.8 mV/fC
sg0=1, sg1=1 →  4.7 mV/fC
```

**成形时间 ST(0,1)：（注意：与直觉不同）**
```
st0=0, st1=0 → 1.0 us
st0=1, st1=0 → 0.5 us
st0=0, st1=1 → 3.0 us
st0=1, st1=1 → 2.0 us
```

---

## 1. 项目文件结构

```
femb_qc_nlp/
├── README.md
├── requirements.txt
│
├── config/
│   └── femb_info.csv              # 测试基本信息（操作员/slot/环境）
│
├── core/
│   ├── __init__.py
│   ├── femb_constants.py          # 所有常量：映射表、编码表、WIB地址
│   ├── femb_ssh_lib.py            # Layer 0/1/2B：PC侧SSH/SCP封装
│   ├── femb_wib_atoms.py          # Layer 2A：WIB侧原子操作脚本（需SCP到WIB）
│   ├── femb_analysis_lib.py       # Layer 3：PC本地数据分析
│   └── femb_manifest.py           # 采集清单管理（配置↔文件名映射）
│
├── agent/
│   ├── __init__.py
│   ├── femb_nl_agent.py           # Ollama自然语言接口（Qwen3:8b）
│   ├── femb_function_registry.json # 指令注册表（供模型few-shot使用）
│   └── femb_prompt_templates.py   # Prompt模板
│
├── scripts/
│   └── wib_atoms/                 # 需要SCP到WIB的原子脚本
│       ├── wib_adc_autocali.py
│       ├── wib_coldata_reset.py
│       ├── wib_fe_configure.py
│       ├── wib_data_align.py
│       └── wib_acquire.py
│
├── data/                          # PC本地数据存储（自动创建）
│   └── {timestamp}_{femb_id}/
│       ├── RMS/
│       ├── acquisition_manifest.json
│       └── analysis_results/
│
└── tests/
    ├── test_constants.py
    ├── test_ssh_lib.py
    └── test_analysis_lib.py
```

---

## 2. 依赖与环境

### 2.1 requirements.txt

```
numpy>=1.24.0
scipy>=1.10.0
matplotlib>=3.7.0
pandas>=2.0.0
requests>=2.28.0
paramiko>=3.0.0
ollama>=0.1.0
pytest>=7.0.0
```

### 2.2 Ollama 配置

```bash
# Ubuntu 上安装并运行 Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen3:8b
ollama serve  # 默认监听 localhost:11434
```

### 2.3 WIB SSH 配置（已完成，无需密码）

```
WIB IP: 192.168.121.123
WIB user: root
WIB workdir: /home/root/BNL_CE_WIB_SW_QC/
SSH: 免密，无需额外配置
```

---

## 3. 核心模块详细规范

### 3.1 `core/femb_constants.py`

**要求：** 定义所有常量，不含任何业务逻辑。

```python
# WIB 连接
WIB_HOST     = "root@192.168.121.123"
WIB_WORKDIR  = "/home/root/BNL_CE_WIB_SW_QC"
WIB_QC_DIR   = "/home/root/BNL_CE_WIB_SW_QC/QC"
WIB_ATOMS_DIR = "/home/root/BNL_CE_WIB_SW_QC/atoms"  # 原子脚本目录

# Ollama
OLLAMA_HOST  = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:8b"

# 芯片映射表
CHIP_CHANNEL_MAP = {
    0: ("U07",  0,  15),
    1: ("U17", 16,  31),
    2: ("U11", 32,  47),
    3: ("U03", 48,  63),
    4: ("U19", 64,  79),
    5: ("U23", 80,  95),
    6: ("U25", 96, 111),
    7: ("U21",112, 127),
}
SILKSCREEN_TO_CHIP = {v[0]: k for k, v in CHIP_CHANNEL_MAP.items()}

# LArASIC 配置编码
GAIN_MAP = {
    "14mV/fC":  (0, 0),
    "14.0mV/fC":(0, 0),
    "25mV/fC":  (1, 0),
    "25.0mV/fC":(1, 0),
    "7.8mV/fC": (0, 1),
    "4.7mV/fC": (1, 1),
}

PEAKING_MAP = {
    "0.5us": (1, 0),   # st0=1, st1=0
    "0.5μs": (1, 0),
    "1us":   (0, 0),   # st0=0, st1=0  ← 注意不是直觉顺序
    "1.0us": (0, 0),
    "2us":   (1, 1),   # st0=1, st1=1
    "2.0us": (1, 1),
    "3us":   (0, 1),   # st0=0, st1=1
    "3.0us": (0, 1),
}

BASELINE_MAP = {
    "200mV": 1,
    "900mV": 0,
}

# 文件名模板（与现有 QC_runs.py 兼容）
GAIN_TAG = {
    (0,0): "14_0mVfC",
    (1,0): "25_0mVfC",
    (0,1): "7_8mVfC",
    (1,1): "4_7mVfC",
}
PEAKING_TAG = {
    (1,0): "0_5us",
    (0,0): "1_0us",
    (1,1): "2_0us",
    (0,1): "3_0us",
}
BASELINE_TAG = {
    1: "200mVBL",
    0: "900mVBL",
}

# QC item 到函数的映射
QC_ITEM_MAP = {
    1:  "pwr_consumption",
    2:  "pwr_cycle",
    3:  "femb_leakage_cur",
    4:  "femb_chk_pulse",
    5:  "femb_rms",           # ← 当前专注
    6:  "femb_CALI_1",
    7:  "femb_CALI_2",
    8:  "femb_CALI_3",
    9:  "femb_CALI_4",
    10: "femb_MON_1",
    11: "femb_MON_2",
    12: "femb_MON_3",
    13: "femb_CALI_5",
    14: "femb_CALI_6",
    15: "femb_adc_sync_pat",
    16: "femb_test_pattern_pll",
}

# 电流阈值
BIAS_I_LIM = 0.05
FE_I_LOW   = 0.30
CD_I_HIGH  = 0.30

# PC 本地数据根目录
PC_DATA_ROOT = "./data"
```

---

### 3.2 `core/femb_ssh_lib.py`

**要求：** 封装所有 SSH/SCP 操作，每个函数职责单一，有完整日志输出。

#### 接口定义

```python
# ── Layer 0：初始化 ──────────────────────────────────────────────────────────

def wib_ping(timeout: int = 10) -> bool:
    """
    检查 WIB 是否可达。
    返回 True/False。
    实现：subprocess ping -c 3 192.168.121.123
    """

def wib_time_sync() -> bool:
    """
    同步 WIB 系统时间为 PC 当前 UTC 时间。
    实现：SSH: date -s '{formatted_utc_now}'
    """

def wib_startup() -> bool:
    """
    执行 WIB 初始化脚本。
    实现：SSH: cd BNL_CE_WIB_SW_QC; python3 wib_startup.py
    成功标志：stdout 包含 "Done"
    超时：60s
    """

def cfg_push(local_csv: str = "./config/femb_info.csv") -> bool:
    """
    将 femb_info.csv 推送到 WIB 并验证。
    步骤：
      1. SCP: local_csv → root@192.168.121.123:/home/root/BNL_CE_WIB_SW_QC/
      2. SCP回读到 ./readback/femb_info.csv
      3. filecmp 比较，一致返回 True
    """

# ── Layer 1：电源控制 ────────────────────────────────────────────────────────

def femb_power_on(slots: list, env: str = "RT") -> dict:
    """
    上电指定 FEMB slots。
    参数：
      slots: [0,1,2,3] 的子集，如 [0,1]
      env: "RT"（室温）或 "LN"（液氮）
    实现：
      - RT: SSH: python3 top_femb_powering.py {s0} {s1} {s2} {s3}
            其中 si = "on" if i in slots else "off"
      - LN: SSH: python3 top_femb_powering_LN.py {s0} {s1} {s2} {s3}
    返回：
      {'success': bool, 'slot_status': {0: bool, 1: bool, ...}, 'stdout': str}
    成功标志：stdout 包含 'SLOT#{i} Power Connection Normal' for each slot
    超时：150s
    """

def femb_power_off() -> bool:
    """
    关闭所有 FEMB。
    实现：SSH: python3 top_femb_powering.py off off off off
    超时：60s
    """

# ── Layer 2B：完整流程调用（PC组装，SSH执行）──────────────────────────────

def run_full_rms(slots: list, operator: str, env: str = "RT",
                 local_data_dir: str = None) -> dict:
    """
    执行完整 item5 RMS 测试（所有32种配置）。
    等价于现有 QC_top.py -t 5，但输出结构化结果。
    步骤：
      1. 准备 femb_info.csv（含 operator/slots/env）
      2. cfg_push()
      3. SSH: python3 QC_top.py {slot_list} -t 5
             user_input = "{operator}\\n{env_yn}\\nN\\nnote\\n{femb_ids}\\n"
      4. pull_qc_data(local_data_dir)
      5. clean_wib_data()
      6. 生成 acquisition_manifest.json
    返回：
      {'success': bool, 'data_dir': str, 'manifest_path': str, 'configs': list}
    超时：1800s
    """

def run_single_config(slots: list, snc: int, sg0: int, sg1: int,
                      st0: int, st1: int, mode: str = "SE",
                      num_samples: int = 10,
                      local_data_dir: str = None) -> dict:
    """
    执行单一配置的 RMS 采集（Phase 2核心）。
    步骤：
      1. 推送原子脚本到 WIB（atoms目录）
      2. SSH 依次执行：
         a. wib_coldata_reset.py {slots}
         b. wib_adc_autocali.py {slots}
         c. wib_fe_configure.py {slots} {snc} {sg0} {sg1} {st0} {st1}
         d. wib_data_align.py {slots}
         e. wib_acquire.py {slots} {num_samples} {output_fname}
      3. pull_qc_data(local_data_dir)
      4. clean_wib_data()
      5. 生成 acquisition_manifest.json（单条记录）
    返回：
      {'success': bool, 'data_dir': str, 'file': str, 'config': dict}
    """

def run_config_matrix(slots: list, snc_list: list, gain_list: list,
                      peaking_list: list, num_samples: int = 10,
                      local_data_dir: str = None) -> dict:
    """
    执行配置矩阵采集（Phase 2扩展）。
    参数示例：
      snc_list = ["200mV"]
      gain_list = ["14mV/fC", "25mV/fC"]
      peaking_list = ["2us"]
    内部：对每种组合调用 run_single_config()
    返回：
      {'success': bool, 'data_dir': str, 'configs_run': list, 'manifest_path': str}
    """

def pull_qc_data(local_dir: str) -> bool:
    """
    从 WIB 拉取 QC 数据到 PC。
    实现：SCP -r root@192.168.121.123:/home/root/BNL_CE_WIB_SW_QC/QC/ {local_dir}
    """

def clean_wib_data() -> bool:
    """
    清理 WIB 上的临时数据。
    实现：SSH: rm -rf /home/root/BNL_CE_WIB_SW_QC/QC/
    超时：15s
    """

def push_atoms_to_wib() -> bool:
    """
    将 scripts/wib_atoms/ 下的所有原子脚本推送到 WIB。
    实现：SCP -r ./scripts/wib_atoms/ root@192.168.121.123:{WIB_ATOMS_DIR}/
    """
```

#### 内部辅助函数

```python
def _ssh_run(cmd: str, timeout: int = 60,
             user_input: str = None, check: bool = True) -> subprocess.CompletedProcess | None:
    """
    基础 SSH 执行函数。
    command = ["ssh", WIB_HOST, cmd]
    失败返回 None，不抛异常。
    所有调用都用这个函数，统一日志格式：
    [SSH] {cmd[:60]} → returncode={result.returncode}
    """

def _scp_to_wib(local: str, remote: str, timeout: int = 30) -> bool:
    """SCP 上传到 WIB。"""

def _scp_from_wib(remote: str, local: str, timeout: int = 60) -> bool:
    """SCP 从 WIB 下载。"""

def _make_slot_args(slots: list) -> str:
    """[0,2] → 'on off on off'"""
    return " ".join("on" if i in slots else "off" for i in range(4))

def _make_femb_input_str(operator: str, env: str,
                          toy_tpc: str, comment: str,
                          femb_ids: dict) -> str:
    """
    生成 QC_runs 脚本的 stdin 输入字符串。
    对应 QC_runs.__init__() 的 input() 调用序列：
      tester / env(y/n) / toy_TPC(Y/N) / note / FEMB0 ID / FEMB1 ID ...
    """
```

---

### 3.3 `scripts/wib_atoms/` — WIB 侧原子脚本

**要求：** 每个脚本独立可执行，接受命令行参数，在 WIB 上运行。
这些脚本是从 `QC_runs.py` 中提取的最小操作单元。

#### `wib_coldata_reset.py`

```python
"""
用法: python3 wib_coldata_reset.py 0 1 2 3
功能: 执行 COLDATA 复位
来源: QC_runs.femb_rms() → self.chk.femb_cd_rst()
"""
import sys
from wib_cfgs import WIB_CFGS

fembs = [int(x) for x in sys.argv[1:]]
chk = WIB_CFGS()
chk.wib_fw()
chk.femb_cd_rst()
print("Done: coldata_reset fembs={}".format(fembs))
```

#### `wib_adc_autocali.py`

```python
"""
用法: python3 wib_adc_autocali.py 0 1
功能: 执行一次 ADC 自动校准（每次 cd_rst 后必须做一次）
来源: QC_runs.femb_rms() → self.take_data(autocali=1)
"""
import sys, copy
from wib_cfgs import WIB_CFGS

fembs = [int(x) for x in sys.argv[1:]]
chk = WIB_CFGS()
chk.wib_fw()

# 设置 autocali=1
for i in range(8):
    chk.adcs_paras[i][8] = 1
chk.set_fe_board(sts=0, snc=1, sg0=0, sg1=0, st0=1, st1=1, swdac=0, dac=0)

for femb_id in fembs:
    chk.fe_flg[femb_id] = True
    chk.femb_cfg(femb_id, 0)

import time; time.sleep(0.5)

for femb_id in fembs:
    chk.femb_autocali_off(femb_id)

print("Done: adc_autocali fembs={}".format(fembs))
```

#### `wib_fe_configure.py`

```python
"""
用法: python3 wib_fe_configure.py {fembs} --snc 1 --sg0 0 --sg1 0 --st0 1 --st1 1 [--sdd 0] [--sdf 0]
功能: 配置 LArASIC 寄存器（baseline/gain/peaking）
来源: QC_runs.take_data() → set_fe_board() + femb_cfg()

参数说明:
  fembs : 空格分隔的 slot 编号，如 0 1
  --snc : 0=900mV, 1=200mV
  --sg0/sg1 : 增益编码（见常量表）
  --st0/st1 : 成形时间编码（见常量表）
  --sdd : 0=SE模式（默认）, 1=DIFF模式
  --sdf : 0=关闭SE buffer（默认）, 1=开启SE buffer
"""
import sys, copy, time, argparse
from wib_cfgs import WIB_CFGS

ap = argparse.ArgumentParser()
ap.add_argument("fembs", type=int, nargs='+')
ap.add_argument("--snc",  type=int, default=1)
ap.add_argument("--sg0",  type=int, default=0)
ap.add_argument("--sg1",  type=int, default=0)
ap.add_argument("--st0",  type=int, default=1)
ap.add_argument("--st1",  type=int, default=1)
ap.add_argument("--sdd",  type=int, default=0)
ap.add_argument("--sdf",  type=int, default=0)
ap.add_argument("--autocali", type=int, default=1)
args = ap.parse_args()

fembs = args.fembs
chk = WIB_CFGS()
chk.wib_fw()

# 设置 ColdADC 参数
chk.adcs_paras = [
    [c_id, 0x08, 0 if args.sdd == 0 else 1, 0,
     0xDF, 0x33, 0x89, 0x67, args.autocali]
    for c_id in [0x4, 0x5, 0x6, 0x7, 0x8, 0x9, 0xA, 0xB]
]

# 配置 LArASIC
chk.set_fe_board(
    sts=0, snc=args.snc,
    sg0=args.sg0, sg1=args.sg1,
    st0=args.st0, st1=args.st1,
    swdac=0, dac=0x00,
    sdd=args.sdd, sdf=args.sdf
)

cfg_paras_rec = []
for femb_id in fembs:
    chk.fe_flg[femb_id] = True
    chk.adc_flg[femb_id] = True if args.sdd else chk.adc_flg[femb_id]
    cfg_paras_rec.append((femb_id, copy.deepcopy(chk.adcs_paras),
                          copy.deepcopy(chk.regs_int8), 0))
    chk.femb_cfg(femb_id, 0)
    chk.femb_cfg(femb_id, 0)  # 写两次，与 QC_runs 一致

time.sleep(10)  # 等待 LArASIC 稳定

print("Done: fe_configure fembs={} snc={} sg=({},{}) st=({},{})".format(
    fembs, args.snc, args.sg0, args.sg1, args.st0, args.st1))
```

#### `wib_data_align.py`

```python
"""
用法: python3 wib_data_align.py 0 1
功能: 数据链路对齐
来源: QC_runs.take_data() → self.chk.data_align()
"""
import sys
from wib_cfgs import WIB_CFGS

fembs = [int(x) for x in sys.argv[1:]]
chk = WIB_CFGS()
chk.wib_fw()
chk.data_align(fembs)
chk.align_flg = False
print("Done: data_align fembs={}".format(fembs))
```

#### `wib_acquire.py`

```python
"""
用法: python3 wib_acquire.py {fembs} --samples 10 --output RMS_SE_200mVBL_14_0mVfC_2_0us_0x00.bin
功能: 触发 Spy Buffer 采集并保存原始数据
来源: QC_runs.take_data() → spybuf_trig() + pickle.dump()
"""
import sys, pickle, argparse
from wib_cfgs import WIB_CFGS

ap = argparse.ArgumentParser()
ap.add_argument("fembs", type=int, nargs='+')
ap.add_argument("--samples", type=int, default=10)
ap.add_argument("--output",  type=str, default="rms_raw.bin")
ap.add_argument("--trig",    type=int, default=0)  # 0=SW trigger
args = ap.parse_args()

fembs = args.fembs
chk = WIB_CFGS()
chk.wib_fw()

rawdata = chk.spybuf_trig(
    fembs=fembs,
    num_samples=args.samples,
    trig_cmd=args.trig,
    fastchk=True
)

if rawdata is False:
    print("ERROR: data sync failed")
    sys.exit(1)

outpath = "/home/root/BNL_CE_WIB_SW_QC/QC/" + args.output
import os; os.makedirs(os.path.dirname(outpath), exist_ok=True)

with open(outpath, 'wb') as f:
    # 兼容 QC_runs 格式：[rawdata, cfg_paras_rec, fembs]
    pickle.dump([rawdata, [], fembs], f)

print("Done: acquired {} samples → {}".format(args.samples, outpath))
```

---

### 3.4 `core/femb_manifest.py`

**要求：** 管理采集清单，实现配置↔文件名的双向映射。

```python
"""
acquisition_manifest.json 格式：
{
  "created_at": "2025-04-05 14:30:00",
  "pc_data_dir": "./data/20250405_143000/",
  "fembs": [0, 1],
  "operator": "Lke",
  "env": "RT",
  "acquisitions": [
    {
      "file": "RMS_SE_200mVBL_14_0mVfC_2_0us_0x00.bin",
      "config": {
        "mode": "SE",
        "snc": 1,   "snc_label": "200mV",
        "sg0": 0,   "sg1": 0,   "gain_label": "14mV/fC",
        "st0": 1,   "st1": 1,   "peaking_label": "2us",
        "dac": "0x00"
      },
      "num_samples": 10,
      "timestamp": "2025-04-05 14:30:05"
    },
    ...
  ]
}
"""

def generate_filename(mode: str, snc: int, sg0: int, sg1: int,
                      st0: int, st1: int, dac: int = 0) -> str:
    """
    根据配置参数生成与 QC_runs.py 兼容的文件名。
    例：RMS_SE_200mVBL_14_0mVfC_2_0us_0x00.bin
    """

def parse_filename(fname: str) -> dict:
    """
    从文件名反解配置参数。
    RMS_SE_200mVBL_14_0mVfC_2_0us_0x00.bin →
    {'mode':'SE','snc':1,'snc_label':'200mV','gain_label':'14mV/fC',
     'peaking_label':'2us','sg0':0,'sg1':0,'st0':1,'st1':1}
    """

def create_manifest(data_dir: str, fembs: list, operator: str,
                    env: str) -> dict:
    """创建空的 manifest 并保存。"""

def add_acquisition(manifest: dict, file: str, config: dict,
                    num_samples: int) -> dict:
    """向 manifest 添加一条采集记录并保存。"""

def load_manifest(manifest_path: str) -> dict:
    """加载已有 manifest。"""

def find_files_by_config(manifest: dict, snc_label: str = None,
                         gain_label: str = None,
                         peaking_label: str = None,
                         mode: str = None) -> list:
    """
    按配置条件筛选文件列表。
    返回匹配的 acquisition 记录列表。
    None 表示不过滤该字段。
    """
```

---

### 3.5 `core/femb_analysis_lib.py`

**要求：** 纯 PC 本地分析，不涉及 SSH。基于现有 `QC_tools.ana_tools` 重构，
增加精确通道筛选能力。

```python
"""
核心依赖（从现有代码复制到本项目）：
  - spymemory_decode.wib_dec   → 解码 spy buffer 原始数据
  - QC_check.CHKPulse          → Pass/Fail 判定
"""

# ── 数据加载 ──────────────────────────────────────────────────────────────────

def load_rms_bin(filepath: str) -> tuple:
    """
    加载单个 RMS bin 文件（QC_runs 格式）。
    返回 (rawdata, cfg_paras_rec, fembs)
    """

def load_full_rms_dict(data_dir: str) -> dict:
    """
    加载 item5 全量结果文件 QC_femb_rms_t5.bin。
    返回 {filename: [rawdata, pwr_meas, cfg_paras_rec, logs], ...}
    """

# ── 数据解码 ──────────────────────────────────────────────────────────────────

def decode_to_channels(rawdata, fembs: list, spy_num: int = 5) -> dict:
    """
    将 spy buffer 原始数据解码为通道数据。
    返回：{femb_id: channels_data}
    其中 channels_data[ch] = np.ndarray shape (N_samples,)，ch=0~127
    
    内部调用：wib_dec(rawdata, fembs, spy_num=spy_num)
    """

# ── 通道筛选（核心新功能）────────────────────────────────────────────────────

def resolve_chip(chip_spec) -> int:
    """chip_id(int) 或 丝印号(str如'U03') → chip_id"""

def resolve_channels(chips=None, chip_channels=None,
                     global_channels=None) -> list:
    """
    统一解析通道选择，返回全局通道号列表。
    三种输入方式（优先级从高到低）：
      global_channels: [48, 49, 59]          → 直接使用
      chip_channels:   {'U03':[11], 3:[0,1]} → 转换为全局通道号
      chips:           [3,'U07']             → 整片芯片所有通道
      都为 None                               → 全部128通道
    """

# ── RMS 计算 ──────────────────────────────────────────────────────────────────

def compute_rms(channels_data: dict, femb_id: int,
                target_channels: list = None) -> dict:
    """
    计算指定通道的 pedestal 和 RMS。
    直接移植自 ana_tools.GetRMS()，增加通道筛选。
    
    参数：
      channels_data: decode_to_channels() 的返回值
      femb_id: 要分析的 FEMB 编号
      target_channels: None=全部128通道，否则只计算指定通道
    
    返回：
    {
      'femb_id': int,
      'channels': {
        'ch_000': {
          'global_ch': 0, 'chip_id': 0, 'silkscreen': 'U07', 'chip_chn': 0,
          'ped': float,    # mean ADC count (pedestal)
          'rms': float,    # std ADC count
          'ped_max': float,
          'ped_min': float,
        }, ...
      },
      'summary': {
        'ped_mean': float, 'ped_std': float,
        'rms_mean': float, 'rms_std': float,
        'rms_median': float,
      }
    }
    """

# ── Pass/Fail 判定 ────────────────────────────────────────────────────────────

def check_passfail(rms_result: dict,
                   ped_threshold: float = 1500.0,
                   rms_threshold: float = 0.6) -> dict:
    """
    对 compute_rms() 结果做 Pass/Fail 判定。
    直接使用 QC_check.CHKPulse() 逻辑。
    
    返回：
    {
      'pass': bool,
      'ped_status': bool,
      'rms_status': bool,
      'bad_channels': [int, ...],   # 全局通道号
      'bad_chips':    [int, ...],   # chip_id
      'bad_silkscreens': [str, ...],
      'summary': str,  # 人类可读的总结
    }
    """

# ── 绘图 ─────────────────────────────────────────────────────────────────────

def plot_rms_128ch(rms_result: dict, config_label: str,
                   save_path: str = None, show: bool = False):
    """
    绘制128通道 RMS 分布图（对标 ana_tools._plot_data()）。
    x轴：通道号（0~127），每16通道一个刻度（对应芯片边界）
    y轴：RMS（ADC counts）
    标注：芯片丝印号（U07/U17/...）
    """

def plot_rms_compare(results_dict: dict, save_path: str = None,
                     show: bool = False):
    """
    多配置横向对比图。
    参数：{config_label: rms_result, ...}
    例：{'200mV_14mVfC_2us': result1, '200mV_25mVfC_2us': result2}
    """

# ── 高层接口（供 NL Agent 调用）──────────────────────────────────────────────

def analyze_from_manifest(manifest_path: str, femb_id: int,
                          snc_label: str = None,
                          gain_label: str = None,
                          peaking_label: str = None,
                          chips=None,
                          chip_channels=None,
                          global_channels=None,
                          plot: bool = True,
                          save_dir: str = None) -> dict:
    """
    Phase 1 主分析接口：从 manifest 找到对应文件，解码并分析。
    
    参数：
      manifest_path: acquisition_manifest.json 路径
      femb_id: 要分析的 FEMB 编号
      snc_label/gain_label/peaking_label: 配置过滤（None=不过滤）
      chips/chip_channels/global_channels: 通道筛选
      plot: 是否生成图表
      save_dir: 图表保存目录
    
    返回：
    {
      'matched_configs': int,        # 匹配到的配置数量
      'results': {
        'config_label': {
          'rms_result': dict,        # compute_rms() 结果
          'passfail': dict,          # check_passfail() 结果
        }, ...
      },
      'summary': str,               # 人类可读总结
    }
    """
```

---

### 3.6 `agent/femb_nl_agent.py`

**要求：** 使用 Ollama + Qwen3:8b，通过 few-shot prompt 实现自然语言→指令参数的解析。
**不需要微调模型**，只用 prompt engineering。

#### 核心流程

```python
class FEMBNLAgent:
    """
    自然语言驱动的 FEMB QC 代理。
    
    职责：
      1. 解析用户自然语言 → 结构化参数（JSON）
      2. 选择合适的指令序列
      3. 调用 femb_ssh_lib / femb_analysis_lib 执行
      4. 将结果翻译为人类可读输出
    """
    
    def __init__(self, ollama_host: str = "http://localhost:11434",
                 model: str = "qwen3:8b"):
        """初始化 Ollama 客户端，加载函数注册表。"""
    
    def parse_intent(self, user_input: str) -> dict:
        """
        调用 Qwen3:8b 解析用户意图。
        
        返回结构（JSON）：
        {
          "intent": "analyze_rms" | "run_rms" | "run_single" | "power_on" | ...,
          "params": {
            "fembs":    [0, 1],
            "snc":      "200mV",     # 或 null
            "gain":     "14mV/fC",   # 或 null
            "peaking":  "2us",       # 或 null
            "chips":    ["U03"],     # 或 null
            "chip_channels": null,
            "global_channels": null,
            "env":      "RT",
            "operator": "Lke",
            "num_samples": 10,
          },
          "confidence": 0.95,
          "clarification_needed": false,
          "clarification_question": null
        }
        
        Prompt 设计（few-shot）：
          - System prompt：角色定义 + 参数空间说明 + 编码表
          - Few-shot examples：至少10组中英文示例
          - 输出要求：严格 JSON，不含其他文字
        """
    
    def execute(self, user_input: str, 
                interactive: bool = True) -> dict:
        """
        完整执行流程。
        
        步骤：
          1. parse_intent(user_input) → params
          2. 如果 confidence < 0.8 且 interactive=True，向用户确认
          3. 打印中间表示（参数列表）让用户确认
          4. 调用对应函数执行
          5. 返回结构化结果 + 人类可读总结
        """
    
    def _build_system_prompt(self) -> str:
        """构建系统 prompt，包含所有参数空间和编码表。"""
    
    def _build_few_shot_examples(self) -> list:
        """
        构建 few-shot 示例列表。至少包含以下场景：
        
        中文输入示例：
        1. "对FEMB 0做baseline RMS测试，200mV基线，14mV/fC，2us"
        2. "分析U03芯片在200mV 14mVfC 2us下的RMS"
        3. "测FEMB 0和1所有配置的噪声"
        4. "查看chip3第11通道的baseline"
        5. "打开FEMB 0上电"
        
        英文输入示例：
        6. "run full RMS on FEMB 0 and 1"
        7. "analyze U07 chip, 200mV baseline, 14mV/fC gain"
        8. "what is the RMS of channel 59"
        9. "power on slot 0"
        10. "run single config: FEMB 0, 900mV, 7.8mV/fC, 1us"
        """
    
    def _call_ollama(self, messages: list) -> str:
        """
        调用 Ollama API。
        使用 requests POST 到 http://localhost:11434/api/chat
        stream=False，返回 message.content
        """
    
    def _map_intent_to_action(self, intent: dict) -> callable:
        """
        根据 intent 选择对应的执行函数。
        
        intent_map = {
          "run_rms":      self._action_run_full_rms,
          "run_single":   self._action_run_single_config,
          "analyze_rms":  self._action_analyze_rms,
          "power_on":     self._action_power_on,
          "power_off":    self._action_power_off,
        }
        """
```

#### Prompt 模板核心内容

```python
SYSTEM_PROMPT_TEMPLATE = """
你是一个 DUNE 实验 FEMB 冷电子学测试系统的智能助手。
你的任务是将用户的自然语言描述解析为结构化的测试参数，输出严格的 JSON 格式。

## 系统架构
- FEMB 编号：0~3（对应 Slot 0~3）
- 每块 FEMB 有 8 个 LArASIC 芯片，128 个通道
- 芯片-丝印-通道对照表：
  Chip 0 = U07 = 通道 0~15
  Chip 1 = U17 = 通道 16~31
  Chip 2 = U11 = 通道 32~47
  Chip 3 = U03 = 通道 48~63
  Chip 4 = U19 = 通道 64~79
  Chip 5 = U23 = 通道 80~95
  Chip 6 = U25 = 通道 96~111
  Chip 7 = U21 = 通道 112~127

## 可配置参数
基线电压（snc）：200mV 或 900mV
增益（gain）：4.7mV/fC、7.8mV/fC、14mV/fC、25mV/fC
成形时间（peaking）：0.5us、1us、2us、3us
环境（env）：RT（室温）或 LN（液氮）

## 意图类型
- run_rms：执行完整 RMS 测试（所有配置）
- run_single：执行单一配置的 RMS 采集
- analyze_rms：分析已有数据
- power_on：上电 FEMB
- power_off：断电 FEMB

## 输出要求
只输出 JSON，不含任何解释文字。
未指定的参数设为 null。
"""
```

---

### 3.7 `agent/femb_function_registry.json`

```json
{
  "version": "2.0.0",
  "description": "FEMB QC 系统完整指令注册表（Phase 1 + Phase 2）",

  "layer0_init": {
    "wib_ping":      {"nl_triggers": ["ping", "检查WIB", "WIB是否在线"], "params": {}},
    "wib_time_sync": {"nl_triggers": ["同步时间", "sync time"], "params": {}},
    "wib_startup":   {"nl_triggers": ["初始化WIB", "WIB startup", "启动WIB"], "params": {}},
    "cfg_push":      {"nl_triggers": ["推送配置", "push config"], "params": {"operator": "str", "env": "RT|LN"}}
  },

  "layer1_power": {
    "femb_power_on": {
      "nl_triggers": ["上电", "打开FEMB", "power on", "turn on"],
      "params": {"slots": "list[0-3]", "env": "RT|LN"}
    },
    "femb_power_off": {
      "nl_triggers": ["断电", "关掉FEMB", "power off", "turn off"],
      "params": {}
    }
  },

  "layer2_acquire": {
    "run_full_rms": {
      "nl_triggers": ["完整RMS", "全量测试", "run full rms", "测所有配置", "item5"],
      "params": {"slots": "list[0-3]", "operator": "str", "env": "RT|LN"},
      "note": "Phase 1：调用 QC_top.py -t 5，采集全部32种配置"
    },
    "run_single_config": {
      "nl_triggers": ["单配置", "指定配置采集", "run single", "只测这一种"],
      "params": {
        "slots": "list[0-3]",
        "snc":  "200mV|900mV",
        "gain": "4.7mV/fC|7.8mV/fC|14mV/fC|25mV/fC",
        "peaking": "0.5us|1us|2us|3us",
        "num_samples": "int"
      },
      "note": "Phase 2：调用原子脚本序列，只采目标配置"
    },
    "run_config_matrix": {
      "nl_triggers": ["配置矩阵", "多种配置", "config matrix"],
      "params": {
        "slots": "list[0-3]",
        "snc_list": "list[200mV|900mV]",
        "gain_list": "list[...]",
        "peaking_list": "list[...]"
      }
    }
  },

  "layer3_analysis": {
    "analyze_from_manifest": {
      "nl_triggers": ["分析", "analyze", "查看RMS", "看结果", "baseline是多少"],
      "params": {
        "femb_id": "int",
        "snc_label": "200mV|900mV|null",
        "gain_label": "str|null",
        "peaking_label": "str|null",
        "chips": "list[chip_id or silkscreen]|null",
        "chip_channels": "dict|null",
        "global_channels": "list[int]|null"
      }
    }
  },

  "param_synonyms": {
    "snc": {
      "200mV基线": "200mV", "200mVBL": "200mV", "低基线": "200mV",
      "900mV基线": "900mV", "900mVBL": "900mV", "高基线": "900mV"
    },
    "gain": {
      "14": "14mV/fC", "14mVfC": "14mV/fC",
      "25": "25mV/fC", "7.8": "7.8mV/fC", "4.7": "4.7mV/fC"
    },
    "peaking": {
      "2微秒": "2us", "0.5微秒": "0.5us", "1微秒": "1us", "3微秒": "3us"
    },
    "chip": {
      "U3": "U03", "U7": "U07", "chip0": 0, "chip3": 3
    },
    "env": {
      "液氮": "LN", "LN2": "LN", "冷测": "LN", "室温": "RT", "常温": "RT"
    }
  }
}
```

---

## 4. 入口脚本

### 4.1 `main.py` — 交互式命令行

```python
#!/usr/bin/env python3
"""
FEMB QC 自然语言驱动系统 — 主入口

用法：
  python3 main.py                    # 交互模式
  python3 main.py "分析FEMB 0的RMS"  # 单次执行
  python3 main.py --phase1           # 直接跑全量 item5
"""
import sys
from agent.femb_nl_agent import FEMBNLAgent

def main():
    agent = FEMBNLAgent()
    
    if len(sys.argv) > 1 and sys.argv[1] != "--phase1":
        # 单次执行模式
        result = agent.execute(" ".join(sys.argv[1:]))
        print(result['summary'])
    elif "--phase1" in sys.argv:
        # 直接跑完整 item5（不经过 NL 解析）
        from core.femb_ssh_lib import run_full_rms
        result = run_full_rms(slots=[0], operator="Lke", env="RT")
        print(result)
    else:
        # 交互模式
        print("FEMB QC 系统已就绪。输入 'exit' 退出。")
        print("示例：'分析FEMB 0在200mV基线14mVfC 2us下的RMS'")
        print("-" * 60)
        while True:
            try:
                user_input = input("\n> ").strip()
                if user_input.lower() in ('exit', 'quit', '退出'):
                    break
                if not user_input:
                    continue
                result = agent.execute(user_input)
                print("\n" + result.get('summary', str(result)))
            except KeyboardInterrupt:
                break
    
    print("\n再见！")

if __name__ == "__main__":
    main()
```

---

## 5. 实现顺序与优先级

Claude Code 请按以下顺序实现，每步完成后运行对应测试：

```
Step 1  core/femb_constants.py
        → 运行 tests/test_constants.py
          验证：编码表、映射表、全局通道号计算

Step 2  core/femb_manifest.py
        → 验证：generate_filename / parse_filename 互逆
          验证：find_files_by_config 过滤逻辑

Step 3  core/femb_ssh_lib.py（先实现 _ssh_run/_scp_*/_make_slot_args）
        → 运行 tests/test_ssh_lib.py
          用 mock 验证命令拼接是否正确，不实际连接 WIB

Step 4  scripts/wib_atoms/*.py
        → 语法检查，不需要 WIB 硬件

Step 5  core/femb_analysis_lib.py
        → 用模拟数据验证 compute_rms / check_passfail / resolve_channels
          验证：chip_channels={'U03':[11]} 正确解析为 global_ch=59

Step 6  agent/femb_nl_agent.py（先实现 parse_intent，mock Ollama）
        → 验证：10个 few-shot 示例都能正确解析

Step 7  main.py + 端到端集成测试（需要 Ollama 运行）

Step 8  有 WIB 硬件时：运行 Phase 1 全流程
Step 9  有 WIB 硬件时：运行 Phase 2 单配置采集
```

---

## 6. 测试规范

### 6.1 `tests/test_constants.py`

```python
def test_gain_encoding():
    from core.femb_constants import GAIN_MAP
    assert GAIN_MAP["14mV/fC"] == (0, 0)
    assert GAIN_MAP["25mV/fC"] == (1, 0)
    assert GAIN_MAP["7.8mV/fC"] == (0, 1)
    assert GAIN_MAP["4.7mV/fC"] == (1, 1)

def test_peaking_encoding():
    from core.femb_constants import PEAKING_MAP
    assert PEAKING_MAP["1us"]   == (0, 0)   # 注意不是 (1,0)
    assert PEAKING_MAP["0.5us"] == (1, 0)
    assert PEAKING_MAP["2us"]   == (1, 1)
    assert PEAKING_MAP["3us"]   == (0, 1)

def test_chip_channel_mapping():
    from core.femb_constants import CHIP_CHANNEL_MAP, SILKSCREEN_TO_CHIP
    assert CHIP_CHANNEL_MAP[3] == ("U03", 48, 63)
    assert SILKSCREEN_TO_CHIP["U03"] == 3
    # chip3 chn11 → global 59
    chip_id, ch_start, ch_end = CHIP_CHANNEL_MAP[3]
    assert ch_start + 11 == 59
```

### 6.2 `tests/test_analysis_lib.py`

```python
import numpy as np

def make_mock_channels_data(n_channels=128, n_samples=500, seed=42):
    rng = np.random.default_rng(seed)
    return {
        ch: rng.normal(loc=800 + ch * 2, scale=3.0, size=n_samples)
        for ch in range(n_channels)
    }

def test_resolve_channels_by_silkscreen():
    from core.femb_analysis_lib import resolve_channels
    chs = resolve_channels(chips=["U03"])
    assert chs == list(range(48, 64))

def test_resolve_channels_by_chip_channels():
    from core.femb_analysis_lib import resolve_channels
    chs = resolve_channels(chip_channels={"U03": [11]})
    assert chs == [59]

def test_compute_rms_basic():
    from core.femb_analysis_lib import compute_rms, decode_to_channels
    # mock channels_data
    mock_data = {0: make_mock_channels_data()}
    result = compute_rms(mock_data, femb_id=0)
    assert len(result['channels']) == 128
    for key, val in result['channels'].items():
        assert 'ped' in val and 'rms' in val
        assert val['rms'] > 0

def test_compute_rms_filtered():
    from core.femb_analysis_lib import compute_rms
    mock_data = {0: make_mock_channels_data()}
    result = compute_rms(mock_data, femb_id=0,
                         target_channels=[48, 49, 59])
    assert len(result['channels']) == 3
    assert 'ch_059' in result['channels']
    assert result['channels']['ch_059']['chip_id'] == 3
    assert result['channels']['ch_059']['silkscreen'] == 'U03'
```

---

## 7. 注意事项（给 Claude Code 的特别提示）

1. **ST 编码反直觉**：`1us → st=(0,0)`，`2us → st=(1,1)`，`0.5us → st=(1,0)`，`3us → st=(0,1)`。
   严格按照 Datasheet Table 6 和本文档 Section 0.4 实现，不要按直觉猜测。

2. **WIB 脚本兼容性**：`scripts/wib_atoms/` 里的脚本在 WIB 上运行，
   WIB 是 Linux（Zynq），Python 版本可能是 3.6，不要用 f-string 的高级特性，
   不要用 3.8+ 的 walrus operator。

3. **femb_cfg 写两次**：`wib_fe_configure.py` 里 `femb_cfg()` 要调用两次，
   这是与 `QC_runs.take_data()` 保持行为一致的要求。

4. **文件名兼容性**：生成的数据文件名必须与 `QC_runs.py` 的命名格式完全一致，
   以便现有的 `QC_report.py` 也能直接读取分析。

5. **Ollama 调用**：使用 `requests.post` 而不是 `ollama` 库，
   因为后者版本兼容性不稳定。API 端点：`POST http://localhost:11434/api/chat`，
   设置 `"stream": false`。

6. **数据目录**：每次测试生成一个时间戳目录 `./data/YYYYMMDD_HHMMSS/`，
   不要覆盖历史数据。

7. **`wib_atoms` 目录**：脚本需要提前 SCP 到 WIB 的 `{WIB_ATOMS_DIR}`，
   `femb_ssh_lib.push_atoms_to_wib()` 负责这个步骤，在首次使用前调用一次即可。

8. **Phase 2 的稳定等待**：`wib_fe_configure.py` 里有 `time.sleep(10)`，
   这是 LArASIC 配置后稳定所需时间，不能删除。SSH 调用超时要相应设长（≥30s）。

9. **`decode_to_channels` 的数据结构**：
   `wib_dec` 返回值的结构是 `wibdata[spy_idx][femb_idx][ch]`，
   需要沿时间轴 concatenate 所有 spy_num 帧后才是完整的通道数据。

10. **SSH user_input 格式**：`QC_top.py` 启动时会交互式询问操作员名、环境、ToyTPC 等，
    用 `subprocess.run(input=user_input_str)` 传入，格式严格按照 `_make_femb_input_str()` 生成。
