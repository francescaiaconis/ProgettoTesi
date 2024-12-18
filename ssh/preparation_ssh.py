import json
from collections import defaultdict
from datetime import datetime, timedelta
import csv
import re
import hashlib
import pandas as pd

def label_simulated_attacks(path, output_csv_path): #etichetta i record e filtra quelli richiesta/risposta
    new_dataset = []
    with open(path, 'r') as file:
        for line in file:
            record = json.loads(line.strip())
            if record['source_ip']=='1ccdb898890cce841210e3fb0bcc3e7974f069ca89da96625e7b7699bf277165' and record['dest_ip']=='f4c36b35451f863e37f34989cca218a6e7c40d22f699aafeef3a6d7ae76a75a2':
                record['label']=1
            else:
                record['label']=0
            new_dataset.append(record)

     # Converte la lista filtrata in un DataFrame
    filtered_df = pd.DataFrame(new_dataset)

    # Salva il DataFrame filtrato in un nuovo file CSV
    filtered_df.to_csv(output_csv_path, index=False)

def find_all_ips(data, exclude_ips):# Funzione per trovare gli indirizzi IP nel JSON senza includere combinazioni IP:Porta e quelli in record["related"]["ip"]
    ip_set = set()
    ip_pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')

    def extract_ips(value):
        if isinstance(value, dict):
            for k, v in value.items():
                extract_ips(v)
        elif isinstance(value, list):
            for item in value:
                extract_ips(item)
        elif isinstance(value, str):
            if ip_pattern.fullmatch(value):# Verifica se il valore è esattamente un indirizzo IP e non parte di un'altra stringa
                ip_set.add(value)

    extract_ips(data)
    ip_set -= exclude_ips  # Rimuove gli IP da escludere
    return ip_set

def read_json_file(file_path): # Funzione per leggere un file JSON riga per riga
    data = []
    with open(file_path, 'r') as file:
        for line in file:
            if line.strip():
                try:
                    record = json.loads(line.strip())
                    data.append(record)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON on line: {line.strip()} - {e}")
    return data


def add_ip_to_record(darktrace_ai_analyst):
   
    for record in darktrace_ai_analyst: # Aggiornare i record con i nuovi IP
        exclude_ips = set(record.get("related", {}).get("ip", []))
        ips = find_all_ips(record, exclude_ips)
        for ip in ips:
            record["related"]["ip"].append(ip) #aggiungo gli ip trovati nel messaggio testuale per fare il filtro successivamente
            
    return darktrace_ai_analyst



def calculate_sha256(data):
    if isinstance(data, str):
        data = data.encode()
    sha256_hash = hashlib.sha256(data).hexdigest()
    return sha256_hash

def find_with_dest_ip(timestamp_start, timestamp_end, source_ip, dest_ip, darktrace_raw):
    for _, raw_record in darktrace_raw.iterrows():
        if ((raw_record['@timestamp'] >= timestamp_start and
             raw_record['@timestamp'] <= timestamp_end) and
            raw_record['source_ip'] == calculate_sha256(source_ip) and
            raw_record['dest_ip'] == calculate_sha256(dest_ip)):
            raw_record['label'] = 1
        else:
            if 'label' not in raw_record or pd.isna(raw_record['label']):
                raw_record['label'] = 0

def find_without_dest_ip(timestamp_start, timestamp_end, source_ip, darktrace_raw):
    for _, raw_record in darktrace_raw.iterrows():
        if ((raw_record['@timestamp'] >= timestamp_start and
             raw_record['@timestamp'] <= timestamp_end) and
            raw_record['source_ip'] == calculate_sha256(source_ip)):
            raw_record['label'] = 1
        else:
            if 'label' not in raw_record or pd.isna(raw_record['label']):
                raw_record['label'] = 0

def label_detected_attacks(darktrace_ai_analyst, darktrace_raw_csv_path, output_csv_path):

    darktrace_ai_analyst=add_ip_to_record(darktrace_ai_analyst)
    # Carica il dataset CSV come DataFrame
    darktrace_raw = pd.read_csv(darktrace_raw_csv_path)

    for record in darktrace_ai_analyst:
        source_ip = record["related"]["ip"][0]
        timestamp_start = record["event"]["start"][0][:-5]
        timestamp_end = record["event"]["end"][0][:-5]

        if len(record["related"]["ip"]) > 1:
            for dest_ip in record["related"]["ip"][1:]:
                find_with_dest_ip(timestamp_start, timestamp_end, source_ip, dest_ip, darktrace_raw)
        else:
            find_without_dest_ip(timestamp_start, timestamp_end, source_ip, darktrace_raw)

    # Salva il DataFrame aggiornato come CSV
    darktrace_raw.to_csv(output_csv_path, index=False)


   
def main():
    train_raw_json = "train_ssh_raw.json"
    train_ai_json= "train_ssh_ai.json"
    test_raw_json = "test_ssh_raw.json"
    test_ai_json = "test_ssh_ai.json"

    train_raw_csv = "train_ssh_raw.csv"
    test_raw_csv = "test_ssh_raw.csv"
    print("Etichettamento degli attacchi simulati e rilevati da Darktrace AI Analyst in corso...")
    label_simulated_attacks(train_raw_json, train_raw_csv) #etichetta gli attacchi simulati
    label_simulated_attacks(test_raw_json, test_raw_csv)#etichetta gli attacchi simulati


    darktrace_ai_analyst=read_json_file(train_ai_json) #carica il file json
    label_detected_attacks(darktrace_ai_analyst, train_raw_csv, train_raw_csv) #etichetta gli attacchi rilevati da Darktrace AI Analyst

    darktrace_ai_analyst=read_json_file(test_ai_json) #carica il file json
    label_detected_attacks(darktrace_ai_analyst, test_raw_csv, test_raw_csv) #etichetta gli attacchi rilevati da Darktrace AI Analyst
    print("Etichettamento completato.")

# Esegui il main
if __name__ == "__main__":
    main()