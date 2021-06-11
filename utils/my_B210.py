import uhd
from uhd import libpyuhd as lib
from threading import Thread

class my_B210():

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
        """
        self.transmit_flag = True  # used to kill the tx_thread when done

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
        tx_thread = Thread(target=self.send_data_cont, args=(tx_data, tx_md))

        tx_thread.start()
        print("tx thread begins")

    def stop_transmit(self):
        self.transmit_flag = False

    def recv_and_save_data(self, rx_buffer, num_rx_samps, rx_md = lib.types.rx_metadata()):
        """

        :param rx_buffer: should be an numpy array with dimension 2 by num_rx_samps, where
                        1) the elements are of type complex64 and 2) the first row of I/Q data is
                        obtained from the rx buffer in channelA and the second row of I/Q data is
                        obtained from the tx buffer in channelB
                        the received data is stored in the rx_buffer.

        :param num_rx_samps: how many I/Q samples to receive
        :param rx_md: rx metadata
        """
        stream_cmd = lib.types.stream_cmd(lib.types.stream_mode.num_done)
        stream_cmd.num_samps = num_rx_samps
        stream_cmd.stream_now = False
        stream_cmd.time_spec = self.usrp.get_time_now() + lib.types.time_spec(0.01)
        self.rx_streamer.issue_stream_cmd(stream_cmd)  # tells all channels to stream

        self.rx_streamer.recv(rx_buffer, rx_md)