#!/usr/bin/env python3
"""
FEMB QC Natural Language Driven System — Main Entry Point

Usage:
  python3 main.py                    # Interactive mode
  python3 main.py "分析FEMB 0的RMS"  # Single-shot execution
  python3 main.py --phase1           # Run full item-5 directly (no NL parsing)
"""

import sys
import os

# Ensure the project root (femb_qc_nlp/) is on sys.path so that
# `from core.xxx import ...` and `from agent.xxx import ...` work when
# main.py is invoked from any working directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from agent.femb_nl_agent import FEMBNLAgent


def main():
    agent = FEMBNLAgent()

    if len(sys.argv) > 1 and sys.argv[1] != "--phase1":
        # Single-shot execution mode
        user_text = " ".join(sys.argv[1:])
        result = agent.execute(user_text, interactive=False)
        print(result["summary"])

    elif "--phase1" in sys.argv:
        # Direct item-5 full run — bypass NL parsing
        from core.femb_ssh_lib import run_full_rms
        result = run_full_rms(slots=[0], operator="Lke", env="RT")
        print(result)

    else:
        # Interactive loop
        print("FEMB QC 系统已就绪。输入 'exit' 退出。")
        print("示例：'分析FEMB 0在200mV基线14mVfC 2us下的RMS'")
        print("-" * 60)

        while True:
            try:
                user_input = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "退出"):
                break

            result = agent.execute(user_input)
            print("\n" + result.get("summary", str(result)))

    print("\n再见！")


if __name__ == "__main__":
    main()
