# implement state machine using Python

from utils.MyB210 import MyB210
from utils.signals import complex_sinusoid
from radar_parameters import *
import numpy as np
import matplotlib.pyplot as plt

# create our state machine to implement the SFCW radar

# prepare tx data
tx_data, length_wave_one_period = complex_sinusoid(samp_rate)

# construct the hardware object
B210 = MyB210(samp_rate, master_clock_rate, tx_bandwidth, rx_bandwidth)

B210.init_usrp_device_time()
B210.set_gains([50, 50], [0, 0])
B210.tune_center_freq(1e9)
B210.thread_send_data(tx_data)

# tune gains
center_freqs = np.arange(500e6, 1e9, 10e6)
txA_gain = tx_gains[0]
txB_gain = tx_gains[1]
target_rxA_amp = 0.6
target_rxB_amp = 0.6
amp_tolerence = 0.02

B210.get_gains_for_all_freqs(center_freqs, txA_gain, txB_gain, target_rxA_amp, target_rxB_amp, amp_tolerence)

# select one frequency and plot the rx signal
test_center_freq =  610000000.0
B210.tune_center_freq(test_center_freq)
B210.set_gains(tx_gains, [14.0, 40.0])  # the good rx gain for test_center_freq
B210.recv_and_save_data(B210.rx_buffer, B210.num_rx_samps)

fig, ax = plt.subplots()
ax.plot(np.real(B210.rx_buffer[1]))
B210.stop_transmit()

plt.show()


