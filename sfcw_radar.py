# implement state machine using Python

from utils.my_B210 import my_B210
from utils.signals import complex_sinusoid
from radar_parameters import *

# create our state machine to implement the SFCW radar

# prepare tx data
tx_data, length_wave_one_period = complex_sinusoid(samp_rate)

B210 = my_B210(samp_rate, master_clock_rate, tx_bandwidth, rx_bandwidth)

B210.init_usrp_device_time()
B210.set_gains([50, 50], [0, 0])
B210.tune_center_freq(1e9)
B210.thread_send_data(tx_data)