import os
from os.path import join

import numpy as np
import sklearn.metrics

from core.skeleton import AbstractEvaluator


class BasicEvaluator(AbstractEvaluator):
    def __init__(self):
        self.metric_module_list = []
        self.hist = {}

        # add default metrics
        self.add_metric_module(['epoch'], lambda ad, epoch, logs: [epoch])

    def add_metric_module(self, names, metrics):
        '''
        :param namse: the names of the metrics
        :param metrics: function with signature metrics(anomaly_detector, epoch, logs)
        '''

        self.metric_module_list.append((names, metrics))
        for name in names:
            self.hist[name] = np.array([], dtype=float)

    def add_auroc_module(self, x, y, score_type='fm', target_fpr=1e-4):
        def auroc_metric(ad, epoch, logs):
            anomaly_prob = ad.get_anomaly_scores(x, type=score_type)
            auroc = sklearn.metrics.roc_auc_score(y, anomaly_prob)
            fpr, tpr, _ = sklearn.metrics.roc_curve(y, anomaly_prob, pos_label=1)
            idx = np.argmax(fpr > target_fpr)
            lr_pos_ = tpr[idx] / fpr[idx]
            return [auroc, lr_pos_]

        self.add_metric_module(['auroc_' + score_type, 'lr_pos_' + score_type], auroc_metric)

    def compute_rates(self, threshold, scores):
        return 0, 0

    def compute_threshold(self):
        pass

    def add_anomaly_score_module(self, x_sm, x_bsm, score_type='fm'):
        def recon_metrics(ad, epoch, logs):
            scores_sm = ad.get_anomaly_scores(x_sm, type=score_type)
            scores_bsm = ad.get_anomaly_scores(x_bsm, type=score_type)

            sm_mean = np.mean(scores_sm)
            sm_std = np.std(scores_sm)
            bsm_mean = np.mean(scores_bsm)
            bsm_std = np.std(scores_bsm)

            return sm_mean, sm_std, bsm_mean, bsm_std

        names = ['sm_mean', 'sm_std', 'bsm_mean', 'bsm_std']
        names = [name + '_' + score_type for name in names]
        self.add_metric_module(names, recon_metrics)

    def get_metrics(self, eval_result):
        pass

    # used for online evaluation
    def evaluate(self, anomaly_detector, epoch, logs):
        for names, metrics in self.metric_module_list:
            metrics_res = metrics(anomaly_detector, epoch, logs)
            for i, name in enumerate(names):
                self.hist[name] = np.append(self.hist[name], metrics_res[i])

    def save_results(self, path):
        np.save(join(path, 'metrics.npy'), self.hist, allow_pickle=True)
