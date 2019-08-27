# %% imports
import os
import importlib.util
import math

import tensorflow as tf
from sklearn.metrics import roc_curve, roc_auc_score
import numpy as np
from scipy.stats import binned_statistic
import matplotlib.pyplot as plt
import pickle

from alad_mod.alad import ALAD
from data.hlf_dataset_utils import load_data, feature_names, load_data2
from data.hlf_preprocessing import HLFDataPreprocessor, load

# %% load data
data_path = '/home/oliverkn/pro/data/hlf_set'
max_samples = 5_000_000

dataset_list = ['Wlnu', 'qcd', 'Zll', 'ttbar']
bsm_list = ['Ato4l', 'leptoquark', 'hToTauTau', 'hChToTauNu']
sm_fraction = [0.592, 0.338, 0.067, 0.003]

roc_data = {}
for bsm in bsm_list:
    x, y = load_data2(data_path, set='valid', type='custom', sm_list=['sm_mix'], bsm_list=[bsm])
    roc_data[bsm] = (x, y)

vae_roc = {}
vae_roc['Ato4l'] = pickle.load(open('alad_mod/vae_roc/VAE_all-in-one_v71_ROC1_dict_Ato4l.pkl', 'rb'), encoding='latin1')
vae_roc['leptoquark'] = pickle.load(open('alad_mod/vae_roc/VAE_all-in-one_v71_ROC1_dict_leptoquark.pkl', 'rb'),
                                    encoding='latin1')
vae_roc['hToTauTau'] = pickle.load(open('alad_mod/vae_roc/VAE_all-in-one_v71_ROC1_dict_hToTauTau.pkl', 'rb'),
                                   encoding='latin1')
vae_roc['hChToTauNu'] = pickle.load(open('alad_mod/vae_roc/VAE_all-in-one_v71_ROC1_dict_hChToTauNu.pkl', 'rb'),
                                    encoding='latin1')

# %% load alad
result_path = '/home/oliverkn/euler/results/hlf_set/alad/kdd_l12/'
result_path = '/home/oliverkn/pro/results/4_4/alad/test_eval_6/'
config_file = result_path + 'config.py'
weights_file = result_path + 'model-900000'

# loading config
spec = importlib.util.spec_from_file_location('config', config_file)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

# loading preprocessor
preprocessor = load(os.path.join(result_path, 'preprocessor.pkl'))

# loading alad
tf.reset_default_graph()
ad = ALAD(config, tf.Session())
ad.load(weights_file)

# %% plot ROC
target_fpr = 1e-5

fig, ax_arr = plt.subplots(2, 2, figsize=(12, 12))
for i, bsm in enumerate(bsm_list):
    x, y = roc_data[bsm]

    x = preprocessor.transform(x)
    print('data shape:' + str(x.shape))

    ax = ax_arr[i // 2, i % 2]

    scores = ad.compute_all_scores(x)
    score_names = ['fm', 'l1', 'l2', 'weighted_lp']
    for score, name in zip(scores, score_names):
        fpr, tpr, _ = roc_curve(y, score, pos_label=1)
        # auroc = roc_auc_score(y, score)
        idx = np.argmax(fpr > target_fpr)
        lr_plus = tpr[idx] / fpr[idx]
        ax.loglog(fpr, tpr, label=name + ' (LR+=%.2f)' % lr_plus)

    # plot vae reference
    fpr, tpr = vae_roc[bsm]['eff_SM'], vae_roc[bsm]['eff_BSM']
    idx = np.argmax(fpr > target_fpr)
    lr_plus = tpr[idx] / fpr[idx]
    ax.loglog(fpr, tpr, label='vae (LR+=%.2f)' % lr_plus)

    ax.axvline(target_fpr, ls='--', color='magenta')
    ax.set_title('SM-mix + ' + bsm)
    ax.set_xlabel('FPR')
    ax.set_ylabel('TPR')
    ax.grid()
    ax.set(xlim=(1e-6, 1), ylim=(1e-6, 1))
    ax.legend()

plt.show()

# %% plot anomaly scores histogram

dataset_list = ['Wlnu', 'Zll', 'ttbar', 'qcd', 'Ato4l', 'leptoquark', 'hToTauTau', 'hChToTauNu']
score_type = 'fm'
max_samples = 1_000_000
n_bins = 100
quantile = 1e-5

fig, ax_arr = plt.subplots(1, 2, figsize=(12, 12))

scores = {}

histo_range = (np.inf, -np.inf)

for dataset in dataset_list:
    x, _ = load_data(data_path, set='valid', type='custom', shuffle=True, sm_list=[dataset], bsm_list=[],
                     balance_sm=False)
    x = x[:max_samples]
    x = preprocessor.transform(x)
    score = ad.get_anomaly_scores(x, type=score_type)
    histo_range = (np.minimum(np.quantile(score, quantile), histo_range[0]),
                   np.maximum(np.quantile(score, 1. - quantile), histo_range[1]))

    scores[dataset] = score

for dataset in dataset_list:
    score = scores[dataset]

    pdf, bin_edges = np.histogram(score, bins=n_bins, range=histo_range)

    pdf = pdf / score.shape[0]
    ccdf = 1 - np.cumsum(pdf)
    ax_arr[0].semilogy(bin_edges[:-1], pdf, label=dataset)
    ax_arr[1].semilogy(bin_edges[:-1], ccdf, label=dataset)

ax_arr[0].set_xlabel(score_type + '-score')
ax_arr[0].set_ylabel('PDF')
ax_arr[0].legend()
ax_arr[1].set_xlabel(score_type + '-score')
ax_arr[1].set_ylabel('CCDF')
ax_arr[1].legend()

plt.show()

# %% plot recon loss per parameter
dataset_list = ['sm_mix', 'Ato4l', 'leptoquark', 'hToTauTau', 'hChToTauNu']
score_type = 'fm'
max_samples = 1_000_00
n_bins = 100
quantile = 1e-5

fig, ax_arr = plt.subplots(1, 2, figsize=(12, 12))

scores = {}

histo_range = (np.inf, -np.inf)

for dataset in dataset_list:
    x, _ = load_data(data_path, set='valid', type='custom', shuffle=True, sm_list=[dataset], bsm_list=[],
                     balance_sm=False)
    x = x[:max_samples]
    x = preprocessor.transform(x)
    score = ad.get_anomaly_scores(x, type=score_type)
    histo_range = (np.minimum(np.quantile(score, quantile), histo_range[0]),
                   np.maximum(np.quantile(score, 1. - quantile), histo_range[1]))

    scores[dataset] = score

for dataset in dataset_list:
    score = scores[dataset]

    pdf, bin_edges = np.histogram(score, bins=n_bins, range=histo_range)

    pdf = pdf / score.shape[0]
    ccdf = 1 - np.cumsum(pdf)
    # ccdf = np.cumsum(pdf) # just for debugging (see if it sums to 1)

    if dataset == 'sm_mix':
        ax_arr[0].fill_between(bin_edges[:-1], 0, pdf, label=dataset)
        ax_arr[1].fill_between(bin_edges[:-1], 0, ccdf, label=dataset)
    else:
        ax_arr[0].plot(bin_edges[:-1], pdf, label=dataset)
        ax_arr[1].plot(bin_edges[:-1], ccdf, label=dataset)

ax_arr[0].set_yscale('log')
ax_arr[0].grid(True)
ax_arr[0].set_xlabel(score_type + '-score')
ax_arr[0].set_ylabel('PDF')
ax_arr[0].legend()

ax_arr[1].set_yscale('log')
ax_arr[1].grid(True)
ax_arr[1].set_xlabel(score_type + '-score')
ax_arr[1].set_ylabel('CCDF')
ax_arr[1].legend()

plt.show()

# %% plot recon pdf per parameter and data set
import alad_mod.testvar as t
from importlib import reload

reload(t)

print(t.x)
