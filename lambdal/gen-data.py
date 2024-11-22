import pandas as pd
from sklearn.preprocessing import MinMaxScaler


scaler = MinMaxScaler()

df = pd.read_csv("results/pytorch-train-throughput-v2-fp16.csv")
numeric_columns = df.select_dtypes(include=['number']).columns
df[numeric_columns] = scaler.fit_transform(df[numeric_columns])

df = df.rename(columns={"Unnamed: 0": "name"})

print(df.to_json(orient='records', indent=2))

