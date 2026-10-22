import pandas as pd
import numpy as np
import h5py

def messzeit_utc_handling(df, handling):
    if "messzeit_utc" in df.columns:
        df["messzeit_utc"] = pd.to_datetime(df["messzeit_utc"], utc=True)

        if handling.get("extract_time", False):
            df["hour_sin"] = np.sin(2 * np.pi * df["messzeit_utc"].dt.hour / 24)
            df["hour_cos"] = np.cos(2 * np.pi * df["messzeit_utc"].dt.hour / 24)
            
        if handling.get("extract_doy", False):
            doy = df["messzeit_utc"].dt.dayofyear
            angle = (doy + 11) % 365 / 365 * 2 * np.pi 
            df["doy_cos"] = (-np.cos(angle) + 1) / 2
            
        return df

def get_feature_lists(config):
    scale_list = []
    pass_list = []

    for key, subkeys in config['preprocessing']['SB_measured_values'].items():
        for sub in subkeys:
            scale_list.append(f"{key}_{sub}")

    if config['preprocessing']['neighboring_senseBoxes']:
        num_neighbors = config['preprocessing']['number_of_neighbors'][1]
        for i in range(1, num_neighbors + 1):
            for key, subkeys in config['preprocessing']['measured_values_neighbors'].items():
                for sub in subkeys:
                    scale_list.append(f"{key}_{sub}_neighbor_{i}")

    time_cfg = config['preprocessing']['feature_engineering']['measurement_time_handling']
    if time_cfg.get('extract_time'):
        pass_list.append("hour_sin")
        pass_list.append("hour_cos")
    if time_cfg.get('extract_doy'):
        pass_list.append("doy_cos")

    return scale_list, pass_list