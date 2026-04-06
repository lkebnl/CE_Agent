# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : CE item-17 checkout and verification script
chk = WIB_CFGS()
chk.wib_fw()

WIB2CE_voltage = 2.5
chk.fembs_vol_set(vfe=WIB2CE_voltage, vcd=WIB2CE_voltage, vadc=WIB2CE_voltage)

if len(fembs) != 0:
    print (f"Turn FEMB {fembs} on")
    chk.femb_power_com_on(fembs)
    chk.femb_cd_rst()
else:
    print (f"Turn All FEMB off")
    chk.femb_power_com_off(fembs_off)




chk.femb_cd_rst()
cfg_paras_rec = []
# for i in range(8):
#     chk.adcs_paras[i][8]=1   # enable  auto

for i in range(8):
    chk.adcs_paras[i][2]=1   # enable differential
    chk.adcs_paras[i][8]=1   # enable  auto

for femb_id in fembs:
    chk.set_fe_board(sts=0, snc=snc, sg0=sg0, sg1=sg1, st0=st0, st1=st1, swdac=0, dac=0x00 )
    adac_pls_en = 0
    cfg_paras_rec.append((femb_id, copy.deepcopy(chk.adcs_paras), copy.deepcopy(chk.regs_int8), adac_pls_en))
    chk.femb_cfg(femb_id, adac_pls_en )
    self.femb_i2c_wrchk(femb_id, chip_addr=c_id, reg_page=1, reg_addr=0x9d,
                    wrdata=0x27)  # ibuff0 current should be 200uA when input buffers are enabled
    self.femb_i2c_wrchk(femb_id, chip_addr=c_id, reg_page=1, reg_addr=0x9e,
                    wrdata=0x27)  # ibuff0 current should be 200uA when input buffers are enabled

data acquire




