"""
28 Aug 2013


"""
from pytadbit.imp.imp_modelling import generate_3d_models
from pytadbit.utils.extraviews import plot_2d_optimization_result
from pytadbit.utils.extraviews import plot_3d_optimization_result
import numpy as np

class IMPoptimizer(object):
    """
    IMPoptimizer, optimizes a set of paramaters (scale, maxdist, lowfreq and
    upfreq) in order to maximize the correlation between models generated by IMP
    and real data.

    :param experiment: a class:`pytadbit.experiment.Experiment` instance
    :param start: start of the region to model (bin number)
    :param end: end of the region to model (bin number, both inclusive)
    :param 5000 n_models: number of modes to generate.
    :param 1000 n_keep: number of models to keep (models with lowest
       objective function final value). Usually 20% of the models generated
       are kept.
    :param 1 close_bins: number of particle away a particle may be to be
       considered as a neighbor.
    
    """
    def __init__(self, experiment, start, end, 
                 n_models=500, cutoff=300, n_keep=100, close_bins=1):

        self.resolution = experiment.resolution
        print experiment
        print start, end
        self.zscores, self.values = experiment._sub_experiment_zscore(start,
                                                                      end)
        self.n_models   = n_models
        self.n_keep     = n_keep
        self.close_bins = close_bins
        self.cutoff     = cutoff

        self.scale_range = []
        self.maxdist_range = []
        self.lowfreq_range = []
        self.upfreq_range = []
        self.results = {}

        
    def run_grid_search(self, upfreq_range=(0, 1, 0.1), lowfreq_range=(-1, 0, 0.1),
                    scale_range=(0.005, 0.005, 0.001),
                    maxdist_range=(400, 1500, 100), n_cpus=1, verbose=True):
        """
        Calculates the correlation between models generated by IMP and real
        data, for the 4 main IMP parameters in given ranges of values.
        
        :param n_cpus: number of CPUs to use for the optimization of models
        :param (-1,0,0.1) lowfreq_range: a tuple with the boundaries between
           which to search for the minimum threshold used to decide which
           experimental values have to be included in the computation of
           restraints. Last value of the input tuple is the step for
           lowfreq increments
        :param (0,1,0.1,0.1) upfreq_range: a tuple with the boundaries between
           which to search for the maximum threshold used to decide which
           experimental values have to be included in the computation of
           restraints. Last value of the input tuple is the step for
           upfreq increments
        :param (400,1400,100) maxdist_range: tuple with upper and lower bounds
           used to search for the optimal maximum experimental distance. Last
           value of the input tuple is the step for maxdist increments
        :param (0.005,0.005,0.001) scale_range: tuple with upper and lower
           bounds used to search for the optimal scale parameter (how many
           nanometers occupies one nucleotide). Last value of the input tuple is
           the step for scale parameter increments
        :param True verbose: print results as they are computed
        """
        if type(maxdist_range) == tuple:
            maxdist_step = maxdist_range[2]
            maxdist_arange = range(maxdist_range[0],
                                        maxdist_range[1] + maxdist_step,
                                        maxdist_step)
        else:
            maxdist_arange = maxdist_range
        if type(lowfreq_range) == tuple:
            lowfreq_step = lowfreq_range[2]
            lowfreq_arange = np.arange(lowfreq_range[0],
                                            lowfreq_range[1] + lowfreq_step / 2,
                                            lowfreq_step)
        else:
            lowfreq_arange = lowfreq_range
        if type(upfreq_range) == tuple:
            upfreq_step = upfreq_range[2]
            upfreq_arange = np.arange(upfreq_range[0],
                                           upfreq_range[1] + upfreq_step / 2,
                                           upfreq_step)
        else:
            upfreq_arange = upfreq_range
        if type(scale_range) == tuple:
            scale_step = scale_range[2]
            scale_arange = np.arange(scale_range[0],
                                          scale_range[1] + scale_step / 2,
                                          scale_step)
        else:
            scale_arange = scale_range
            
        count = 0
        for scale in scale_arange:
            if not scale in self.scale_range:
                self.scale_range.append(scale)
            for maxdist in maxdist_arange:
                if not maxdist in self.maxdist_range:
                    self.maxdist_range.append(maxdist)
                for upfreq in upfreq_arange:
                    if not upfreq in self.upfreq_range:
                        self.upfreq_range.append(upfreq)
                    for lowfreq in lowfreq_arange:
                        if not lowfreq in self.lowfreq_range:
                            self.lowfreq_range.append(lowfreq)
                        if (scale, maxdist, upfreq, lowfreq) in self.results:
                            continue
                        tmp = {'kforce'   : 5,
                               'lowrdist' : 100,
                               'maxdist'  : maxdist,
                               'upfreq'   : upfreq,
                               'lowfreq'  : lowfreq,
                               'scale'    : scale}
                        tdm = generate_3d_models(self.zscores, self.resolution,
                                                 self.n_models,
                                                 self.n_keep, config=tmp,
                                                 n_cpus=n_cpus,
                                                 values=self.values,
                                                 close_bins=self.close_bins)
                        count += 1
                        if verbose:
                            print '%5s  ' % (count),
                            print upfreq, lowfreq, maxdist, scale,
                        try:
                            result = tdm.correlate_with_real_data(
                                cutoff=self.cutoff)[0]
                            if verbose:
                                print result
                            self.results[(my_round(scale),
                                          my_round(maxdist),
                                          my_round(upfreq),
                                          my_round(lowfreq))] = result
                        except Exception, e:
                            print 'ERROR %s' % e
                            
        self.scale_range.sort()
        self.maxdist_range.sort()
        self.lowfreq_range.sort()
        self.upfreq_range.sort()


    def plot_2d(self, axes=('scale', 'maxdist', 'upfreq', 'lowfreq'),
                show_best=0, skip=None):
        """
        A grid of heatmaps representing the result of the optimization.

        :param 'scale','maxdist','upfreq','lowfreq' axes: tuple of axes to
           represent. The order will define which parameter will be placed on the
           w, z, y or x axe.
        :param 0 show_best: number of best correlation value to identifie.
        :param None skip: a dict can be passed here in order to fix a given axe,
           e.g.: {'scale': 0.001, 'maxdist': 500}

        """
        results = self._result_to_array()
        plot_2d_optimization_result((('scale', 'maxdist', 'upfreq', 'lowfreq'),
                                     (self.scale_range, self.maxdist_range,
                                      self.upfreq_range, self.lowfreq_range),
                                     results), axes=axes,
                                    show_best=show_best, skip=skip)

    def plot_3d(self, axes=('scale', 'maxdist', 'upfreq', 'lowfreq')):
        """
        A grid of heatmaps representing the result of the optimization.

        :param 'scale','maxdist','upfreq','lowfreq' axes: tuple of axes to
           represent. The order will define which parameter will be placed on the
           w, z, y or x axe.

        """
        results = self._result_to_array()
        plot_3d_optimization_result((('scale', 'maxdist', 'upfreq', 'lowfreq'),
                                     (self.scale_range, self.maxdist_range,
                                      self.upfreq_range, self.lowfreq_range),
                                     results), axes=axes)


    def _result_to_array(self):
        results = np.empty((len(self.scale_range), len(self.maxdist_range),
                            len(self.upfreq_range), len(self.lowfreq_range)))
        for w, scale in enumerate(self.scale_range):
            for x, maxdist in enumerate(self.maxdist_range):
                for y, upfreq in enumerate(self.upfreq_range):
                    for z, lowfreq in enumerate(self.lowfreq_range):
                        try:
                            results[w, x, y, z] = self.results[
                                (my_round(scale), my_round(maxdist),
                                 my_round(upfreq), my_round(lowfreq))]
                        except KeyError:
                            results[w, x, y, z] = float('nan')
        return results


    def write_result(self, f_name):
        """
        Writes a log file of all the values tested for each parameter, and the
        resulting correlation value.

        This file can be used to load or merge data a posteriori using 
        func:`pytadbit.imp.impoptimizer.IMPoptimizer.load_from_file`
        
        :param f_name: path to file
        """
        out = open(f_name, 'w')
        out.write(('## n_models: %s cutoff: %s n_keep: %s ' +
                   'close_bins: %s\n') % (self.n_models, self.cutoff,
                                          self.n_keep, self.close_bins))
        out.write('# scale\tmax_dist\tup_freq\tlow_freq\tcorrelation\n')
        for scale in self.scale_range:
            for maxdist in self.maxdist_range:
                for upfreq in self.upfreq_range:
                    for lowfreq in self.lowfreq_range:
                        try:
                            result = self.results[(my_round(scale),
                                                   my_round(maxdist),
                                                   my_round(upfreq),
                                                   my_round(lowfreq))]
                            out.write('%s\t%s\t%s\t%s\t%s\n' % (
                                scale, maxdist, upfreq, lowfreq, result))
                        except KeyError:
                            continue
        out.close()
        

    def load_from_file(self, f_name):
        """
        Loads optimizations from file generated with function: 
        func:`pytadbit.imp.impoptimizer.IMPoptimizer.write_result`.
        If some results where already loaded or calculated, they will not be
        overwritten.

        :param f_name: path to file
        """
        for line in open(f_name):
            # Check same parameters
            if line.startswith('##'):
                n_models, _, cutoff, _, n_keep, _, close_bins = line.split()[2:]
                if ([int(n_models), int(cutoff), int(n_keep), int(close_bins)]
                    != 
                    [self.n_models, self.cutoff, self.n_keep, self.close_bins]):
                    raise Exception('Parameters does not match: %s\n%s' % (
                        [int(n_models), int(cutoff),
                         int(n_keep), int(close_bins)],
                        [self.n_models, self.cutoff,
                         self.n_keep, self.close_bins]))
            if line.startswith('#'):
                continue
            scale, maxdist, upfreq, lowfreq, result = line.split()
            scale, maxdist, upfreq, lowfreq = (
                float(scale), int(maxdist), float(upfreq), float(lowfreq))
            self.results[(my_round(scale), my_round(maxdist),
                          my_round(upfreq), my_round(lowfreq))] = float(result)
            if not scale in self.scale_range:
                self.scale_range.append(scale)
            if not maxdist in self.maxdist_range:
                self.maxdist_range.append(maxdist)
            if not upfreq in self.upfreq_range:
                self.upfreq_range.append(upfreq)
            if not lowfreq in self.lowfreq_range:
                self.lowfreq_range.append(lowfreq)
        self.scale_range.sort()
        self.maxdist_range.sort()
        self.lowfreq_range.sort()
        self.upfreq_range.sort()


def my_round(num, val=4):
    num = round(num, val)
    return str(int(num) if num == int(num) else num)
