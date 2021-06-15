# device parameters
import numpy as np

# device parameters
samp_rate = 1e6    # sample rate of the ADC and DAC for baseband signal
master_clock_rate = 16e6   # device reference clock rate, should be larger than the samp_rate
tx_bandwidth = 0.2e6  # RF transmit filter bandwidth
rx_bandwidth = 0.2e6  # RF receiver filter bandwidth

txA_gain = 70
txB_gain = 70
target_rxA_amp = 0.6
target_rxB_amp = 0.6
amp_tolerence = 0.03



# sfcw radar parameters
start_freq = 500e6
stop_freq = 3.5e9
freq_step = 10e6

# center_freqs = np.arange(start_freq, stop_freq, freq_step)
center_freqs = [1e9, 500e6, 1.5e9, 3e9, 5e9, 6e9]
