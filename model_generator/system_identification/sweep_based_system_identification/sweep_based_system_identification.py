from nlsp.model_generator.system_identification.system_identification_approaches import SystemIdentification
import numpy
import nlsp
import sumpf


class SineSweep(SystemIdentification):
    """
    A class which identifies a model of the system using a sine sweep signal.
    """

    def __init__(self, system_response=None, select_branches=None, aliasing_compensation=None,
                 excitation_length=None, excitation_sampling_rate=None, filter_length=None, excitation_start_freq=20.0,
                 excitation_stop_freq=20000.0):
        """
        :param system_response: the response of the nonlinear system
        :param select_branches: the branches of the model to which the filter kernels have to be found Eg. [1,2,3,4,5]
        :param aliasing_compensation: the aliasing compensation parameter of the resulting model
        :param excitation_length: the length of the excitation and response signals
        :param excitation_sampling_rate: the sampling rate of the excitation and response signals
        :param filter_length: the identified filter length
        :param excitation_start_freq: the start frequency of the excitation signal
        :param excitation_stop_freq: the stop frequency of the excitation signal
        """
        SystemIdentification.__init__(self, system_response=system_response, select_branches=select_branches,
                                      aliasing_compensation=aliasing_compensation, excitation_length=excitation_length,
                                      excitation_sampling_rate=excitation_sampling_rate, filter_length=filter_length)
        self.__start_freq = excitation_start_freq
        self.__stop_freq = excitation_stop_freq

    @sumpf.Output(sumpf.Signal)
    def GetExcitation(self, excitation_length=None, excitation_sampling_rate=None, excitation_start_freq=None,
                      excitation_stop_freq=None):
        """
        Get the excitation signal for system identification.

        :param excitation_length: the length of the excitation signal
        :param excitation_sampling_rate: the sampling rate of the excitation signal
        :param excitation_start_freq: the start frequency of the excitation signal
        :param excitation_stop_freq: the stop frequency of the excitation signal
        :return: the excitation signal
        """
        if excitation_length is not None:
            self._length = excitation_length
        if excitation_sampling_rate is not None:
            self._sampling_rate = excitation_sampling_rate
        if excitation_start_freq is not None:
            self.__start_freq = excitation_start_freq
        if excitation_stop_freq is not None:
            self.__stop_freq = excitation_stop_freq
        self.__excitation_generator = nlsp.excitation_generators.Sinesweepgenerator_Novak(
            sampling_rate=self._sampling_rate,
            approximate_numberofsamples=self._length,
            start_frequency=self.__start_freq,
            stop_frequency=self.__stop_freq)
        return self.__excitation_generator.GetOutput()

    def _GetFilterImpuleResponses(self):
        """
        Get the identified filter impulse responses.

        :return: the filter impulse responses
        """
        branches = max(self._select_branches)
        sweep_length = self.__excitation_generator.GetLength()
        rev = self.__excitation_generator.GetReversedOutput()
        rev_spec = sumpf.modules.FourierTransform(rev).GetSpectrum()
        out_spec = sumpf.modules.FourierTransform(self._system_response).GetSpectrum()
        out_spec = out_spec / self._system_response.GetSamplingRate()
        tf = rev_spec * out_spec
        ir_sweep = sumpf.modules.InverseFourierTransform(tf).GetSignal()
        ir_sweep_direct = sumpf.modules.CutSignal(signal=ir_sweep, start=0, stop=int(sweep_length / 4)).GetOutput()
        ir_merger = sumpf.modules.MergeSignals(on_length_conflict=sumpf.modules.MergeSignals.FILL_WITH_ZEROS)
        ir_merger.AddInput(ir_sweep_direct)
        for i in range(branches - 1):
            split_harm = nlsp.common.FindHarmonicImpulseResponse_NovakSweep(impulse_response=ir_sweep,
                                                                            harmonic_order=i + 2,
                                                                            sweep_generator=self.__excitation_generator).GetHarmonicImpulseResponse()
            split_harm = sumpf.modules.CutSignal(signal=split_harm,
                                                 stop=len(self.__excitation_generator.GetOutput())).GetOutput()
            ir_merger.AddInput(sumpf.Signal(channels=split_harm.GetChannels(),
                                            samplingrate=ir_sweep.GetSamplingRate(),
                                            labels=split_harm.GetLabels()))
        ir_merger = ir_merger.GetOutput()
        tf_harmonics_all = sumpf.modules.FourierTransform(ir_merger).GetSpectrum()
        n = len(tf_harmonics_all.GetChannels()) // branches
        items = range(len(tf_harmonics_all.GetChannels()))
        clubbed = [a for a in zip(*[iter(items)] * n)]
        harmonics_tf = []
        for clubb in clubbed:
            tf_harmonics = sumpf.modules.SplitSpectrum(data=tf_harmonics_all, channels=clubb).GetOutput()
            harmonics_tf.append(tf_harmonics)
        A_matrix = numpy.zeros((branches, branches), dtype=numpy.complex128)
        for n in range(0, branches):
            for m in range(0, branches):
                if ((n >= m) and ((n + m) % 2 == 0)):
                    A_matrix[m][n] = (((-1 + 0j) ** (2 * (n + 1) - m / 2)) / (2 ** n)) * nlsp.math.binomial_expression(
                        (n + 1), (n - m) / 2)
                else:
                    A_matrix[m][n] = 0
        A_inverse = numpy.linalg.inv(A_matrix)
        for row in range(0, len(A_inverse)):
            if row % 2 != 0.0:
                A_inverse[row] = A_inverse[row] * (0 + 1j)
        B = []
        for row in range(0, branches):
            A = sumpf.modules.ConstantSpectrumGenerator(value=0.0, resolution=harmonics_tf[0].GetResolution(),
                                                        length=len(harmonics_tf[0])).GetSpectrum()
            for column in range(0, branches):
                temp = sumpf.modules.Multiply(value1=harmonics_tf[column], value2=A_inverse[row][column]).GetResult()
                A = A + temp
            B_temp = sumpf.modules.InverseFourierTransform(A).GetSignal()
            B.append(B_temp)
        filter_kernels = []
        for branch in self._select_branches:
            if self._filter_length is not None:
                filter_kernels.append(nlsp.common.helper_functions_private.change_length_signal(signal=B[branch - 1],
                                                                                                length=self._filter_length))
            else:
                filter_kernels.append(B[branch - 1])
        filters = []
        for filt in filter_kernels:
            filters.append(sumpf.Signal(channels=filt.GetChannels(), samplingrate=ir_sweep.GetSamplingRate(),
                                        labels=filt.GetLabels()))
        return filters

    def _GetNonlinerFunctions(self):
        """
        Get the nonlinear functions.

        :return: the nonlinear functions
        """
        nonlinear_functions = []
        for branch in self._select_branches:
            nonlinear_func = nlsp.nonlinear_function.Power(degree=branch)
            nonlinear_functions.append(nonlinear_func)
        return nonlinear_functions


class CosineSweep(SystemIdentification):
    """
    A class which identifies a model of the system using a cosine sweep signal.
    """

    def GetExcitation(self, excitation_length=None, excitation_sampling_rate=None):
        """
        Get the excitation signal for system identification.

        :param excitation_length: the length of the excitation signal
        :param excitation_sampling_rate: the sampling rate of the excitation signal
        :return: the excitation signal
        """
        if excitation_length is not None:
            self._length = excitation_length
        if excitation_sampling_rate is not None:
            self._sampling_rate = excitation_sampling_rate
        self.__excitation_generator = nlsp.excitation_generators.Cosinesweepgenerator_Novak(
            sampling_rate=self._sampling_rate,
            approximate_numberofsamples=self._length)
        return self.__excitation_generator.GetOutput()

    def _GetFilterImpuleResponses(self):
        """
        Get the identified filter impulse responses.

        :return: the filter impulse responses
        """
        branches = max(self._select_branches)
        sweep_length = self.__excitation_generator.GetLength()
        rev = self.__excitation_generator.GetReversedOutput()
        rev_spec = sumpf.modules.FourierTransform(rev).GetSpectrum()
        out_spec = sumpf.modules.FourierTransform(self._system_response).GetSpectrum()
        out_spec = out_spec / self._system_response.GetSamplingRate()
        tf = rev_spec * out_spec
        ir_sweep = sumpf.modules.InverseFourierTransform(tf).GetSignal()
        ir_sweep_direct = sumpf.modules.CutSignal(signal=ir_sweep, start=0, stop=int(sweep_length / 4)).GetOutput()
        ir_merger = sumpf.modules.MergeSignals(on_length_conflict=sumpf.modules.MergeSignals.FILL_WITH_ZEROS)
        ir_merger.AddInput(ir_sweep_direct)
        for i in range(branches - 1):
            split_harm = nlsp.common.FindHarmonicImpulseResponse_NovakSweep(impulse_response=ir_sweep,
                                                                            harmonic_order=i + 2,
                                                                            sweep_generator=self.__excitation_generator).GetHarmonicImpulseResponse()
            split_harm = sumpf.modules.CutSignal(signal=split_harm,
                                                 stop=len(self.__excitation_generator.GetOutput())).GetOutput()
            ir_merger.AddInput(sumpf.Signal(channels=split_harm.GetChannels(),
                                            samplingrate=ir_sweep.GetSamplingRate(),
                                            labels=split_harm.GetLabels()))
        ir_merger = ir_merger.GetOutput()
        n = len(ir_merger.GetChannels()) // branches
        items = range(len(ir_merger.GetChannels()))
        clubbed = [a for a in zip(*[iter(items)] * n)]
        ir_harmonics = []
        for clubb in clubbed:
            ir_harmonics.append(sumpf.modules.SplitSignal(data=ir_merger, channels=clubb).GetOutput())
        filter_kernels = []
        for branch in self._select_branches:
            if self._filter_length is not None:
                filter_kernels.append(
                    nlsp.common.helper_functions_private.change_length_signal(signal=ir_harmonics[branch - 1],
                                                                              length=self._filter_length))
            else:
                filter_kernels.append(ir_harmonics[branch - 1])
        filters = []
        for filt in filter_kernels:
            filters.append(sumpf.Signal(channels=filt.GetChannels(), samplingrate=ir_sweep.GetSamplingRate(),
                                        labels=filt.GetLabels()))
        return filter_kernels

    def _GetNonlinerFunctions(self):
        """
        Get the nonlinear functions.

        :return: the nonlinear functions
        """
        nonlinear_functions = []
        for branch in self._select_branches:
            nonlinear_func = nlsp.nonlinear_function.Chebyshev(degree=branch)
            nonlinear_functions.append(nonlinear_func)
        return nonlinear_functions
