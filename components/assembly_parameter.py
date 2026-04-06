# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : Assembly QC parameter definitions and defaults

#voltage setting


D = 0
def para(env):
    if env == 'RT':
        D = 0
    else:
        D = 1

voltage_FE      = 3.0
voltage_COLDATA = 3.0
voltage_ColdADC = 3.5

#chip current reference
if D==0:
    bias_i_low  =   0.15
    fe_i_low    =   0.3
    fe_i_high   =   0.7
    cd_i_low    =   0.1
    cd_i_high   =   0.3
    adc_i_low   =   1.2
    adc_i_high  =   1.99
else:
    bias_i_low  =   0.15
    fe_i_low    =   0.3
    fe_i_high   =   0.65
    cd_i_low    =   0.1
    cd_i_high   =   0.3
    adc_i_low   =   1.2
    adc_i_high  =   1.99


