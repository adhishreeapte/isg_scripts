#charging assist efficiency, voltage ripple norm value, energy consumed
import os
import click
import sys
import json as json
import numpy as np
import pandas as pd
import math as math
import matplotlib.pyplot as plt
import pycan.sym as parser
import pycan.trace as tracer
from datetime import datetime as dtime
from datetime import time as ddtime
from datetime import timedelta as timedelta


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
    #main function
    if not os.path.exists(config):
        print('{} file not found'.format(config))
        sys.exit()

    op_points = []
    with open(config, 'r') as f:
        op_points = json.load(f)

    for op in op_points:
        b = op['begin_time']
        beg_time = ddtime(b[0], b[1], b[2])
        e = op['end_time']
        end_time = ddtime(e[0], e[1], e[2])
        Rs = op['Rs']
        aorc = op['a_or_c']
        actual_name_list = [op['battery_voltage'], op['battery_current'], op['assist_state'], op['charge_state'], op['ia'], op['ib'], op['ic']]
        col_name_list = ['vbat', 'current', 'ast', 'cst', 'ia', 'ib', 'ic']
        name_dict = dict(zip(col_name_list, actual_name_list))
        sym_tree = parser.parse_sym_file(op['sym_file'])
        can_msgs = tracer.parse_trace_file(op['trace_file'])
        print('config file read')
        
        print("total_can_msgs in trace file = ", len(can_msgs))
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

        print('variable_name_to_can_id_map', name_cid_dict)
        var_df_sub.set_index('var_name', inplace = True)
        can_id_specify = [sym_tree.symbol_df['identifier'][i] for i in var_df_sub['symbol_index']]
        print('can_ids_filtered', can_id_specify)
        unwrap_dict = var_df_sub.to_dict('index')
        can_take = [msg for msg in can_msgs if msg.identifier in can_id_specify]
        can_take = [msg for msg in can_take if msg.time.time() < end_time and msg.time.time() > beg_time]
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


        if dict_y['cst'] == []:
            print("Array not populated, pls check file names")
            sys.exit()
        
        #==========================energy consumed and efficiency======================================
        st_time = 0
        en_time = 0
        arr_x, arr_y = [], []
        state = 0
        print("user input charging" if aorc == "c" else "user input assist")

        if aorc == "c":
            arr_x = dict_x['cst']
            arr_y = dict_y['cst']
            state = 1
        else:
            arr_x = dict_x['ast']
            arr_y = dict_y['ast']
            state = 2

        for i in range(len(arr_x)):
            if st_time == 0 and arr_y[i] == state:
                st_time = arr_x[i]
            if en_time == 0 and arr_y[-1*i] == state:
                en_time = arr_x[-1*i]
            if st_time !=0 and en_time !=0:
                break
        print("start_time = " , st_time)
        print("end_time = ", en_time)
        print('------------------------------')

        e_bat = 0
        v_sq = 0
        v_s = 0
        n = 0
        for i, t in enumerate(dict_x['vbat']):
            #if t != st_time and t != en_time:
            if i != len(dict_x['vbat']) -1:
                e_bat += dict_y['vbat'][i]*dict_y['current'][i]*((dict_x['vbat'][i+1] - dict_x['vbat'][i]).total_seconds())
                v_sq += dict_y['vbat'][i]**2
                v_s += dict_y['vbat'][i]
                n += 1

        v_ripple = math.sqrt( ((v_sq/n) - ((v_s/n)**2)) )
        print("Voltage ripple = " + "{:.3f}".format(v_ripple) + " V")
        print('------------------------------')
        print("Energy flowing out of battery = " + "{:.2f}".format(e_bat) + " J")
        print('------------------------------')

        e_loss = 0
        for i, t in enumerate(dict_x['ia']):
            #if t > st_time and t < en_time:
            if i != len(dict_x['ia']) -1:
                e_loss += Rs*1e-3*( (dict_y['ia'][i]**2)+ (dict_y['ib'][i]**2) + (dict_y['ic'][i]**2) )*( (dict_x['ia'][i+1] - dict_x['ia'][i]).total_seconds() )
        print("Energy of copper losses = " + "{:.2f}".format(e_loss) + " J")
        print('------------------------------')

        if aorc == 'c':
            eta = -1*e_bat/(-1*e_bat + e_loss)
        else:
            eta = 1 - (e_loss/e_bat)

        print("Efficiency = " + "{:.3f}".format(eta))
        print('------------------------------')

if __name__ == "__main__":
    cli()
