"""
Generating signals for transmitting
"""
import numpy as np

def complex_sinusoid(samp_rate, wave_ampl = 0.8, wave_freq = 1000):
    """
    :param samp_rate: the sample rate of the DAC in the B210
    :param wave_ampl: amplitude of the complex sinusoid
    :param wave_freq: the frequency of the complex sinusoid
    :return: the baseband signal that is going to be sent to B210 tx buffers.
             the baseband signal is sotred in a numpy array with dimension 2 by N, where the elements are
             complex64 and the first row of I/Q data is going to be sent to txA buffer and the second row of
             I/Q data is going to be sent to txB buffer
    """
    channel_list = (0, 1)
    # generate the tx baseband waveform
    waveforms = {
        "complex_exp": lambda n, tone_freq, samp_rate: np.exp(
            n * 2j * np.pi * tone_freq / samp_rate
        )
        # a function that take the n-th sample as input and output the function value exp(2*pi*tone_freq*n*1/samp_freq)
    }
    # prepare tx data, tx metadata

    wave_one_period = np.array(
        list(
            map(
                lambda n: wave_ampl * waveforms["complex_exp"](n, wave_freq, samp_rate),
                np.arange(int(np.floor(samp_rate / wave_freq)), dtype=np.complex64),
            )
        ),
        dtype=np.complex64,
    )  # create one period of the wave_form

    tx_data = np.tile(
        wave_one_period, (1, 10000)
    )  # send 10,000 period of the wave; the send data should be a row vector?
    tx_data = np.tile(
        tx_data[0], (len(channel_list), 1)
    )  # since we have two channels to transmit, we tile tx_data

    # prepare the complex conjugate tx_data
    tx_data = np.conjugate(tx_data)

    length_wave_one_period = wave_one_period.size

    return tx_data, length_wave_one_period
