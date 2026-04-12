# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : Assembly QC report formatting and export
import components.assembly_log as log
import subprocess


#================   Final Report    ===================================
# LKE@BNL.GOV

def dict_to_html_table(dictionary, KEY="KEY", VALUE="RECORD"):
    keys = list(dictionary.keys())
    values = list(dictionary.values())
    html = "<table border='1' style='border-collapse: collapse;'>"
    if VALUE == "PWRVALUE":
        # Confirm the value is a list → output as multi-column table
        max_len = max(len(v) if isinstance(v, list) else 1 for v in values)
        html += f"<tr><th>{KEY}</th>" + "".join(f"<th>CH{i}</th>" for i in range(max_len)) + "</tr>\n"

        for key, value in zip(keys, values):
            if isinstance(value, list):
                html += f"<tr><td>{key}</td>" + "".join(f"<td>{v}</td>" for v in value) + "</tr>\n"
            else:
                html += f"<tr><td>{key}</td><td colspan='{max_len}'>{value}</td></tr>\n"

    elif VALUE == "MonPath":
    # Multi-column table: KEY is the row name, each value is a list displayed as a full row
        max_len = max(len(v) if isinstance(v, list) else 1 for v in values)
        html += f"<tr><th>{KEY}</th>" + "".join(f"<th>CH{i}</th>" for i in range(max_len)) + "</tr>\n"
        for key, value in zip(keys, values):
            if isinstance(value, list):
                html += f"<tr><td>{key}</td>" + "".join(f"<td>{v}</td>" for v in value) + "</tr>\n"
            else:
                html += f"<tr><td>{key}</td><td colspan='{max_len}'>{value}</td></tr>\n"

    elif VALUE == "Horizontal":
        html += "<tr>" + "".join(f"<th>{key}</th>" for key in keys) + "</tr>"
        html += "<tr>" + "".join(f"<td>{str(dictionary[key]).strip()}</td>" for key in keys) + "</tr>"
    else:
        html += f"<tr><th>{KEY}</th><th>{VALUE}</th></tr>"
        for key, value in zip(keys, values):
            html += f"<tr><td>{key}</td><td>{value}</td></tr>"
    html += "</table>"
    return html


def final_report(datareport, fembs, fembNo, Rail=True):
    print("\n\n\n")
    print("==================================================================================")
    print("+++++++               GENERAL REPORT for FEMB BOARDS TESTING               +++++++")
    print("+++++++                                                                    +++++++")
    print("==================================================================================")
    print("\n")
    print(log.report_log01["ITEM"])
    for key, value in log.report_log01["Detail"].items():
        print(f"{key}: {value}")

    print('\n')

    all_true = {}
    for ifemb in fembs:
        femb_id = "FEMB ID {}".format(fembNo['femb%d' % ifemb])

        log.final_status[femb_id]["item2"] = log.report_log021[femb_id]["Result"]
        log.final_status[femb_id]["item3"] = log.report_log03[femb_id]["Result"]
        log.final_status[femb_id]["item4"] = log.report_log04[femb_id]["Result"]
        log.final_status[femb_id]["item5"] = log.report_log051[femb_id]["Result"]
        if Rail:
            log.final_status[femb_id]["item6"] = log.report_log061[femb_id]["Result"]
        log.final_status[femb_id]["item7"] = log.report_log07[femb_id]["Result"]
        log.final_status[femb_id]["item8"] = log.report_log08[femb_id]["Result"]
        log.final_status[femb_id]["item9"] = log.report_log091[femb_id]["Result"]
        if Rail:
            log.final_status[femb_id]["item10"] = log.report_log101[femb_id]["Result"]
        log.final_status[femb_id]["Monitor_Path"] = log.report_log111[femb_id]["Result"]

        all_true[femb_id] = all(value for value in log.final_status[femb_id].values())

        if all_true[femb_id]:
            print("FEMB ID {}\t Slot {} PASS\t ALL ASSEMBLY CHECKOUT".format(fembNo['femb%d' % ifemb], ifemb))
        else:
            print("femb id {}\t Slot {} faild\t the checkout".format(fembNo['femb%d' % ifemb], ifemb))
    print("\n\n")
    print("Here is the Summary")

    for ifemb in fembs:
        femb_id = "FEMB ID {}".format(fembNo['femb%d' % ifemb])

        # Determine the list of logs to check based on Rail variable
        if Rail:
            dict_list = [
                log.report_log021, log.report_log03, log.report_log04, log.report_log051,
                log.report_log061, log.report_log07, log.report_log08, log.report_log091,
                log.report_log101, log.report_log111
            ]
        else:
            dict_list = [
                log.report_log021, log.report_log03, log.report_log04, log.report_log051,
                log.report_log07, log.report_log08, log.report_log091, log.report_log111
            ]

        issue_note = ""
        if all_true[femb_id]:
            # If all tests pass, mark with green pass status
            summary = "<span style='color: green;'>" + "FEMB SN {}\t      PASS\t  CHECKOUT".format(fembNo['femb%d' % ifemb]) + "</span>"
            note = "### Here is the Summary"
            status = 'P'
            fhtml = datareport[ifemb] + 'report_FEMB_{}_Slot{}_{}.html'.format(fembNo['femb%d' % ifemb], ifemb, status)
        else:
            # If tests failed, mark with red fail status and output issue details
            print(femb_id)
            summary = "<span style='color: red;'>" + "femb id {}\t      faild\t checkout".format(fembNo['femb%d' % ifemb]) + "</span>"
            status = 'F'  # Note: original code had 'P' here, possibly a typo; check if should be 'F'

            for dict in dict_list:
                if dict[femb_id]["Result"] == False:
                    print(dict[femb_id])
                    issue_note += "{} \n".format(dict[femb_id])

            note = "### Here is the issue: \n" + str(issue_note) + "\n"
        fhtml = datareport[ifemb] + 'report_FEMB_{}_Slot{}_{}.html'.format(fembNo['femb%d' % ifemb], ifemb, status)
        # fhtml = datareport[ifemb] + 'report_FEMB_{}_Slot{}_{}.html'.format(fembNo['femb%d' % ifemb], ifemb, status)
        with open(fhtml, 'w', encoding="utf-8") as file:
            file.write('<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n<title>FEMB Report</title>\n</head>\n<body>\n')
            file.write('<br><br>\n')

            # Summary (with colored title)
            file.write(f'<h1>{summary}</h1>\n')
            file.write('<br>\n<br>\n')

            # Part 01: Input information heading
            Head01 = '<h3>PART 01 INPUT INFORMATION</h3>\n'
            file.write(Head01)

            # Write input info using HTML table format
            info = dict_to_html_table(log.report_log01["Detail"], VALUE="Horizontal")
            file.write(info + '<br>\n')

            text_line = "{}".format(femb_id)
            file.write(text_line + '<br>\n')
            text_line = "COLDATA_SN_CD0: {}".format(log.report_log00[femb_id]["COLDATA_SN_CD0"])
            file.write(text_line + '<br>\n')
            text_line = "COLDATA_SN_CD1: {}".format(log.report_log00[femb_id]["COLDATA_SN_CD1"])
            file.write(text_line + '<br>\n')

            # Note (issue details or general notes)
            file.write('<div>\n' + note.replace('###', '<h3>').replace('\n', '<br>\n') + '\n</div>\n')

            # Divider line
            file.write('<hr>\n')

            file.write('</body>\n</html>\n')

            # 02 Print <initial test results>
            if (log.report_log021[femb_id]["Result"] == True) and (log.report_log03[femb_id]["Result"] == True):
                Head02 = '<h3><span style="color: green;">PART 02 POR Measurement &nbsp;&nbsp; &lt; Pass &gt;</span></h3>\n'
            else:
                Head02 = '<h3><span style="color: red;">PART 02 POR Measurement &nbsp;&nbsp; | Fail</span></h3>\n'

            file.write(Head02)

            # Write Initial Current Measurement heading
            file.write(f'<h4>{log.report_log02["ITEM"]}</h4>\n')

            # Convert table to HTML table format
            info = dict_to_html_table(log.report_log02[femb_id], KEY="2.1 Initial Current Measurement", VALUE="PWRVALUE")
            file.write(info + '<br>\n')

            # Write Initial Register Check heading
            file.write(f'<h4>{log.report_log03["ITEM"]}</h4>\n')

            # Convert table to HTML table format
            info = dict_to_html_table(log.report_log03[femb_id], KEY="Initial Register Check", VALUE="Horizontal")
            file.write(info + '<br>\n')

            # 03 Print <SE OFF RMS, PED, Pulse, Power Current, Power Rail>
            if Rail:
                if (log.report_log04[femb_id]["Result"] == True) and (log.report_log051[femb_id]["Result"] == True) and (log.report_log061[femb_id]["Result"] == True):
                    Head03 = '<h3><span style="color: green;">PART 03 SE OFF Measurement &nbsp;&nbsp; &lt; Pass &gt;</span></h3>\n'
                else:
                    Head03 = '<h3><span style="color: red;">PART 03 SE OFF Measurement &nbsp;&nbsp; | Fail</span></h3>\n'
            else:
                if (log.report_log04[femb_id]["Result"] == True) and (log.report_log051[femb_id]["Result"] == True):
                    Head03 = '<h3><span style="color: green;">PART 03 SE OFF Measurement &nbsp;&nbsp; &lt; Pass &gt;</span></h3>\n'
                else:
                    Head03 = '<h3><span style="color: red;">PART 03 SE OFF Measurement &nbsp;&nbsp; | Fail</span></h3>\n'

            file.write(Head03)

            # Write SE Noise Measurement heading
            file.write(f'<h4>{log.report_log04["ITEM"]}</h4>\n')

            # Noise image insertion (ped + rms)
            file.write('<div>\n')
            file.write('<img src="./ped_Raw_SE_200mVBL_14_0mVfC_2_0us_0x00.png" alt="ped" style="max-width: 45%; margin-right: 10px;">\n')
            file.write('<img src="./rms_Raw_SE_200mVBL_14_0mVfC_2_0us_0x00.png" alt="rms" style="max-width: 45%;">\n')
            file.write('</div><br>\n')

            # Table output: SE Noise Measurement
            info = dict_to_html_table(log.report_log04[femb_id], KEY="3.1 Noise Measurement  200 mVBL  14 mV/fC  2 us", VALUE="VALUE")
            file.write(info + '<br>\n')

            # Write SE Current Measurement heading
            file.write(f'<h4>{log.report_log05["ITEM"]}</h4>\n')
            info = dict_to_html_table(log.report_log05[femb_id], KEY="3.2 SE OFF Power Measurement", VALUE="PWRVALUE")
            file.write(info + '<br>\n')

            # If Rail test included, write Power Rail info
            if Rail:
                file.write(f'<h4>{log.report_log06["ITEM"]}</h4>\n')
                info = dict_to_html_table(log.report_log06[femb_id], KEY="3.3 SE OFF LDO Measurement / mV", VALUE="Horizontal")
                file.write(info + '<br>\n')

            # Write Pulse Response test item
            file.write(f'<h4>{log.report_log07["ITEM"]}</h4>\n')

            # Pulse image insertion
            file.write('<div>\n')
            file.write('<img src="./pulse_Raw_SE_900mVBL_14_0mVfC_2_0us_0x10.bin.png" alt="pulse response" style="max-width: 90%;">\n')
            file.write('</div><br>\n')

            info = dict_to_html_table(log.report_log07[femb_id], KEY="3.4 SE OFF Pulse Response [900mV 14mV/fC 2us]", VALUE="VALUE")
            file.write(info + '<br>\n')

            # 04 Print <DIFF RMS, PED, Pulse, Power Current, Power Rail>
            if Rail:
                if (log.report_log08[femb_id]["Result"] == True) and (log.report_log091[femb_id]["Result"] == True) and (log.report_log101[femb_id]["Result"] == True):
                    Head04 = '<h3><span style="color: green;">PART 04 DIFF Measurement &nbsp;&nbsp; &lt; Pass &gt;</span></h3>\n'
                else:
                    Head04 = '<h3><span style="color: red;">PART 04 DIFF Measurement &nbsp;&nbsp; | Fail</span></h3>\n'
            else:
                if (log.report_log08[femb_id]["Result"] == True) and (log.report_log091[femb_id]["Result"] == True):
                    Head04 = '<h3><span style="color: green;">PART 04 DIFF Measurement &nbsp;&nbsp; &lt; Pass &gt;</span></h3>\n'
                else:
                    Head04 = '<h3><span style="color: red;">PART 04 DIFF Measurement &nbsp;&nbsp; | Fail</span></h3>\n'

            file.write(Head04)

            # 4.1 DIFF Pulse Measurement
            file.write(f'<h2>{log.report_log08["ITEM"]}</h2>\n')
            file.write('<div>\n')
            file.write('<img src="./pulse_Raw_DIFF_900mVBL_14_0mVfC_2_0us_0x10.png" alt="diff pulse" style="max-width: 90%;">\n')
            file.write('</div><br>\n')

            info = dict_to_html_table(log.report_log08[femb_id], KEY="4.1 DIFF Pulse Measurement at 900mV, 14mV/fC, 2us", VALUE="VALUE")
            file.write(info + '<br>\n')

            # 4.2 DIFF Current Measurement
            file.write(f'<h2>{log.report_log09["ITEM"]}</h2>\n')
            info = dict_to_html_table(log.report_log09[femb_id], KEY="4.2 DIFF Power Measurement", VALUE="PWRVALUE")
            file.write(info + '<br>\n')

            # 4.3 DIFF Power Rail (written only when Rail is True)
            if Rail:
                file.write(f'<h2>{log.report_log10["ITEM"]}</h2>\n')
                info = dict_to_html_table(log.report_log10[femb_id], KEY="4.3 DIFF LDO Measurement / mV", VALUE="Horizontal")
                file.write(info + '<br>\n')



            # 05 PART 05 Monitoring Path Measurement  # Lingyun Ke set
            if log.report_log111[femb_id]["Result"] == True:
                Head05 = f'<h2><span style="color: green;">PART 05 Monitoring Measurement &nbsp;&nbsp; &lt; Pass &gt;</span></h2>\n'
            else:
                Head05 = f'<h2><span style="color: red;">PART 05 Monitoring Measurement {femb_id} | Fail</span></h2>\n'

            file.write(Head05)

            # Write section heading
            file.write(f'<h2>{log.report_log11["ITEM"]}</h2>\n')

            # Table: monitoring path measurement data
            info = dict_to_html_table(log.report_log11[femb_id], KEY="Monitor Path", VALUE="MonPath")
            file.write(info + '<br>\n')
            line = "------\n"
            file.write(line + '<br>\n')
            file.write('lke@bnl.gov' + '<br>\n')

            print("Checkout Report Saved")
