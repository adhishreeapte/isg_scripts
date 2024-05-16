import numpy as np
import matplotlib.pyplot as plt
import csv
from scipy import signal
import sys
import click
import os

pi = np.pi

@click.command()
@click.option('--file_name',
              type = str,
              prompt = 'Enter file name containing raw data: ',
              required = True,
              help = 'File name containing raw data')

#file_name = input('Enter file name containing raw data: ')
def cli(file_name):
  data_folder = 'isg_plots/'
  if not os.path.exists(data_folder):
    os.makedirs(data_folder)

  with open(file_name, 'r') as file:
    csvreader = csv.reader(file)
    # count number of rows
    row_count = sum(1 for row in csvreader) - 3

  # extracting raw speed sensor and throttle sensor data
  with open(file_name, mode ='r') as csvfile:
    # reading the CSV file
    csvreader = csv.reader(csvfile)
    line_count = 0
    time_arr = np.zeros(row_count)
    print(row_count)
    speed_sensor_data_arr = np.zeros(row_count)
    throttle_sensor_data_arr = np.zeros(row_count)
    for row in csvreader:
      line_count += 1
      if line_count >= 4:
        time_arr[line_count-4]= float(row[0])
        speed_sensor_data_arr[line_count-4]= float(row[1])
        throttle_sensor_data_arr[line_count-4] = float(row[2])

  time_arr = np.array(time_arr)
  speed_sensor_data_arr = np.array(speed_sensor_data_arr)
  throttle_sensor_data_arr = np.array(throttle_sensor_data_arr)
  speed_sensor_data_procsd_arr = np.zeros(len(time_arr), dtype=int)
  throttle_sensor_data_procsd_arr = np.zeros(len(time_arr), dtype=int)
  # plt.subplots()
  # plt.plot(time_arr, speed_sensor_data_arr)
  # plt.show()
  #----------------------------------------------------------------------------------
  #processing speed sensor and throttle sensor data
  speed_sensor_Thr = 2.5;
  speed_sensor_His = 1;
  speed_sensor_state = 0;
  if speed_sensor_data_arr[1] > 2.5:
    speed_sensor_state = 1;


  for i in range(len(time_arr)):
      if speed_sensor_state == 1:
          if speed_sensor_data_arr[i] < speed_sensor_Thr - speed_sensor_His:
              speed_sensor_data_procsd_arr[i] = 0
              speed_sensor_state = 0
          else:
              speed_sensor_data_procsd_arr[i] = 1

      else:
          if speed_sensor_data_arr[i] > speed_sensor_Thr + speed_sensor_His:
              speed_sensor_data_procsd_arr[i] = 1
              speed_sensor_state = 1
          else:
              speed_sensor_data_procsd_arr[i] = 0

  throttle_sensor_Thr = 2.5;
  throttle_sensor_His = 1.5;
  throttle_sensor_state = 0;
  if throttle_sensor_data_arr[1] > 2.5:
    throttle_sensor_state = 1;

  for i in range(len(time_arr)):
      if throttle_sensor_state == 1:
          if throttle_sensor_data_arr[i] < throttle_sensor_Thr - throttle_sensor_His:
              throttle_sensor_data_procsd_arr[i] = 0
              throttle_sensor_state = 0
          else:
              throttle_sensor_data_procsd_arr[i] = 1

      else:
          if throttle_sensor_data_arr[i] > throttle_sensor_Thr + throttle_sensor_His:
              throttle_sensor_data_procsd_arr[i] = 1
              throttle_sensor_state = 1
          else:
              throttle_sensor_data_procsd_arr[i] = 0

  #--------------------------------------------------------------------------
  ## Speed Calculations
  speed_sensor_data_change_arr = speed_sensor_data_procsd_arr[1:] - speed_sensor_data_procsd_arr[0:-1]

  # rising edge detection
  rising_edge_index_arr = np.where(speed_sensor_data_change_arr==1)
  rising_edge_index_arr = rising_edge_index_arr[0]
  interrupt_time_arr = np.zeros(len(rising_edge_index_arr))
  speed_arr = np.zeros(len(rising_edge_index_arr))

  for k, index in enumerate(rising_edge_index_arr):
    interrupt_time_arr[k]= time_arr[index]
    if k > 0:
      delta_t = interrupt_time_arr[k] - interrupt_time_arr[k-1]
      speed_arr[k] = (2*pi*.223*1e-3*60)*((60/47)*1/delta_t);

  speed_zoh_arr = np.zeros(len(time_arr)) #zero order hold speed array

  index_time_sparse = 0
  for n, time in enumerate(time_arr):
    if index_time_sparse < len(speed_arr) -1:
      if time > interrupt_time_arr[index_time_sparse+1]:
        index_time_sparse += 1
      speed_zoh_arr[n] = speed_arr[index_time_sparse]
    else:
      speed_zoh_arr[n] = speed_arr[-1]

  #speed filtering

  speed_filtered_arr = speed_zoh_arr.copy()
  delta_t = time_arr[1] - time_arr[0]
  cutt_off_freq = 10 #in Hertz
  tau = 1/(2*pi*cutt_off_freq)
  for k, raw_speed in enumerate(speed_zoh_arr):
    if k > 0:
      filtered_speed = speed_filtered_arr[k-1]+(raw_speed - speed_filtered_arr[k-1])*delta_t/tau
      speed_filtered_arr[k] = filtered_speed

  # rising edge detection for throttle
  throttle_sensor_data_change_arr = throttle_sensor_data_procsd_arr[1:] - throttle_sensor_data_procsd_arr[0:-1]
  throttle_rising_edge_index_arr = np.where(throttle_sensor_data_change_arr==1)
  throttle_rising_edge_index_arr = throttle_rising_edge_index_arr[0]
  start_time_arr = np.zeros(len(throttle_rising_edge_index_arr))

  # computing acceleration time
  for k, index in enumerate(throttle_rising_edge_index_arr):
    start_time_arr[k]= time_arr[index]

  num_trials = len(throttle_rising_edge_index_arr)

  time_stamp_speeds = np.zeros([num_trials, 6])

  for k in range(num_trials):
    # computing time stamps for kth trial

    start_time = start_time_arr[k]
    kmph_state = 1
    for m, time in enumerate(time_arr):
      if time >= start_time_arr[k]:
        if kmph_state == 1:
          if speed_filtered_arr[m] >= 10: #KMPH

            time_stamp_speeds[k][0] = time - start_time
            kmph_state = 2

        elif kmph_state == 2:
          if speed_filtered_arr[m] >= 20: #KMPH
            time_stamp_speeds[k][1] = time - start_time

            kmph_state = 3

        elif kmph_state == 3:
          if speed_filtered_arr[m] >= 30: #KMPH
            time_stamp_speeds[k][2] = time - start_time

            kmph_state = 4

        elif kmph_state == 4:
          if speed_filtered_arr[m] >= 40: #KMPH
            time_stamp_speeds[k][3] = time - start_time

            kmph_state = 5

        elif kmph_state == 5:
          if speed_filtered_arr[m] >= 50: #KMPH
            time_stamp_speeds[k][4] = time - start_time

            kmph_state = 6

        elif kmph_state == 6:
          if speed_filtered_arr[m] >= 60: #KMPH
            time_stamp_speeds[k][5] = time - start_time

            break
          else:
            time_stamp_speeds[k][5] = np.nan

  result_file_name = 'output_speedtime.csv'
  fields = ['10 KMPH', '20 KMPH', '30 KMPH', '40 KMPH', '50 KMPH', '60 KMPH']


  with open(result_file_name, 'w', newline='') as csvfile:
      # creating a csv writer object
      csvwriter = csv.writer(csvfile)

      # writing the fields
      csvwriter.writerow(fields)

      # writing the data rows
      csvwriter.writerows(time_stamp_speeds)

  fig, ax1 = plt.subplots()
  ax2 = ax1.twinx()
  p1,  = ax1.plot(time_arr, speed_filtered_arr, label = 'Filtered linear speed', color='blue')
  p2,  = ax2.plot(time_arr, throttle_sensor_data_arr, label= 'throttle sensor output', color='orange')
  ax1.set_xlabel('time(s)')
  ax1.set_ylabel('Voltage (V)')
  ax2.set_ylabel('speed(kmph)')

  ax1.yaxis.label.set_color(p1.get_color())
  ax2.yaxis.label.set_color(p2.get_color())

  h1, l1 = ax1.get_legend_handles_labels()
  h2, l2 = ax2.get_legend_handles_labels()
  ax1.legend(h1 + h2, l1 + l2 , loc='right')
  ax1.grid(axis='both', which='major', alpha=0.35)
  ax2.grid(axis='both', which='major', alpha=0.35)
  
  plt.savefig(data_folder + 'output_speedtime' + '.png')
  plt.show()


if __name__ == "__main__":
  cli()
