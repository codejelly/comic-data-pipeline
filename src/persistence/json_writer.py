import json
from pathlib import Path
from typing import List, Dict, Any, Union

def save_json_log(
    data: Union[List[Any], Dict[str, Any]], 
    output_path: Union[str, Path]
) -> Union[List[Any], Dict[str, Any]]:
    """
    Generic utility to safely write structured data (dict or list) to a 
    JSON file, auto-creating parent directories if missing.
    
    Returns the original data intact so it can be chained in pipelines.
    """
    out_file = Path(output_path)
    
    # Auto-create directories (e.g., creating 'data/logs/' automatically)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f" Successfully logged data payload to: {out_file.resolve()}")
    return data