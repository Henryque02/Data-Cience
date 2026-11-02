"""Walk-forward respeita o tempo e as métricas conferem com contas à mão."""

import numpy as np
import pandas as pd

from abertura.models import (CLASSES, add_aligned_features, confusion, scores, walk_forward_predict,
                             walk_forward_windows)

GAP = 'y_gap_class'


def table(rows=900, seed=0):
    dates = pd.bdate_range('2020-01-01', periods=rows, name='date_brt')
    signal = np.random.default_rng(seed).normal(size=rows)
    labels = np.select([signal > 0.5, signal < -0.5], ['alta', 'baixa'], 'normal')
    return pd.DataFrame({'x_pre_a': signal, GAP: labels}, index=dates)


class Recorder:
    """Modelo real mínimo que registra as datas vistas no treino e no teste."""

    seen = []

    def fit(self, features, target):
        self.classes_ = np.array(sorted(set(target)))
        self.last_train = features.index.max()
        return self

    def predict_proba(self, features):
        Recorder.seen.append((self.last_train, features.index.min()))
        return np.full((len(features), len(self.classes_)), 1 / len(self.classes_))


def test_windows_train_before_test_and_step_forward():
    dates = pd.DatetimeIndex(['2020-01-01', '2022-08-01'])
    windows = walk_forward_windows(dates, 2, 3, 3)
    assert windows[0] == (pd.Timestamp('2020-01-01'), pd.Timestamp('2022-01-01'), pd.Timestamp('2022-04-01'))
    assert windows[1] == (pd.Timestamp('2020-04-01'), pd.Timestamp('2022-04-01'), pd.Timestamp('2022-07-01'))
    assert len(windows) == 3


def test_model_never_trains_on_test_dates():
    Recorder.seen = []
    result = walk_forward_predict(table(), GAP, ['x_pre_a'], Recorder, train_years=2, test_months=3, step_months=3)
    assert len(Recorder.seen) >= 3
    assert all(last_train < first_test for last_train, first_test in Recorder.seen)
    assert result.index.min() >= pd.Timestamp('2022-01-01')
    assert result.index.is_unique


def test_class_missing_from_training_gets_zero_probability():
    data = table()
    data[GAP] = data[GAP].replace('baixa', 'normal')
    result = walk_forward_predict(data, GAP, ['x_pre_a'], Recorder, train_years=2, test_months=3, step_months=3)
    assert result['baixa'].eq(0).all()
    assert list(result.columns[:3]) == CLASSES[GAP]


def test_rows_with_missing_feature_leave_the_sample():
    data = table()
    data.loc[data.index[-1], 'x_pre_a'] = np.nan
    result = walk_forward_predict(data, GAP, ['x_pre_a'], Recorder, train_years=2, test_months=3, step_months=3)
    assert data.index[-1] not in result.index


def test_scores_match_hand_computation():
    predictions = pd.DataFrame({'baixa': [0.5, 0.0], 'normal': [0.25, 1.0], 'alta': [0.25, 0.0],
                                'y_true': ['baixa', 'alta'], 'y_pred': ['baixa', 'normal']})
    result = scores(predictions, CLASSES[GAP])
    assert result['n'] == 2
    assert result['accuracy'] == 0.5
    assert np.isclose(result['brier'], ((0.25 + 0.0625 + 0.0625) + (0 + 1 + 1)) / 2)


def test_confusion_keeps_class_order_with_true_labels_in_rows():
    predictions = pd.DataFrame({'y_true': ['alta', 'alta', 'baixa'], 'y_pred': ['alta', 'normal', 'alta']})
    result = confusion(predictions, CLASSES[GAP])
    assert list(result.index) == CLASSES[GAP] == list(result.columns)
    assert result.loc['alta', 'normal'] == 1
    assert result.loc['baixa', 'alta'] == 1
    assert result.loc['normal'].sum() == 0


def test_aligned_features_measure_return_in_gap_direction():
    data = pd.DataFrame({'x_open_gap': [0.01, -0.01], 'x_pre_spx_overnight': [0.02, 0.02]})
    result = add_aligned_features(data, ['x_pre_spx_overnight'])
    assert result.x_open_aligned_spx_overnight.tolist() == [0.02, -0.02]
