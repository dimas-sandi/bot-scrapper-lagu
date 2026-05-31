import json

def check():
    json_path = "download_history.json"
    with open(json_path, 'r', encoding='utf-8') as f:
        history = json.load(f)
        
    print(f"Total keys in download_history.json: {len(history)}")
    
    statuses = {}
    for k, v in history.items():
        status = v.get('status', 'Unknown')
        statuses[status] = statuses.get(status, 0) + 1
        
    print("Status distribution:")
    for status, count in statuses.items():
        print(f"  {status}: {count}")

if __name__ == "__main__":
    check()
