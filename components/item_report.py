# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : Individual-item QC report writer
# from wib_cfgs import WIB_CFGS
# import time
# import sys
# import numpy as np
# import pickle
# import copy
# import os
# import time, datetime, random, statistics
# import fpdf as fpdf
# import fitz
#
#
#
#
# import fitz  # PyMuPDF
#
# def merge_pdfs(input_paths, output_path):
#     # Create a PdfWriter object for writing the merged PDF
#     pdf_writer = fitz.open()
#
#     try:
#         # Iterate over the input PDF file paths
#         for path in input_paths:
#             # Open each PDF file
#             pdf_document = fitz.open(path)
#
#             # Iterate over each page and add it to the PdfWriter object
#             for page_num in range(pdf_document.page_count):
#                 page = pdf_document[page_num]
#                 pdf_writer.insert_pdf(pdf_document, from_page=page_num, to_page=page_num, start_at=pdf_writer.page_count)
#
#         # Save the merged PDF to the output file
#         pdf_writer.save(output_path)
#
#         print(f'Success Merge Report to {output_path}')
#
#     except Exception as e:
#         print(f'Error occurred: {str(e)}')
#
#     finally:
#         # Close all opened PDF files
#         pdf_writer.close()
#
# # Specify the list of input PDF file paths
#
#
# def Gather_Report(datadir):
#     print(datadir)
#     item1   = datadir+'/' + 'PWR_Meas/report.pdf'
#     item3   = datadir+'/' + 'Leakage_Current/report.pdf'
#     item4   = datadir+'/' + 'CHK/report.pdf'
#     item5   = datadir+'/' + 'RMS/report.pdf'
#
#     item6_1 = datadir+'/' + 'CALI1/report_200mVBL_4_7mVfC_2_0us.pdf'
#     item6_2 = datadir+'/' + 'CALI1/report_200mVBL_7_8mVfC_2_0us.pdf'
#     item6_3 = datadir+'/' + 'CALI1/report_200mVBL_14_0mVfC_2_0us.pdf'
#     item6_4 = datadir+'/' + 'CALI1/report_200mVBL_25_0mVfC_2_0us.pdf'
#     item7   = datadir+'/' + 'CALI2/report_900mVBL_14_0mVfC_2_0us.pdf'
#     item8   = datadir+'/' + 'CALI3/report_200mVBL_14_0mVfC_2_0us_sgp1.pdf'
#     item9   = datadir+'/' + 'CALI4/report_900mVBL_14_0mVfC_2_0us_sgp1.pdf'
#
#     input_pdf_paths = [item1, item6_1, item6_2, item6_3, item6_4, item7, item8, item9, item3, item4, item5]
#
#     # Specify the output PDF file path
#     output_pdf_path = datadir + '/temp_report.pdf'
#
#     # Call the function to merge PDF files
#     merge_pdfs(input_pdf_paths, output_pdf_path)
#
#
#     print(314159)