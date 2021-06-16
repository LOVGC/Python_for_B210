
from utils.MyB210 import MyB210
from radar_parameters import *
import numpy as np
from utils.signals import complex_sinusoid

import time
import scipy.io
import os
# get gain table name
gain_table_name = input("Enter the gain table name that you want to load: ")
sfcw_rx_signal_name = input("Enter the file name for the sfcw_rx_signal: ")

# prepare data
tx_data, length_wave_one_period = complex_sinusoid(samp_rate)

# construct the hardware object
B210 = MyB210(samp_rate, master_clock_rate, tx_bandwidth, rx_bandwidth)
B210.load_gain_table(gain_table_name)

start_time = time.time()
sfcw_rx_signal, center_freqs = B210.sfcw_seep(tx_data, center_freqs, txA_gain, txB_gain)
end_time = time.time()
print("sfcw radar survey takes {} seconds".format(end_time - start_time))
# stop transmit
B210.stop_transmit()

# save data
# np.save("./data/npy_data/channel_data_{}.npy".format(sfcw_rx_signal_name), sfcw_rx_signal)

# syntax:
#   scipy.io.savemat(<string: file path>, <dictionary: {variable_name : numpy data}>)

# file path
file_path = "./data/matlab_data/channel_data_{}.mat".format(sfcw_rx_signal_name)

with open(file_path,'wb') as f:  # need 'wb' in Python3
    scipy.io.savemat(f, {"channel_data_{}".format(sfcw_rx_signal_name): sfcw_rx_signal} )
    scipy.io.savemat(f, {"center_freqs": center_freqs})

# Beep when finish
duration = 0.3  # second
freq = 440
os.system("play -nq -t alsa synth {} sine {}".format(duration, freq))