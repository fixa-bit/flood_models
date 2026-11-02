"""Shared CLI; LSTM training implementation lives in lstm/train.py."""
from lstm.train import check_evaluation_years, device_for, load_checkpoint, main, run_training, seed_everything

if __name__ == '__main__':
    main()
