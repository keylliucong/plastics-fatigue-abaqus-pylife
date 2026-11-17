"""虚构循环：演示 pyLife 2.3.1 的均值应力变换，不是材料标定。"""
import numpy as np
import pandas as pd
import pylife
import pylife.strength.meanstress  # 注册 pandas accessor

collective = pd.DataFrame({
    'from': [-10.0, 10.0], 'to': [10.0, 30.0], 'cycles': [1.0, 1.0]
})
print('pyLife:', pylife.__version__)
for sensitivity, expected in [(0.0, [10.0, 10.0]), (0.2, [10.0, 12.75]),
                              (0.5, [10.0, 17.142857142857142])]:
    params = pd.Series({'M': sensitivity})
    result = collective.meanstress_transform.fkm_goodman(params, R_goal=-1.0)
    amplitudes = result.amplitude.to_numpy()
    np.testing.assert_allclose(amplitudes, expected)
    print('M:', sensitivity, 'M2:', params['M2'], 'amplitudes:', amplitudes)
