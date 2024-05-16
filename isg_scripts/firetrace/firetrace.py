"""
- process .trc files of many normal engine starts
- plots of power, energy, reverse bang, fire times
- example config file: fireconfig.json

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
import matplotlib.pyplot as plt

def plot_arr(x, y, start, fire, relative):
    #creates arrays with given limits for ease of plotting
    y_pl, x_pl = [], []
    for i, t in enumerate(x):
        if (x[i] >= start) and  (x[i]<= fire):
            y_pl.append(y[i])
            if relative:
                x_pl.append((t-start).total_seconds())
            else:
                x_pl.append(x[i])
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

        CAL_vjump = op['vertical_speed_jump']
        CAL_idling_speed = op['idling_speed']
        CAL_htime = op['jump_time_duration']
        actual_name_list = [op['battery_voltage'], op['battery_current'], op['m_speed'], op['u_theta'], op['operation_mode']]
        col_name_list = ['vbat', 'current', 'mspeed', 'utheta', 'op_mode']
        name_dict = dict(zip(col_name_list, actual_name_list))
        sym_tree = parser.parse_sym_file(op['sym_file'])
        can_msgs = tracer.parse_trace_file(op['trace_file'])
        
        print("read config file")
        print("total_can_msgs in trace file = ", len(can_msgs))
        name_cid_dict = {}
        dict_x = dict_y = {k:[] for k in col_name_list}
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

        print('variable_name_to_can_id_map', name_cid_dict)
        var_df_sub.set_index('var_name', inplace = True)
        can_id_specify = [sym_tree.symbol_df['identifier'][i] for i in var_df_sub['symbol_index']]
        print('can_ids_filtered', can_id_specify)
        unwrap_dict = var_df_sub.to_dict('index')
        can_take = [msg for msg in can_msgs if msg.identifier in can_id_specify]
        print("number of filtered can_msgs = " , len(can_take))

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

        for k in dict_x.keys(): print("length of ", k, "array ", len(dict_x[k])) 

        #=================initialize for process op_mode=====================================
        st_array = []
        en_array = []
        bang_array = []
        int_pair = False
        n_cranks = 0
        d_data = (dict_x['mspeed'][2] - dict_x['mspeed'][1]).total_seconds()
        fire_found = False
        pass_95 = False

        curr_crank = 0
        fire_array = []
        speed95_array = []
        crank_energies = []
       
        print("jump_time_duration", CAL_htime)
        n_pt = int(CAL_htime/d_data)
        print("data points in jump_time_duration = ", n_pt)

        #==============equalize sizes of vbat and current based on zero order hold ==============
        st_big = 'vbat' if len(dict_x['vbat']) > len(dict_x['current']) else 'current'
        st_small = 'vbat' if st_big == 'current' else 'current'
        j = 0
        small_y = []
        len_big = len(dict_x[st_big])
        len_small = len(dict_x[st_small])
        print(st_big)
        print(st_small)

        if len_big > len_small:
            for i in range(len_big):
                j+=1
                if dict_x[st_small][j] > dict_x[st_big][i] and j < (len_small -1):
                    j= j -1
                small_y.append(dict_y[st_small][j])       
            dict_y[st_small] = small_y
            dict_x[st_small] = dict_x[st_big]
        
        pow_y = np.multiply(dict_y['vbat'], dict_y['current'])
        d_data_vbat = (dict_x['vbat'][2] - dict_x['vbat'][1]).total_seconds()
        
        #=================process Op_Mode and isolate cranks=====================================
        f = open('firetrace_output.csv', 'w')
        writer = csv.writer(f)
        writer.writerow(["crank_number", "energy consumed upto 95% idling", "fire_times", "bang_times"])

        for i in range(len(dict_y['op_mode'])-1):
            if dict_y['op_mode'][i] == 1 and (dict_y['op_mode'][i+1] == 4 or dict_y['op_mode'][i+1] ==2):
                st_array.append(dict_x['op_mode'][i])
                int_pair = True
            if int_pair :
                if dict_y['op_mode'][i] == 2 and (dict_y['op_mode'][i+1] == 3 or dict_y['op_mode'][i+1] == 6):
                    if (dict_x['op_mode'][i] - st_array[-1]).total_seconds() <= 2.5:
                        en_array.append(dict_x['op_mode'][i])
                        int_pair = False
                        skip_bang = False
                        n_cranks +=1
                        x_pl, y_pl = plot_arr(dict_x['mspeed'], dict_y['mspeed'], st_array[-1], en_array[-1], relative = True)
                        x_plt, y_plt = plot_arr(dict_x['mspeed'], dict_y['mspeed'], st_array[-1], en_array[-1], relative = False)
                        ux, uy = plot_arr(dict_x['utheta'], dict_y['utheta'], st_array[-1], en_array[-1], relative = True)
                        barr = [ux[i] for i, y in enumerate(uy) if y == -90 if uy[i+1] == 90]
                        print('n_cranks = ', n_cranks)
                        print('st_time= ', st_array[-1])
                        print('en_time = ', en_array[-1])
                        if not barr : barr = [ux[i] for i, y in enumerate(uy) if y == -120 if uy[i+1] == 120]
                        if not barr: 
                            print ('barr is empty, successful crank without reverse bang')
                            barr = [ux[i] for i, y in enumerate(uy) if y == 120]
                            bang_time = barr[0]
                            bang_array.append(barr[0])
                        else:
                            bang_time = barr[0]
                            bang_array.append(barr[0])
                        print("barr[0] = ", barr[0])
                        for j in range(len(x_pl)):
                            if x_pl[j] > bang_time:
                                if not fire_found:
                                    g_1 = y_pl[j+1] - y_pl[j]
                                    g = y_pl[j+n_pt] - y_pl[j]
                                    if g >= CAL_vjump and g_1 >=0 and y_pl[j] > 0.1*CAL_idling_speed:
                                        fire_array.append(x_pl[j])
                                        fire_time = x_pl[j]
                                        fire_found = True
                                        print('fire_found = ', fire_found)
                                if not pass_95 and y_pl[j] >= 0.95*CAL_idling_speed:
                                    speed95_array.append(x_pl[j])
                                    speed95_time = x_plt[j]
                                    pass_95 = True
                                    print('pass_95 = ', pass_95)
                                if not fire_found and pass_95:
                                    print('fire time not found for ', n_cranks, 'th bang, bang skipped')
                                    print('try changing fire detect parameters in config file')
                                    fire_found = False
                                    pass_95 = False
                                    skip_bang = True
                                    break
                                if fire_found and pass_95:
                                    fire_found = False
                                    pass_95 = False
                                    break
                        if not skip_bang:
                            pow_xpl, pow_ypl = plot_arr(dict_x['vbat'], pow_y, st_array[-1], en_array[-1], relative = True) 
                            pow95x, pow95y = plot_arr(dict_x['vbat'], pow_y, st_array[-1], speed95_time, relative = True)
                            crank_energies.append(np.sum(pow95y)*d_data_vbat)
                            writer.writerow([n_cranks, crank_energies[-1], fire_time, bang_time])
                            fig = plt.figure()
                            ax = fig.add_subplot(111)
                            fig.subplots_adjust(right=0.8)
                            ax.plot(pow_xpl, pow_ypl, 'royalblue')
                            ax.set_ylabel('Power-out(W)')
                            ax.spines['left'].set_color('royalblue')
                            ax.tick_params(axis = 'y', colors = 'royalblue', which='both')
                            ax.yaxis.label.set_color('royalblue')

                            ax2 = ax.twinx()
                            ax2.plot(x_pl, y_pl, 'brown')
                            ax2.set_ylabel('Speed(RPM)')
                            ax2.spines['right'].set_color('brown')
                            ax2.tick_params(axis = 'y', colors = 'brown', which='both')
                            ax2.yaxis.label.set_color('brown')

                            plt.axvline(x = fire_time, linestyle = ':', color = 'dimgrey')
                            plt.axvline(x = bang_time, linestyle = ':', color = 'dimgrey')
                            ax.set_xlabel('time(sec)')

                            trans = ax.get_xaxis_transform()
                            plt.text(fire_time*0.9, 1.05, 'engine fired at ' + "{:.2f}".format(fire_time)+ ' s', transform = trans)
                            plt.text(bang_time*0.5, 1.05, 'reverse bang at ' + "{:.2f}".format(bang_time)+ ' s', transform = trans)
                            fig.savefig(data_folder + str(n_cranks) + '.png')
                            plt.close()
                        
                    else:
                        st_array.pop()
                        int_pair = False
                if (dict_x['op_mode'][i] - st_array[-1]).total_seconds() > 2.5 or dict_x['op_mode'] == 5 or dict_x['op_mode'] == 7:
                    st_array.pop()
                    int_pair = False

        print("number of cranks = " + str(n_cranks))
        print("--------------------------------")

#=================================== plotting histograms =============================
        fig = plt.figure()
        plt.hist(fire_array)
        av_fire_time = np.average(fire_array)
        plt.axvline(x = av_fire_time, linestyle = ':', color = 'dimgrey')
        plt.text(av_fire_time, 1.0, 'avg fire times = ' + "{:.2f}".format(av_fire_time)+ ' s')
        plt.xlabel('time (sec)')
        plt.ylabel('# of starts')
        fig.suptitle('Time upto Engine Fire (sec)')
        fig.savefig(data_folder + 'firetrace_firehist' + '.png')
        

        fig = plt.figure()
        plt.hist(bang_array)
        av_bang_time = np.average(bang_array)
        plt.axvline(x = av_bang_time, linestyle = ':', color = 'dimgrey')
        plt.text(av_bang_time, 1.0, 'avg bang time = ' + "{:.2f}".format(av_bang_time)+ ' s')
        plt.xlabel('time (sec)')
        plt.ylabel('# of starts')
        fig.suptitle('Time upto Reverse Bang (sec)')
        fig.savefig(data_folder + 'firetrace_banghist' + '.png')

        fig = plt.figure()
        plt.hist(crank_energies)
        av_energy = np.average(crank_energies)
        plt.axvline(x = av_energy, linestyle = ':', color = 'dimgrey')
        plt.text(av_energy, 1.0, 'avg energy = ' + "{:.2f}".format(av_energy)+ ' J')
        plt.xlabel('energy (J)')
        plt.ylabel('# of starts')
        fig.suptitle('Energy Consumed upto 95% Idling (J)')
        fig.savefig(data_folder + 'firetrace_en95hist' + '.png')
        plt.close()

        print('check isg_plots for figures and firetrace_output for numbers')

        writer.writerow(['avg', av_energy, av_fire_time, av_bang_time])
        f.close()
        print("--------------------------")
        print('processed trace file = ', op['trace_file'])
        print("--------------------------")

        sys.exit()

if __name__ == "__main__":
    cli()
