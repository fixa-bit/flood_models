import unittest
import numpy as np
import pandas as pd
from glofas_correction.bias_correction import SeasonalQuantileMapper


class BiasTests(unittest.TestCase):
    def data(self):
        dates = pd.date_range("2018-01-02", "2020-12-31")
        f = pd.DataFrame({"issue_date": dates-pd.Timedelta(days=1), "valid_date": dates, "lead_day": 1,
                          "member": "0", "q_cumecs": np.arange(len(dates))%100+10., "product_kind": "reforecast"})
        o = pd.DataFrame({"q_cumecs": f.q_cumecs.to_numpy()*2}, index=dates)
        return f, o

    def test_future_observations_do_not_change_maps(self):
        f, o = self.data()
        a = SeasonalQuantileMapper().fit(f, o, [2018, 2019])
        o.loc[o.index.year == 2020, "q_cumecs"] = 999999
        b = SeasonalQuantileMapper().fit(f, o, [2018, 2019])
        self.assertEqual(a.to_dict(), b.to_dict())
        self.assertLessEqual(a.fitted_until, pd.Timestamp("2019-12-31"))

    def test_extreme_increments_are_not_capped_or_shrunk(self):
        f, o = self.data()
        mapper = SeasonalQuantileMapper().fit(f, o, [2018, 2019])
        future = f.iloc[:2].copy()
        future["q_cumecs"] = [1000., 2000.]
        result = mapper.transform(future)
        self.assertAlmostEqual(result[1]-result[0], 1000.)
        self.assertGreater(result.max(), o.q_cumecs.max())

    def test_only_reforecasts_may_fit(self):
        f, o = self.data()
        f["product_kind"] = "historical"
        with self.assertRaises(ValueError): SeasonalQuantileMapper().fit(f, o, [2018])


if __name__ == "__main__": unittest.main()
