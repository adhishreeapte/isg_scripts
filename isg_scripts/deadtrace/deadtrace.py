"""
- process .trc files of many engine starts without sparkplug
- plots of power, energy, reverse bang per cycle
- example config file: deadconfig.json

"""
import os
import sys
import csv
import click
import json as json
import numpy as np
import pandas as pd
import math as math
import pycan.sym as parser
import pycan.trace as tracer
from datetime import time as ddtime
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

def __plot_arr(x, y, start, fire, plot):
    #creates arrays with given limits for ease of plotting
    y_pl, x_pl = [], []
    for i, t in enumerate(x):
        if (x[i] >= start) and  (x[i]<= fire):
            y_pl.append(y[i])
            if plot >= 1:
                x_pl.append((t-start).total_seconds())
            else:
                x_pl.append(t)
    return x_pl, y_pl

@click.command()
@click.option('--config', type=str, default='config.json')
def cli(config):

    data_folder = 'isg_plots/'
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)
    if not os.path.exists(config):
        print('{} file not found'.format(config))
        sys.exit()

    op_points = []
    with open(config, 'r') as f:
        op_points = json.load(f)

    for op in op_points:
        beg_time = ddtime(17, 21, 31)
        end_time = ddtime(17, 21, 45)

        actual_name_list = [op['battery_voltage'], op['battery_current'], op['m_speed'], op['u_theta'], op['operation_mode'], op['ia']]
        col_name_list = ['vbat', 'current', 'mspeed', 'utheta', 'op_mode', 'ia']
        name_dict = dict(zip(col_name_list, actual_name_list))
        sym_tree = parser.parse_sym_file(op['sym_file'])
        can_msgs = tracer.parse_trace_file(op['trace_file'])
        Vb_x, Vb_y, IDC_x, IDC_y, Bh_x, Bh_y, Op_x, Op_y, Uth_x, Uth_y, Ia_x, Ia_y  = [], [], [], [], [], [], [], [], [], [], [], []
        print("read config file")
        print("total_can_msgs in trace = ", len(can_msgs))
        name_cid_dict = {}
        dict_x = {k:[] for k in col_name_list}
        dict_y = {k:[] for k in col_name_list}
        var_df_sub = sym_tree.var_df[sym_tree.var_df['var_name'].isin(name_dict.values())]
        actual_can_id_list = [msg.identifier for msg in can_msgs[0:120]]
        df_ind = [ind for ind, row in sym_tree.symbol_df.iterrows() if row['identifier'] in actual_can_id_list]
        var_df_sub = var_df_sub[var_df_sub['symbol_index'].isin(df_ind)]
        var_df_sub.drop_duplicates(subset = 'var_name', inplace = True)

        for index, row in var_df_sub.iterrows():
            key = [k for k, v in name_dict.items() if v == row['var_name']]
            var_df_sub.at[index, 'var_name'] = key[0]
            if sym_tree.symbol_df['identifier'][row['symbol_index']] not in name_cid_dict.keys():
                name_cid_dict[sym_tree.symbol_df['identifier'][row['symbol_index']]] = [key[0]]
            else:
                name_cid_dict[sym_tree.symbol_df['identifier'][row['symbol_index']]].append(key[0])

        print('name_can_id_map', name_cid_dict)
        var_df_sub.set_index('var_name', inplace = True)
        can_id_specify = [sym_tree.symbol_df['identifier'][i] for i in var_df_sub['symbol_index']]
        print('can_ids filtered', can_id_specify)
        unwrap_dict = var_df_sub.to_dict('index')
        can_take = [msg for msg in can_msgs if msg.identifier in can_id_specify]
        #can_take = [msg for msg in can_take if msg.time.time() > beg_time and msg.time.time() < end_time]
        print("can_msgs processed = " , len(can_take))

        for msg in can_take:
            name_list = name_cid_dict[msg.identifier]
            for name in name_list:
                sign = unwrap_dict[name]['signedness']
                start = unwrap_dict[name]['bit_start']
                length = unwrap_dict[name]['bit_length']
                factor = unwrap_dict[name]['factor']
                offset = unwrap_dict[name]['offset']
                encoding = unwrap_dict[name]['encoding']
                value = parser.unwrapper(msg, start, length, encoding, sign, factor, offset)
                dict_x[name].append(msg.time)
                dict_y[name].append(value)

        #for k in dict_x.keys(): print("length of", k, "array", len(dict_x[k]))

#==============equalize sizes of vbat and current based on zero order hold ==============
        st_big = 'vbat' if len(dict_x['vbat']) > len(dict_x['current']) else 'current'
        st_small = 'vbat' if st_big == 'current' else 'current'
        j = 0
        small_y = []
        len_big = len(dict_x[st_big])
        len_small = len(dict_x[st_small])

        if len_big > len_small:
            for i in range(len_big):
                if dict_x[st_small][j] > dict_x[st_big][i] and j < (len_small -1):
                    j+=1
                small_y.append(dict_y[st_small][j])
            dict_y[st_small] = small_y
            dict_x[st_small] = dict_x[st_big]

#==========================detect reverse bang time======================================
        bang_array = [dict_x['utheta'][i] for i, y in enumerate(dict_y['utheta']) if (y == -90 and dict_y['utheta'][i+1] == 90) or (y == -120 and dict_y['utheta'][i+1] == 120)]
        print("length of bang_array = ", len(bang_array))
        print("-------------------")

#===========================find where utheta > 90 ========================================
        st_utheta130_arr = [dict_x['utheta'][i+1] for i in range(len(dict_y['utheta'])-1) if dict_y['utheta'][i] <= 90 and dict_y['utheta'][i+1] > 90]
        en_utheta130_arr = [dict_x['utheta'][i+1] for i in range(len(dict_y['utheta'])-1) if dict_y['utheta'][i] >90 and dict_y['utheta'][i+1] < 90]
        d_data_mspeed = (dict_x['mspeed'][2] - dict_x['mspeed'][1]).total_seconds()
        d_data_vbat = (dict_x['vbat'][2] - dict_x['vbat'][1]).total_seconds()
        vbat_dips = []
        ibat_rises = []
        energy_comp = []
        max_power = []
        avg_power = []
        avg_vbat = []
        avg_ibat = []
        iline_rms = []
        # iline_rms_max = []
        #vbat_rises = []
        #ibat_dips = []
        #vbat_delta = []
        #vbat_ripple = []
        #ibat_ripple = []
        #ibat_delta = []

#======================================for each dead crank ===============================
        for i in range(len(st_utheta130_arr)):
            sp130_x, sp130_y = __plot_arr(dict_x['mspeed'], dict_y['mspeed'], st_utheta130_arr[i], en_utheta130_arr[i], 0)
            sp_inverted = np.multiply(sp130_y, -1)
            period = -2*60/np.mean(sp_inverted)
            dist = int(period/d_data_mspeed)
            peaks, _ = find_peaks(sp_inverted, distance = dist)#prominence = 50)
            t_peak = [sp130_x[i] for i in peaks]
            y_peak = [sp130_y[i] for i in peaks]
            ignore_comp = 2 #keep this greater than 1
            i_prev_vbat = 0
            i_prev_ibat = 0
            i_prev_ia = 0
            plt.figure()
            plt.plot(sp130_x, sp130_y)
            plt.scatter(t_peak, y_peak)
            plt.show()

            for i, tim in enumerate(t_peak):
                if i < ignore_comp: continue
                in_list = [j for j, y in enumerate(dict_x['vbat']) if y <= tim if dict_x['vbat'][j+1] >tim]
                in_list1 = [j for j, y in enumerate(dict_x['current']) if y <= tim if dict_x['current'][j+1] >tim]
                in_list2 = [j for j, y in enumerate(dict_x['ia']) if y <= tim if dict_x['ia'][j+1] >tim]
                if i > ignore_comp:
                    if (in_list[0]-i_prev_vbat) > (in_list1[0] - i_prev_ibat):
                        in_list1[0]+=1
                    elif (in_list[0]-i_prev_vbat) < (in_list1[0] - i_prev_ibat):
                        in_list[0]+=1

                    iline_rms.append(np.sqrt(np.mean(np.square(dict_y['ia'][i_prev_ia:in_list[0]]))))
                    pow_list = np.multiply(dict_y['vbat'][i_prev_vbat:in_list[0]], dict_y['current'][i_prev_ibat:in_list1[0]])
                    energy_comp.append(d_data_vbat*np.sum(pow_list))
                    max_power.append(max(pow_list))
                    avg_power.append(np.mean(pow_list))
                    avg_vbat.append(np.mean(dict_y['vbat'][i_prev_vbat:in_list[0]]))
                    avg_ibat.append(np.mean(dict_y['current'][i_prev_ibat:in_list1[0]]))
                    vbat_dips.append(min(dict_y['vbat'][i_prev_vbat:in_list[0]]))
                    #vbat_delta.append(avg_vbat[-1] - vbat_dips[-1])
                    #vbat_ripple.append(vbat_rises[-1] - vbat_dips[-1])
                    ibat_rises.append(max(dict_y['current'][i_prev_vbat:in_list1[0]]))
                    #ibat_ripple.append(ibat_rises[-1] - ibat_dips[-1])
                    #ibat_delta.append(-avg_ibat[-1] + ibat_rises[-1])
                i_prev_vbat = in_list[0]
                i_prev_ibat = in_list1[0]
                i_prev_ia = in_list2[0]

#====================================plot histograms =======================================
        f = open('deadtrace_output.csv', 'w')
        writer = csv.writer(f)
        writer.writerow(["iline_rms_avg", "iline_rms_max"])
        writer.writerow([np.mean(iline_rms), np.max(iline_rms)])

        fig= plt.figure()
        vbat_avg_val = np.average(avg_vbat)
        vbat_dips_avg = np.average(vbat_dips)
        plt.hist(vbat_dips, histtype = 'step', color = 'brown', label = 'minimum')
        plt.axvline(x = vbat_dips_avg, linestyle = ':', color = 'dimgrey')
        plt.text(vbat_dips_avg, 1.05, 'avg dips = ' + "{:.2f}".format(vbat_dips_avg)+ ' V')
        plt.hist(avg_vbat, histtype = 'step', color = 'blue', label = 'avg')
        plt.axvline(x = vbat_avg_val, linestyle = ':', color = 'dimgrey')
        plt.text(vbat_avg_val, 1.05, 'avg = ' + "{:.2f}".format(vbat_avg_val)+ ' V')
        plt.xlabel('Battery Voltage (V)')
        plt.ylabel('#thermodynamic cycles')
        plt.title('Battery Voltage per cycle')
        plt.legend()
        plt.savefig(data_folder+ 'deadtrace_vbat'+ '.png')

        # fig= plt.figure()
        # avg_vbat_delta = np.average(vbat_delta)
        # avg_vbat_ripple = np.average(vbat_ripple)
        # plt.hist(vbat_delta, histtype = 'step', color = 'brown', label = 'dip from avg')
        # plt.hist(vbat_ripple,histtype = 'step', color = 'olive', label = 'ripple around avg')
        # plt.text(avg_vbat_delta*0.9, 1.05, 'avg fire times = ' + "{:.2f}".format(avg_vbat_delta)+ ' s', transform = trans)
        # plt.text(avg_vbat_ripple*0.9, 1.05, 'avg fire times = ' + "{:.2f}".format(avg_vbat_ripple)+ ' s', transform = trans)
        # plt.xlabel('delta battery voltage (V)')
        # plt.ylabel('#thermodynamic cycles')
        # plt.title('delta_vbat')
        # plt.legend()
        # plt.savefig(data_folder + 'vbatdelta' + '.png')

        fig= plt.figure()
        ibat_avg_val = np.average(avg_ibat)
        ibat_rises_avg = np.average(ibat_rises)
        plt.hist(avg_ibat, histtype = 'step', color = 'blue', label = 'avg')
        plt.text(ibat_avg_val, 1.05, 'avg = ' + "{:.2f}".format(ibat_avg_val)+ ' A')
        plt.axvline(x = ibat_avg_val, linestyle = ':', color = 'dimgrey')
        plt.hist(ibat_rises, histtype = 'step', color = 'olive', label = 'maximum')
        plt.text(ibat_rises_avg, 1.05, 'avg rises = ' + "{:.2f}".format(ibat_rises_avg)+ ' A')
        plt.axvline(x = ibat_rises_avg, linestyle = ':', color = 'dimgrey')
        plt.legend()
        plt.title('Battery Current drawn per cycle')
        plt.xlabel('Battery Current (A)')
        plt.ylabel('#thermodynamic cycles')
        plt.savefig(data_folder+ 'deadtrace_ibat'+ '.png')

        # fig = plt.figure()
        # avg_delta_ibat = np.average(ibat_delta)
        # avg_ibat_ripple = np.average(ibat_ripple)
        # plt.hist(ibat_delta, histtype = 'step', color = 'brown', label = 'rise from avg')
        # plt.hist(ibat_ripple,histtype = 'step', color = 'olive', label = 'ripple avg')
        # plt.text(avg_delta_ibat*0.9, 1.05, 'avg fire times = ' + "{:.2f}".format(avg_delta_ibat)+ ' s', transform = trans)
        # plt.text(avg_ibat_ripple*0.9, 1.05, 'avg fire times = ' + "{:.2f}".format(avg_ibat_ripple)+ ' s', transform = trans)
        # plt.legend()
        # plt.title('delta_ibat')
        # plt.xlabel('delta battery current (A)')
        # plt.ylabel('#thermodynamic cycles')
        # plt.savefig(data_folder + 'ibatdelta' + '.png')

        fig = plt.figure()
        av_power = np.average(avg_power)
        av_max_power = np.average(max_power)
        plt.hist(avg_power, histtype = 'step', color = 'brown', label = 'avg power-out')
        plt.axvline(x = av_power, linestyle = ':', color = 'dimgrey')
        plt.text(av_power, 1.05, 'avg = ' + "{:.2f}".format(av_power)+ ' W')
        plt.hist(max_power,histtype = 'step', color = 'olive', label = 'max power-out')
        plt.axvline(x = av_max_power, linestyle = ':', color = 'dimgrey')
        plt.text(av_max_power, 1.05, 'avg = ' + "{:.2f}".format(av_max_power)+ ' W')
        plt.legend()
        plt.title('Power per cycle')
        plt.xlabel('Power (W)')
        plt.ylabel('#thermodynamic cycles')
        plt.savefig(data_folder + 'deadtrace_power' + '.png')

        fig = plt.figure()
        av_energy_comp = np.average(energy_comp)
        plt.hist(energy_comp, histtype = 'step', color = 'brown', label = 'energy consumed')
        plt.axvline(x = av_energy_comp, linestyle = ':', color = 'dimgrey')
        plt.text(av_energy_comp, 1.05, 'avg energy/cycle = ' + "{:.2f}".format(av_energy_comp)+ ' J')
        plt.legend()
        plt.title('Energy per cycle')
        plt.xlabel('Energy (J)')
        plt.ylabel('#thermodynamic cycles')
        plt.savefig(data_folder + 'deadtrace_energy' + '.png')

        f.close()
        print('check folder named isg_plots for figures')

#==================================profile time=======================================

if __name__ == "__main__":
    cli()
