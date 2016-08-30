import numpy
import sumpf
import nlsp


class SaveandRetrieveModel(object):
    """
    Save and retrieve the model.
    """

    def __init__(self, filename=None):
        """
        @param filename: the filename where the model has to be save or the filename of the model which has to be retrieved
        """
        self._filename = filename
        self._file_format = sumpf.modules.SignalFile.NUMPY_NPZ

    @sumpf.Input(str)
    def SetFilename(self, filename=None):
        """
        Set the filename where the model has to be saved or to be retrieved.
        @param filename: the filename
        """
        self._filename = filename


class SaveHGMModel(SaveandRetrieveModel):
    """
    Save the model in the a file location.
    """

    def __init__(self, filename=None, model=None):
        """
        @param filename: the file location
        @param model: the model
        """
        SaveandRetrieveModel.__init__(self, filename=filename)
        self.__model = model
        self.__SaveModel()

    def SetModel(self, model=None):
        """
        Set model model which has to be saved in the file location.
        @param model: the model
        @return:
        """
        self.__model = model
        self.__SaveModel()

    def __SaveModel(self):
        """
        Save the model in specific file location.
        """
        get_param = nlsp.ModifyModel(input_model=self.__model)
        nonlinear_functions = get_param._nonlinear_functions
        filter_kernels = get_param._filter_impulseresponses
        aliasing = get_param._aliasing_compensation
        downsampling_position = get_param._downsampling_position
        filter_kernels = sumpf.modules.MergeSignals(signals=filter_kernels).GetOutput()
        nonlinear_function_class = nonlinear_functions[0].__class__
        degree = []
        for nl in nonlinear_functions:
            degree.append(nl.GetMaximumHarmonics())
        degree = numpy.asarray(degree)
        aliasing = aliasing.__class__
        label = generate_label(nonlinearfunction_class=nonlinear_function_class, nonlinearfunction_degree=degree,
                               aliasingcomp_type=aliasing, aliasingcomp_loc=downsampling_position)
        model = sumpf.modules.RelabelSignal(signal=filter_kernels,
                                            labels=(label,) * len(filter_kernels.GetChannels())).GetOutput()
        sumpf.modules.SignalFile(filename=self._filename, signal=model, file_format=self._file_format).GetSignal()


class RetrieveHGMModel(SaveandRetrieveModel):
    """
    Retrieve the model from a specific file location.
    """

    def __init__(self, filename=None, file_format=None):
        """
        @param filename: the filename
        @param file_format: the file format
        """
        SaveandRetrieveModel.__init__(self, filename=filename)

    def GetModel(self):
        """
        Get the model which is saved in the file location.
        """
        model = sumpf.modules.SignalFile(filename=self._filename, file_format=self._file_format).GetSignal()
        label = model.GetLabels()[0]
        nonlinearfunction_class, nonlinearfunction_degree, aliasingcomp_type, aliasingcomp_loc = decode_label(
            label=label)
        nonlinear_functions = [nonlinearfunction_class(degree=i) for i in nonlinearfunction_degree]
        filter_kernels = []
        for i in range(len(model.GetChannels())):
            kernel = sumpf.modules.SplitSignal(data=model, channels=[i]).GetOutput()
            filter_kernels.append(kernel)
        model = nlsp.HammersteinGroupModel(nonlinear_functions=nonlinear_functions,
                                           filter_impulseresponses=filter_kernels,
                                           aliasing_compensation=aliasingcomp_type(),
                                           downsampling_position=aliasingcomp_loc)
        return model



def generate_label(nonlinearfunction_class, nonlinearfunction_degree, aliasingcomp_type, aliasingcomp_loc):
    """
    A helper function to generate a label based on model parameters.
    @param nonlinearfunction_class: the class of the nonlinear block
    @param nonlinearfunction_degree: the degree of the nonlinear function
    @param aliasingcomp_type: the type of aliasing compensation
    @param aliasingcomp_loc: the location in which the aliasing compensation is done
    @return: the label
    """
    nonlinear_class = str(nonlinearfunction_class)
    char1 = "/'"
    char2 = "/'"
    print nonlinear_class
    nonlinear_class = nonlinear_class[nonlinear_class.find(char1) + 1: nonlinear_class.find(char2)]
    print nonlinear_class
    label = nonlinear_class + "*" + str(nonlinearfunction_degree) + "*" + str(aliasingcomp_type) + "*" + str(
        aliasingcomp_loc)
    return label


def decode_label(label):
    """
    Decodes the label to different parameters of the model.
    @param label: the label
    @return: nonlinearfunction_class, nonlinearfunction_degree, aliasingcomp_type, aliasingcomp_loc
    """
    a = label.split('*')
    nonlinearfunction_class = a[0]
    nonlinearfunction_degree = a[1]
    aliasingcomp_type = a[2]
    aliasingcomp_loc = a[3]

    model = sumpf.modules.SignalFile(filename="C:/Users/diplomand.8/Desktop/save/some").GetSignal()
    nonlinearfunction_degree = eval(nonlinearfunction_degree)
    nonlinear_functions = [nonlinearfunction_class(degree=i) for i in nonlinearfunction_degree]
    filter_kernels = []
    for i in range(len(model.GetChannels())):
        kernel = sumpf.modules.SplitSignal(data=model, channels=[i]).GetOutput()
        filter_kernels.append(kernel)
    model = nlsp.HammersteinGroupModel(nonlinear_functions=nonlinear_functions,
                                       filter_impulseresponses=filter_kernels,
                                       aliasing_compensation=aliasingcomp_type(),
                                       downsampling_position=aliasingcomp_loc)
