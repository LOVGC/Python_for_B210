import uhd
from uhd import libpyuhd as lib
import numpy as np
from threading import Thread



class MyB210():
###################################################################################################################
# Define some staticmethod in the class as utility functions
###################################################################################################################
    # Class Attributes

    # the number of samples of the baseband signal in one period:
    # will affect the self.buffer size
    LengthOnePeriod = 1000

    @staticmethod
    def estimate_amp(rx_buffer_one_channel):
        """
        :param rx_buffer_one_channel: the rx_buffer_one_channel is a numpy 1 by N array of complex numbers
        :return: amp
                the estimated rx amplitude of the signals stored in the rx_buffer
        """
        # using the simple average method to estimate amplitude
        amp = np.mean(np.absolute(rx_buffer_one_channel))

        return amp

#################################################################################################################
# This is the basic functions for USRP B210
################################################################################################################
    def __init__(self, samp_rate, master_clock_rate, tx_bandwidth, rx_bandwidth, tx_gains=[0, 0], rx_gains=[0, 0]):
        """
        :param samp_rate: the sample rate of the ADC and DAC
        :param master_clock_rate: the base clock rate that is used as a reference clock for the ADC and DAC and the FPGA
        :param tx_bandwidth: the filter bandwidth for the tx chain
        :param rx_bandwidth: the filter bandwidth for the rx chain
        :param tx_gains: 0 -- 89.8 dB of available gain; the first element is for txA gain, the second element is for txB gain
        :param rx_gains: 0 -- 76 dB of available gain; the first element is for rxA gain, the second element is for rxB gain

        the key attributes of a my_B210 object is:
        self.usrp
        self.tx_streamer
        self.rx_streamer

        self.transmit_flag  # used to kill the tx_thread when done

        self.num_rx_samps : the number of rx samples in the self.rx_buffer
        self.rx_buffer : a 2 by self.num_rx_samps numpy array of complex64 numbers

        self.gain_table = {} : this gain_table stores the key-value pairs of {center_freq: [rxA_gain, rxB_gain]}
        """

        # construct some flags
        self.transmit_flag = False  # used to kill the tx_thread when done
        self.gain_table_updated_flag = False # only self.get_gains_for_all_freqs() and self.load_gain_table() can set it to True

        # the num_rx_samps
        self.num_rx_samps =  10 * MyB210.LengthOnePeriod

        # the sample rate of the baseband signal
        self.samp_rate = samp_rate

        # construct the rx_buffer
        self.rx_buffer = np.zeros((2, self.num_rx_samps), dtype=np.complex64)

        # construct the gain_table
        self.gain_table = {}   # this gain_table stores the key-value pairs of {center_freq: [rxA_gain, rxB_gain]}


        # construct the tx_streamer and tx_streamer
        args = "type = b200"

        # create a usrp device and set up it with the device parameters defined above
        self.usrp = uhd.usrp.MultiUSRP(args)

        # set clock ant time
        freq_clock_source = "internal"
        self.usrp.set_clock_source(
            freq_clock_source
        )  # this sets the source of the frequency reference, typically a 10 MHz signal
        self.usrp.set_master_clock_rate(master_clock_rate)

        # select subdevices: the RF frontend tx chains and rx chains
        subdevice = "A:A A:B"  # select subdevice in the daughterboard
        subdevice_spec = lib.usrp.subdev_spec(subdevice)
        self.usrp.set_rx_subdev_spec(subdevice_spec)
        self.usrp.set_tx_subdev_spec(subdevice_spec)
        print("Using Device: {}".format(self.usrp.get_pp_string()))

        # set sample rate of ADC/DAC
        channel_list = (0, 1)  # 0 represents channel A, 1 represents channel B
        self.usrp.set_tx_rate(samp_rate)  # this will set over all channels
        self.usrp.set_rx_rate(samp_rate)
        print("Actual RX0 rate: {} Msps".format(self.usrp.get_rx_rate(0) / 1e6))
        print("Actual RX1 rate: {} Msps".format(self.usrp.get_rx_rate(1) / 1e6))
        print("Actual TX0 rate: {} Msps".format(self.usrp.get_tx_rate(0) / 1e6))
        print("Actual TX1 rate: {} Msps".format(self.usrp.get_tx_rate(1) / 1e6))

        # set the bandwidth of the RF frontend tx and rx filters
        self.usrp.set_tx_bandwidth(tx_bandwidth, channel_list[0])
        self.usrp.set_tx_bandwidth(tx_bandwidth, channel_list[1])
        self.usrp.set_rx_bandwidth(rx_bandwidth, channel_list[0])
        self.usrp.set_rx_bandwidth(rx_bandwidth, channel_list[1])
        print("Actual RX0 bandwidth = {} MHz".format(self.usrp.get_rx_bandwidth(0) / 1e6))
        print("Actual RX1 bandwidth = {} MHz".format(self.usrp.get_rx_bandwidth(1) / 1e6))
        print("Actual TX0 bandwidth = {} MHz".format(self.usrp.get_tx_bandwidth(0) / 1e6))
        print("Actual TX1 bandwidth = {} MHz".format(self.usrp.get_tx_bandwidth(1) / 1e6))

        # set front end gain
        self.usrp.set_rx_gain(rx_gains[0], channel_list[0])
        self.usrp.set_rx_gain(rx_gains[1], channel_list[1])
        self.usrp.set_tx_gain(tx_gains[0], channel_list[0])
        self.usrp.set_tx_gain(tx_gains[1], channel_list[1])
        print("Actual RX0 gain: {}".format(self.usrp.get_rx_gain(0)))
        print("Actual RX1 gain: {}".format(self.usrp.get_rx_gain(1)))
        print("Actual TX0 gain: {}".format(self.usrp.get_tx_gain(0)))
        print("Actual TX1 gain: {}".format(self.usrp.get_tx_gain(1)))

        # create stream args and tx streamer
        st_args = lib.usrp.stream_args("fc32", "sc16")
        st_args.channels = channel_list

        self.tx_streamer = self.usrp.get_tx_stream(st_args)  # create tx streamer
        self.rx_streamer = self.usrp.get_rx_stream(st_args)  # create rx streamer

    def init_usrp_device_time(self):
        """
        set the usrp device time to zero
        """
        self.usrp.set_time_now(lib.types.time_spec(0.0))

    def set_gains(self, tx_gains, rx_gains):
        """
        :param tx_gains: a list that specify the tx gains;  0 -- 89.8 dB of available gain;
        :param rx_gains: a list that specify the rx gains;  0 -- 76 dB of available gain;
        example
        tx_gains = [10, 20] will set txA_gain to be 10 dB and txB_gain to be 20 dB
        """
        self.usrp.set_rx_gain(rx_gains[0], 0)
        self.usrp.set_rx_gain(rx_gains[1], 1)
        self.usrp.set_tx_gain(tx_gains[0], 0)
        self.usrp.set_tx_gain(tx_gains[1], 1)  # we don't use tx1, thus set the gain to zero

    def tune_center_freq(self, target_center_freq):
        """
        usrp is a MultiUSRP device object
        tune the tx/rx LO to target_center_freq
        wait until the LO's are all locked.
        Then tell all threads the lo is OK by setting the tune_OK_s to True
        """

        # tune center freqs on all channels
        self.usrp.set_rx_freq(lib.types.tune_request(target_center_freq), 0)
        self.usrp.set_rx_freq(lib.types.tune_request(target_center_freq), 1)
        self.usrp.set_tx_freq(lib.types.tune_request(target_center_freq), 0)
        self.usrp.set_tx_freq(lib.types.tune_request(target_center_freq), 1)

        # wait until the lo's are locked, or maybe just put some time delay here?
        while not (
                self.usrp.get_rx_sensor("lo_locked", 0).to_bool() and
                self.usrp.get_tx_sensor("lo_locked", 0).to_bool()
        ):
            pass

    def send_data_once(self, tx_data, tx_md = lib.types.tx_metadata()):
        """
        Notice: when sending data, the CPU is fully occupied, thus we need threading for parallel running
        sending data and receiving data.

        :param tx_data: should be an numpy array with dimension 2 by N, where
                        1) the elements are of type complex64 and 2) the first row of I/Q data is
                        sent to the tx channelA and the second row of I/Q data is sent to the tx channelB
        :param tx_md: tx metadata
        """
        self.tx_streamer.send(tx_data, tx_md)

    def send_data_cont(self, tx_data, tx_md = lib.types.tx_metadata()):
        while True:
            if not self.transmit_flag:
                break
            self.tx_streamer.send(tx_data, tx_md)

    def thread_send_data(self, tx_data, tx_md = lib.types.tx_metadata()):
        self.transmit_flag = True

        tx_thread = Thread(target=self.send_data_cont, args=(tx_data, tx_md))
        tx_thread.start()
        print("tx thread begins")

    def stop_transmit(self):
        self.transmit_flag = False
        print("Stop Transmit")

    def recv_and_save_data(self, rx_buffer, num_rx_samps, rx_md = lib.types.rx_metadata()):
        """
        This method fetches the rx data from the hardware into the rx_buffer provided by the user.

        :param rx_buffer: should be an numpy array with dimension 2 by num_rx_samps, where
                        1) the elements are of type complex64 and 2) the first row of I/Q data is
                        obtained from the rx buffer in channelA and the second row of I/Q data is
                        obtained from the tx buffer in channelB
                        the received data is stored in the rx_buffer.

        :param num_rx_samps: how many I/Q samples to receive
        :param rx_md: rx metadata
        """
        if not self.transmit_flag:
            raise Exception('B210 is not transmitting')


        stream_cmd = lib.types.stream_cmd(lib.types.stream_mode.num_done)
        stream_cmd.num_samps = num_rx_samps
        stream_cmd.stream_now = False
        stream_cmd.time_spec = self.usrp.get_time_now() + lib.types.time_spec(0.01)
        self.rx_streamer.issue_stream_cmd(stream_cmd)  # tells all channels to stream

        self.rx_streamer.recv(rx_buffer, rx_md)


    ###############################################################################################
    #  The following sections are for gain tuning
    ################################################################################################
    def _get_gain_for_one_channel_one_center_freq(self, channel, center_freq, tx_gain, target_rx_amp, amp_tolerence):
        """
        Given a center_freq, tx_gain, target_rx_amp, amp_tolerence,
        this helper method finds a good rx gain for the channel.

        :param channel: 0 for channelA, 1 for channelB
        :param center_freq: center_freq for the channel
        :param tx_gain: tx_gain for the channel
        :param target_rx_amp: target rx signal amplitude for the channel
        :param amp_tolerence:
        :return: the good rx gain for the channel
        """

        # suppose the transmitter is turned on through self.thread_send_data()
        if not self.transmit_flag:
            raise Exception('B210 is not transmitting')

        # set hardware parameters
        self.tune_center_freq(center_freq)
        self.usrp.set_tx_gain(tx_gain, channel)
        self.usrp.set_rx_gain(0, channel)

        # the following is a simple tuning algorithm
        # loop init
        self.recv_and_save_data(self.rx_buffer, self.num_rx_samps)  # receive data
        estimated_amp = MyB210.estimate_amp(self.rx_buffer[channel])  # get estimated_amp of the channel

        while not (
                estimated_amp >= target_rx_amp - amp_tolerence
                and estimated_amp <= target_rx_amp + amp_tolerence
        ):
            # if estimated_amp is too small
            if estimated_amp < target_rx_amp - amp_tolerence :
                rx_gain_current = self.usrp.get_rx_gain(channel)
                if rx_gain_current <= 76:
                    self.usrp.set_rx_gain(rx_gain_current + np.random.uniform(1.21, 5.7), channel)
                    print(
                        "trying rx: {} gain {} for frequency {} GHz".format(
                            channel , self.usrp.get_rx_gain(channel), center_freq / 1e9
                        )
                    )
                else:
                    print(
                        "current frequency {} can not be tuned to target amplitude, rx_gain can not exceed 76dB".format(
                            center_freq
                        )
                    )
                    break

            # else if amp is too large
            elif estimated_amp > target_rx_amp + amp_tolerence:
                rx_gain_current = self.usrp.get_rx_gain(channel)
                if rx_gain_current > 0:
                    self.usrp.set_rx_gain(rx_gain_current - np.random.uniform(0.2, 2.3), channel)
                    print(
                        "trying rx: {} gain {} for frequency {} GHz".format(
                            channel ,self.usrp.get_rx_gain(channel) , center_freq / 1e9
                        )
                    )
                elif rx_gain_current < 0:
                    print(
                        "current frequency {} can not be tuned to target amplitude, rx_gain can not be less than 0dB".format(
                            center_freq
                        )
                    )
                    break

            # update the rx_buffer for next loop
            self.recv_and_save_data(self.rx_buffer, self.num_rx_samps)  # receive data
            estimated_amp = MyB210.estimate_amp(self.rx_buffer[channel])  # get estimated_amp of the channel


        # when it is outside the loop, the amp should be within the range
        good_rx_gain = self.usrp.get_rx_gain(channel)
        print(
            "current frequency is {}, the good rx:{} gain is rx_gain = {}".format(
                center_freq, channel, good_rx_gain
            )
        )

        return good_rx_gain

    def get_gains_for_all_freqs(self, center_freqs, txA_gain, txB_gain, target_rxA_amp, target_rxB_amp, amp_tolerence):
        """
        This method get good gains for all freqs
        Then, set the self.gain_table_updated_flag to True

        :param center_freqs: [f1, f2, f3, ...], a list a center freqs that you want to tune the rx gain for
        :param txA_gain: 0 to 89.8dB
        :param txB_gain: 0 to 89.8dB
        :param target_rxA_amp: 0 to 1
        :param target_rxB_amp: 0 to 1
        :param amp_tolerence: a small positive number, like 0.2, 0.3
        :return: stores the good gains in the gain table
        """

        for f in center_freqs:
            # get the good rx gain for rxA
            good_rxA_gain = self._get_gain_for_one_channel_one_center_freq(0, f, txA_gain, target_rxA_amp, amp_tolerence)
            good_rxB_gain = self._get_gain_for_one_channel_one_center_freq(1, f, txB_gain, target_rxB_amp, amp_tolerence)

            # store the gain table
            self.gain_table[f] = [good_rxA_gain, good_rxB_gain]

        self.gain_table_updated_flag = True

    def save_gain_table(self, file_name):
        """
        file_name: string, the file name
        This method save the current self.gain_table into a file in utils for later use
        The file will be overwritten if it exists
        """
        np.save('./utils/gain_tables/{}.npy'.format(file_name), self.gain_table)
        print('gain table is saved into ./utils/gain_tables/{}.npy'.format(file_name))

    def load_gain_table(self, file_name):
        """
        file_name: string, the gain table name without postfix

        load a gain table into self.gain_table for use
        :return:
        """
        self.gain_table = np.load('./utils/gain_tables/{}.npy'.format(file_name),allow_pickle='TRUE').item()
        if type(self.gain_table) is not dict:
            raise Exception('gain table should be a python dictionary object')

        self.gain_table_updated_flag = True
        print('successfully loading ./utils/gain_tables/{}.npy into self.gain_table'.format(file_name))

    ###############################################################################################
    #  The following sections are for performing the SFCW radar function: an application program
    ################################################################################################

    def sfcw_seep(self, tx_data, center_freqs, txA_gain, txB_gain):
        """
        This method performs the sfcw sweep at one survey location, using the txA_gain and txB_gain as the
        transmit gains and self.gain_table as the rx gains.

        :param tx_data : the tx baseband signal
        :param center_freqs: the center_freqs at which you want to sweep
        :param txA_gain: channel A transmit gain
        :param txB_gain: channel B transmit gain
        :return: sfcw_rx_signal, center_freqs
            the received baseband signals obtained by using the txA_gain and txB_gain as the
            transmit gains and self.gain_table as the rx gains at each center_freq.

            the data structure looks like
            sfcw_rx_signal = a list of
                <a 2 by self.num_rx_samps numpy array of complex64 numbers; with the first row for rxA I/Q data and the second row for rxB I/Q data  >
                           = [rx_data at the first freq, rx_data at the second freq, ... ]

            center_freqs = [first_freq, second_freq, ...]

        """
        if not self.gain_table_updated_flag:
            raise Exception('Gain table is not updated')

        # prepare transmit data

        # set the tx gains
        self.usrp.set_tx_gain(txA_gain, 0)
        self.usrp.set_tx_gain(txB_gain, 1)
        # turn on the thread_send_data
        self.thread_send_data(tx_data)

        # loop through the center_freqs
        #      1. set rx gains
        #      2. tune center freq
        #      3. receive data and save data

        sfcw_rx_signal = []
        for f in center_freqs:
            # 1. set rx gains
            self.usrp.set_rx_gain(self.gain_table[f][0], 0)  # set rxA gain
            self.usrp.set_rx_gain(self.gain_table[f][1], 1)   # set rxB gain
            # 2. tune center freq
            self.tune_center_freq(f)
            # 3. receive data
            self.recv_and_save_data(self.rx_buffer, self.num_rx_samps)
            self.rx_buffer = np.conjugate(self.rx_buffer) # take conjugate to satisfy the complex signal model for I/Q modulator and demodulator
            # 4. store rx data into sfcw_rx_signal
            sfcw_rx_signal.append(self.rx_buffer)

        self.stop_transmit()  # stop the transmitter

        return sfcw_rx_signal, center_freqs

