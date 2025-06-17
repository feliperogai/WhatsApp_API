helpers_py = ""
import re
import unicodedata
from typing import Optional, Dict, Any, List
from datetime import datetime
import hashlib
import json

def normalize_phone_number(phone: str) -> str:
    # Remove todos os caracteres não numéricos
    clean_phone = re.sub(r'\\D', '', phone)
    
    # Adiciona código do país se necessário (assume Brasil +55)
    if len(clean_phone) == 11 and clean_phone.startswith('11'):
        clean_phone = '55' + clean_phone
    elif len(clean_phone) == 10:
        clean_phone = '5511' + clean_phone
    elif not clean_phone.startswith('55'):
        clean_phone = '55' + clean_phone
    
    return '+' + clean_phone

def clean_text(text: str) -> str:
    if not text:
        return ""
    
    # Remove acentos e normaliza
    text = unicodedata.normalize('NFKD', text)
    text = ''.join([c for c in text if not unicodedata.combining(c)])
    
    # Remove caracteres especiais mantendo apenas letras, números e espaços
    text = re.sub(r'[^a-zA-Z0-9\\s]', '', text)
    
    # Normaliza espaços
    text = re.sub(r'\\s+', ' ', text).strip()
    
    return text.lower()

def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    if not text:
        return []
    
    # Palavras comuns a ignorar
    stop_words = {
        'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas',
        'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
        'por', 'para', 'com', 'sem', 'sob', 'sobre', 'entre',
        'e', 'ou', 'mas', 'que', 'se', 'quando', 'onde', 'como',
        'eu', 'tu', 'ele', 'ela', 'nos', 'vos', 'eles', 'elas',
        'meu', 'minha', 'seu', 'sua', 'nosso', 'nossa',
        'este', 'esta', 'esse', 'essa', 'aquele', 'aquela',
        'um', 'dois', 'tres', 'quatro', 'cinco', 'muito', 'pouco'
    }
    
    clean = clean_text(text)
    words = clean.split()
    
    keywords = [
        word for word in words 
        if len(word) >= min_length and word not in stop_words
    ]
    
    return list(set(keywords))  # Remove duplicatas

def generate_session_id(phone_number: str) -> str:
    timestamp = datetime.now().isoformat()
    raw_string = f"{phone_number}_{timestamp}"
    return hashlib.md5(raw_string.encode()).hexdigest()[:16]

def format_currency(value: float, currency: str = "BRL") -> str:
    if currency == "BRL":
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        return f"{currency} {value:,.2f}"

def calculate_percentage_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def safe_json_loads(json_str: str, default: Any = None) -> Any:
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default

def format_datetime(dt: datetime, format_str: str = "%d/%m/%Y %H:%M") -> str:
    return dt.strftime(format_str)

def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def create_response_template(agent_name: str, message: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
    return {
        "agent": agent_name,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {}
    } 
