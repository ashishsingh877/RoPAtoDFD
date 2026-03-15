import pandas as pd


def parse_ropa(file):

    df = pd.read_excel(file)

    processes = []

    for _, row in df.iterrows():

        processes.append({
            "process": row.get("Process Name"),
            "data": row.get("Personal Data"),
            "purpose": row.get("Purpose"),
            "system": row.get("System")
        })

    return processes
