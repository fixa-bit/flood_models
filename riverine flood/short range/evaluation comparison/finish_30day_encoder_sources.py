"""Create the next model's comparison/report code from the common experiment pattern."""
from pathlib import Path

SHORT = Path(__file__).resolve().parent.parent
GROUP = SHORT / 'model/model_30_days'
SOURCE = GROUP / 'Hindcast-forecast LSTM/climatology_residual_ensemble/evaluate.py'
TARGET = GROUP / 'Encoder-decoder LSTM/finetuned_15_to_30/evaluate.py'


def main():
    if TARGET.exists():
        raise FileExistsError('Preserve the current evaluator')
    text = SOURCE.read_text(encoding='utf-8')
    text = text.replace('ResidualLSTM', 'EncoderDecoderLSTM')
    text = text.replace('Raw_residual_ensemble', 'Raw_seq2seq_ensemble').replace('Residual_ensemble', 'Seq2seq_30d_ensemble')
    text = text.replace('climatology_residual_ensemble', 'encoder_decoder_finetuned_15_to_30')
    text = text.replace("('past_discharge_predictions', 'LSTM_30d_pastQ', 'Past_discharge_LSTM')]:",
                        "('past_discharge_predictions', 'LSTM_30d_pastQ', 'Past_discharge_LSTM'),\n                                   ('best_ensemble_predictions', 'Residual_ensemble', 'Previous_best_ensemble')]:")
    text = text.replace("'Weather_only_LSTM', 'Past_discharge_LSTM', 'Persistence']", "'Weather_only_LSTM', 'Past_discharge_LSTM', 'Previous_best_ensemble', 'Persistence']")
    text = text.replace("'Smooth_climatology', 'Past_discharge_LSTM', 'Persistence'):", "'Smooth_climatology', 'Previous_best_ensemble', 'Past_discharge_LSTM', 'Persistence'):")
    text = text.replace("'new_seed_models': len(paths),", "'new_seed_models': len(paths), 'source_horizon': 15, 'forecast_horizon': 30,\n                'inherited_training_years': checkpoints[0]['training_years'],\n                'inherited_selection_years': checkpoints[0]['selection_years'],\n                'donor_basins': checkpoints[0].get('pretraining_basins', []),")
    text = text.replace("'smooth_climatology_day30_nse': float(final.loc['Smooth_climatology', 'NSE']),", "'smooth_climatology_day30_nse': float(final.loc['Smooth_climatology', 'NSE']),\n                'previous_best_day30_nse': float(final.loc['Previous_best_ensemble', 'NSE']),")
    text = text.replace('Thirty-day climatology-residual LSTM ensemble', 'Thirty-day encoder-decoder LSTM: fine-tuned from the saved 15-day model')
    text = text.replace("'The encoder and decoder start from the saved past-discharge LSTM; the extra climatology input column is zero-initialized. Mean and quantile heads are new.",
                        "'The encoder, decoder and quantile head start from the saved 15-day CAMELS-US/Marala model. Lead vectors 1-15 are copied exactly; leads 16-30 initially copy day 15, and every lead remains trainable. The extra climatology input column is zero-initialized. The mean head is new; the transferred ordered log-quantile head is converted to physical flow for training.")
    text = text.replace("'The mean-flow head predicts a correction", "'This 32-unit encoder-decoder reads 365 days of ERA5-Land precipitation, temperature and past observed discharge, then decodes all 30 forecast-weather leads in one call. Its two weather inputs and smaller network differ from the previous best 64-unit, eight-weather-input ensemble, so performance differences do not isolate architecture. The mean-flow head predicts a correction")
    text = text.replace("'Both the original and smoothed climatology controls are reported", "'The source donor pretraining used 1985-1994, with donor selection 1995-1996; local fine-tuning used 2016-2020 and selection 2021. All inherited years are carried into the new checkpoints and checked against benchmark years. Both the original and smoothed climatology controls are reported")
    text = text.replace("f'beats the smoothed control: **{manifest[\"beats_smooth_climatology_day30\"]}**.')", "f'beats the smoothed control: **{manifest[\"beats_smooth_climatology_day30\"]}**. '\n               f'Previous best ensemble NSE: **{manifest[\"previous_best_day30_nse\"]:.3f}**.')")
    text = text.replace('One three-seed ensemble', 'One three-seed encoder-decoder ensemble')
    TARGET.write_text(text, encoding='utf-8')
    print(TARGET)


if __name__ == '__main__':
    main()
