# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : GUI email configuration and detail input panel
import GUI.send_email as send_email
sender = "bnlr216@gmail.com"
password = "vvef tosp minf wwhf"
receiver = "lke@bnl.gov"

def send_cold_down_email():
    send_email.send_email(
        sender, password, receiver,
        f"CTS has been cold down [{pre_info['test_site']}]",
        '"** Please Double confirm: reach level3, heat LED off"'
    )