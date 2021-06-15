
from utils.MyB210 import MyB210
from radar_parameters import *
from utils.signals import complex_sinusoid
import time

# get gain table name
gain_table_name = raw_input("Enter the gain table name: ")

# prepare data
tx_data, length_wave_one_period = complex_sinusoid(samp_rate)

# construct the hardware object
B210 = MyB210(samp_rate, master_clock_rate, tx_bandwidth, rx_bandwidth)

# transmitting data
B210.thread_send_data(tx_data)
# get gain table
start_time = time.time()
B210.get_gains_for_all_freqs(center_freqs, txA_gain, txB_gain, target_rxA_amp, target_rxB_amp, amp_tolerence)
end_time = time.time()
print("get gain table takes {} seconds".format(end_time - start_time))
# stop transmit
B210.stop_transmit()
# save gain table
B210.save_gain_table(gain_table_name)
