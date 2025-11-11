#!/usr/bin/env python3


import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import argparse
import sys
import warnings

def parse_bandwidth_csv(filepath, mode):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            df = pd.read_csv(filepath, header=[0, 1], skipinitialspace=True)
    except pd.errors.EmptyDataError:
        print("Error: CSV file contains no data.")
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing CSV: {e}")
        sys.exit(1)

    cols = df.columns.to_list()

    if 'Date' in cols[0][1] and 'Time' in cols[1][1]:
        cols[0] = ('Info', 'Date')
        cols[1] = ('Info', 'Time')
    else:
        print("Error: CSV header does not match expected format.")
        sys.exit(1)

    df.columns = pd.MultiIndex.from_tuples(cols)

    try:
        df['Datetime'] = pd.to_datetime(df[('Info', 'Date')] + ' ' + df[('Info', 'Time')], errors='coerce')
        df = df.set_index('Datetime')
        df = df.drop('Info', axis=1, level=0)
        df = df.dropna(axis=0, how='all')
    except Exception as e:
        print(f"Error processing date/time: {e}")
        sys.exit(1)

    if df.empty:
        print("Error: No valid data after cleaning.")
        sys.exit(1)

    sockets = sorted([s for s in df.columns.get_level_values(0).unique() if s.startswith('SKT')])
    if not sockets:
        print("Error: No 'SKT' socket columns found in CSV.")
        sys.exit(1)

    plt.figure(figsize=(16, 10))
    print(f"Sockets detected: {', '.join(sockets)}")
    print(f"Mode: {mode}")

    type_colors = {'DRAM': 'tab:red', 'PMM': 'tab:orange', 'CXL': 'tab:green'}
    type_styles = {'Read': '-', 'Write': '--', 'Total': 'solid'}

    all_skt_data = {}

    for skt in sockets:
        skt_df = df[skt]
        plot_data = pd.DataFrame(index=skt_df.index)

        def to_numeric_safe(col_name):
            if col_name in skt_df.columns:
                return pd.to_numeric(skt_df[col_name].astype(str).str.strip(), errors='coerce').fillna(0)
            return pd.Series(0, index=plot_data.index)

        plot_data['DRAM_Read'] = to_numeric_safe('Mem Read (MB/s)')
        plot_data['DRAM_Write'] = to_numeric_safe('Mem Write (MB/s)')
        plot_data['PMM_Read'] = to_numeric_safe('PMM_Read (MB/s)')
        plot_data['PMM_Write'] = to_numeric_safe('PMM_Write (MB/s)')

        cxl_cols = [c for c in skt_df.columns if c.startswith('CXL.')]
        cxl_read_cols = [c for c in cxl_cols if 'Read' in c or 'dv->hst' in c]
        cxl_write_cols = [c for c in cxl_cols if 'Write' in c or 'hst->dv' in c]

        plot_data['CXL_Read'] = skt_df[cxl_read_cols].apply(lambda x: pd.to_numeric(x.astype(str).str.strip(), errors='coerce')).sum(axis=1).fillna(0) if cxl_read_cols else 0
        plot_data['CXL_Write'] = skt_df[cxl_write_cols].apply(lambda x: pd.to_numeric(x.astype(str).str.strip(), errors='coerce')).sum(axis=1).fillna(0) if cxl_write_cols else 0

        all_skt_data[skt] = plot_data

    for skt in sockets:
        data = all_skt_data[skt]

        if mode == 'total':
            plt.plot(data.index, data['DRAM_Read'] + data['DRAM_Write'], label=f'{skt} DRAM Total', color=type_colors['DRAM'], linestyle=type_styles['Total'])
            if data['PMM_Read'].sum() + data['PMM_Write'].sum() > 0:
                plt.plot(data.index, data['PMM_Read'] + data['PMM_Write'], label=f'{skt} PMM Total', color=type_colors['PMM'], linestyle=type_styles['Total'])
            if data['CXL_Read'].sum() + data['CXL_Write'].sum() > 0:
                plt.plot(data.index, data['CXL_Read'] + data['CXL_Write'], label=f'{skt} CXL Total', color=type_colors['CXL'], linestyle=type_styles['Total'])
        else:
            plt.plot(data.index, data['DRAM_Read'], label=f'{skt} DRAM Read', color=type_colors['DRAM'], linestyle=type_styles['Read'])
            plt.plot(data.index, data['DRAM_Write'], label=f'{skt} DRAM Write', color=type_colors['DRAM'], linestyle=type_styles['Write'])
            if data['PMM_Read'].sum() + data['PMM_Write'].sum() > 0:
                plt.plot(data.index, data['PMM_Read'], label=f'{skt} PMM Read', color=type_colors['PMM'], linestyle=type_styles['Read'])
                plt.plot(data.index, data['PMM_Write'], label=f'{skt} PMM Write', color=type_colors['PMM'], linestyle=type_styles['Write'])
            if data['CXL_Read'].sum() + data['CXL_Write'].sum() > 0:
                plt.plot(data.index, data['CXL_Read'], label=f'{skt} CXL Read', color=type_colors['CXL'], linestyle=type_styles['Read'])
                plt.plot(data.index, data['CXL_Write'], label=f'{skt} CXL Write', color=type_colors['CXL'], linestyle=type_styles['Write'])

    plt.title("Memory Bandwidth per Socket")
    plt.xlabel("Time")
    plt.ylabel("Bandwidth (MB/s)")
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize='small')

    plt.grid(True, linestyle='solid', alpha=0.6)

    ax = plt.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax.xaxis.set_major_locator(plt.MaxNLocator(10))
    plt.xticks(rotation=30, ha='right')

    plt.tight_layout(rect=[0, 0, 0.85, 1])
    plt.show()
    plt.savefig("bandwidth.png")

def main():
    parser = argparse.ArgumentParser(description="Visualize pcm-memory.x CSV bandwidth data.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-f', '--file', required=True, help="Input CSV file path")
    parser.add_argument('-m', '--mode', choices=['rw', 'total'], default='rw', help="Chart mode: rw - read/write; total - total bandwidth")
    args = parser.parse_args()
    parse_bandwidth_csv(args.file, args.mode)

if __name__ == "__main__":
    main()