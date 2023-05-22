from typing import List, Tuple
import os
import matplotlib as mpl
import matplotlib.pyplot as plt
mpl.rcParams['svg.fonttype'] = 'none' # Takes care that texts show up when
# importing pdf-plots into Inkcape

import numpy as np
import pandas as pd
import seaborn as sns

from src.definitions import RESULTS_DIR, okabe_ito_palette

def read_results_csv(filename):
    df = pd.read_csv(filename, index_col=0)
    if "filename" in df.columns:
        df.drop("filename", axis=1, inplace=True)
    if "Method" in df.columns:
        df.drop("Method", axis=1, inplace=True)
    return df


def results_file_iter(
    methods: List[str],
    segmentation: str,
    permuted: bool,
    adjusted: bool,
):
    def is_adjusted(afile):
        return not afile.endswith('unadjusted')

    def is_unadjusted(afile):
        return afile.endswith('unadjusted')

    def is_permuted(afile):
        return afile.startswith('run_permuted')

    def is_unpermuted(afile):
        return afile.startswith('run_unpermuted')

    filters = []
    if permuted:
        filters.append(is_permuted)
    else:
        filters.append(is_unpermuted)

    if adjusted:
        filters.append(is_adjusted)
    else:
        filters.append(is_unadjusted)

    subfolder_prefix = 'permuted' if permuted else 'unpermuted'

    for file in os.listdir(RESULTS_DIR):
        if all(f(file) for f in filters):
            for sub_folder in os.listdir(RESULTS_DIR / file):
                if sub_folder.startswith(subfolder_prefix):
                    for method in methods:
                        yield (
                            method,
                            RESULTS_DIR / file / sub_folder / method / 'test'
                            / f'roc_auc_{segmentation}_{subfolder_prefix}.csv'
                        )


def load_test_auc_data(methods: List[str], segmentation: str = "freesurfer"):
    """Loads experimental results and puts AUC values in a format compatible
    with 'auc_violinplot'

    Args:
        methods: List of methods (models) that should be included in output
        segmentation: Name of segmentation algorithm.

    Returns:
        mean_unpermuted_aucs: Dictionary of mean AUCs on original dataset
        permuted_aucs: Dataframe of mean AUCs of predictions on permuted
            datasets
        unpermuted_aucs: Dictionary of all AUCs on original dataset
    """
    unpermuted_aucs = {m: {} for m in methods}
    mean_unpermuted_aucs = {m: {} for m in methods}
    permuted_aucs = {'Method': [], 'Diagnosis': [], 'mean_auc': []}
    for method, file in results_file_iter(methods, segmentation, permuted=False, adjusted=True):
        df = read_results_csv(file)
        assert df.shape[0] == 150
        for diagnosis, series in df.items():
            if diagnosis not in unpermuted_aucs[method].keys():
                unpermuted_aucs[method][diagnosis] = []
            unpermuted_aucs[method][diagnosis].extend(
                series.values
            )

    for method, file in results_file_iter(methods, segmentation, permuted=True, adjusted=True):
        df = read_results_csv(file)
        assert df.shape[0] == 5
        for diagnosis, mean_auc in df.mean().items():
            permuted_aucs['Method'].append(method)
            permuted_aucs['Diagnosis'].append(diagnosis)
            permuted_aucs['mean_auc'].append(mean_auc)

    for method in methods:
        for diagnosis in unpermuted_aucs[method].keys():
            mean_unpermuted_aucs[method][diagnosis] = np.mean(
                unpermuted_aucs[method][diagnosis]
            )

    return mean_unpermuted_aucs, pd.DataFrame(permuted_aucs), unpermuted_aucs


def load_test_auc_unadjusted_data(methods: List[str], segmentation: str = "freesurfer"):
    unperm_unadj_aucs = {m: {} for m in methods}
    mean_unperm_unadj_aucs = {m: {} for m in methods}

    for method, file in results_file_iter(methods, segmentation, permuted=False, adjusted=False):
        df = read_results_csv(file)
        for diagnosis in df.columns:
            if diagnosis not in unperm_unadj_aucs[method].keys():
                unperm_unadj_aucs[method][diagnosis] = []
            unperm_unadj_aucs[method][diagnosis].extend(
                list(df[diagnosis])
            )

    for method in methods:
        for diagnosis in unperm_unadj_aucs[method].keys():
            mean_unperm_unadj_aucs[method][diagnosis] = np.mean(
                unperm_unadj_aucs[method][diagnosis]
            )

    return mean_unperm_unadj_aucs, unperm_unadj_aucs


def auc_violinplot(permuted_aucs: pd.DataFrame,
                   unpermuted_aucs: dict,
                   methods_to_plot: List[str],
                   xlims: tuple = (0.425, 0.575),
                   alpha: float = 0.05) -> 'plt.figure':
    """Displays and returns violinplot of ROC AUC values

    Args:
        permuted_aucs: AUC values of predictions on permuted datasets (generated
            by 'load_test_auc_data')
        unpermuted_aucs: AUC values of predictions on original dataset
            (generated by 'load_test_auc_data')
        methods_to_plot: List of exactly two methods that should be plotted.
            Methods must occur in permuted_aucs['Method'] and be a key in
            permuted_aucs.
        xlims: Range of AUC values to plot
        alpha: Significance level alpha. p-values will be printed bold when they
            are below this number.

    Returns:
        Violin plot
    """

    if len(methods_to_plot) != 2:
        raise ValueError('methods_to_plot must contain exactly two elements!')

    # Change labels for legend annotations
    new_labels = {
        'logistic_regression_ovr': 'LRC',
        'logistic_regression_cce': 'LR CCE',
        'xgboost_cce': 'GBM CCE',
    }
    _permuted_aucs = permuted_aucs[
        permuted_aucs['Method'].isin(methods_to_plot)
    ]
    for old, short in new_labels.items():
        _permuted_aucs.loc[
            _permuted_aucs['Method'] == old, 'Method'
        ] = f'Permuted ({short})'
    colors = ['darkgrey', 'lightgrey']
    colors_bars = [okabe_ito_palette['vermillion'], 'white']

    # Plot violinplots of permuted dataset AUCs
    fig = plt.figure(figsize=(11, 14))
    #sns.set_style(style='whitegrid')
    ax = sns.violinplot(
        y='Diagnosis',
        x='mean_auc',
        hue='Method',
        data=_permuted_aucs,
        palette=colors,
        whis=4,
        orient='h',
        hue_order=[f'Permuted ({new_labels[m]})' for m in methods_to_plot],
        zorder=1,
        split=True
    )

    # Plot adjustments
    # Style
    ax_color = 'darkgray'
    ax.spines['bottom'].set_color(ax_color)
    ax.spines['top'].set_color(ax_color)
    ax.spines['right'].set_color(ax_color)
    ax.spines['left'].set_color(ax_color)
    ax.set_axisbelow(True)
    ax.grid(color=ax_color, axis='x')
    ax.set_xlim(xlims)
    ax.set_xlabel('$\\overline{AUC}$', fontsize=24, labelpad=10)  # '$\\overline{AUC}$'
    ax.set_ylabel('')
    ax.set_yticklabels([
        'Major depressive disorder',
        'Bipolar disorder',
        'Psychotic symptoms',
        'ADHD',
        'Oppositional defiant disorder',
        'Conduct disorder',
        'PTSD',
        'Obsessive-compulsive disorder'
    ])
    ax.tick_params(labelsize=20, left=False)
    ax.axvline(
        x=0.5, linestyle=(0, (4, 3)), linewidth=1, color='black', zorder=1.5
    )
    y_offset = 0.18
    markersize = 150
    marker = 'd'

    # Plot AUCs of original datasets
    for i, diagnosis in enumerate(permuted_aucs['Diagnosis'].unique()):
        for j, method in enumerate(methods_to_plot):
            plt.scatter(
                x=unpermuted_aucs[method][diagnosis],
                y=i - y_offset + j * 2 * y_offset,
                facecolors=colors_bars[j],
                edgecolors='black',
                alpha=1,
                marker=marker,
                s=markersize,
                zorder=2,
                label=f'Original ({new_labels[method]})' if i == 0 else None
            )

    #Show p-values
    def mark_significance(p_val: float) -> Tuple[str, str]:
        if p_val <= alpha:
            str1 = '\\pmb{{'
            str2 = '}}'
        else:
            str1 = str2 = ''
        return str1, str2

    p_values = permutation_test(permuted_aucs, unpermuted_aucs)
    for i, diagnosis in enumerate(permuted_aucs['Diagnosis'].unique()):
        for j, method in enumerate(methods_to_plot):
            plt.annotate(
                text=f'$p = {p_values[method][diagnosis]:.3f}$',
                #text=f'$p = {str1}{p_values[method][diagnosis]:.3f}{str2}$',
                xy=(0.617, i - y_offset + j * 2 * y_offset),
                size=20
            )

    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.08), fontsize=18, ncol=2)
    plt.show()
    return fig


def permutation_test(permuted_aucs: pd.DataFrame,
                     unpermuted_aucs: dict) -> dict:
    """ Perform permutation test from
    Ojala, M., & Garriga, G. C. (2010). Permutation tests for studying
    classifier performance. Journal of Machine Learning Research, 11(6).

    Args:
        permuted_aucs: Mean AUCs on permuted datasets
        unpermuted_aucs: Mean AUCs on unpermuted dataset

    Returns:
        Dict of dicts containing calculated p values
    """
    p_values = {m: {} for m in permuted_aucs['Method'].unique()}
    for method in permuted_aucs['Method'].unique():
        for diagnosis in permuted_aucs['Diagnosis'].unique():
            permuted = permuted_aucs.loc[
                (permuted_aucs['Method'] == method) & (permuted_aucs['Diagnosis'] == diagnosis),
                'mean_auc'
            ]
            p_values[method][diagnosis] = (sum(
                    permuted >= unpermuted_aucs[method][diagnosis]
            ) + 1) / (len(permuted) + 1)

    return p_values