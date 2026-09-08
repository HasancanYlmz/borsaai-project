# ---------------------------------------------------------
# BIST30 SECTOR MAPPING
# Portföyün sektörel bazda korunması için kullanılır.
# ---------------------------------------------------------

BIST30_SECTORS = {
    "AKBNK": "BANKACILIK",
    "GARAN": "BANKACILIK",
    "ISCTR": "BANKACILIK",
    "YKBNK": "BANKACILIK",
    
    "KCHOL": "HOLDING",
    "SAHOL": "HOLDING",
    "ALARK": "HOLDING",
    
    "THYAO": "ULASTIRMA",
    "PGSUS": "ULASTIRMA",
    "ASTOR": "ENERJI",
    "ENJSA": "ENERJI",
    
    "TUPRS": "PETROKIMYA",
    "PETKM": "PETROKIMYA",
    
    "EREGL": "DEMIR-CELIK",
    "KRDMD": "DEMIR-CELIK",
    
    "FROTO": "OTOMOTIV",
    "TOASO": "OTOMOTIV",
    "DOAS": "OTOMOTIV",
    
    "BIMAS": "PERAKENDE",
    "ENKAI": "INSAAT",
    "EKGYO": "GAYRIMENKUL",
    "TCELL": "ILETISIM",
    "TTKOM": "ILETISIM",
    
    "SISE": "CAM",
    "KONTR": "TEKNOLOJI",
    "ASELS": "SAVUNMA",
    "SASA": "KIMYA",
    "HEKTS": "TARIM",
    "ODAS": "ENERJI",
    "GUBRF": "GUBRE",
    
    # BIST50 İlaveleri
    "MGROS": "PERAKENDE",
    "SOKM": "PERAKENDE",
    "MAVI": "PERAKENDE",
    "TAVHL": "ULASTIRMA",
    "TTRAK": "OTOMOTIV",
    "CCOLA": "GIDA",
    "AEFES": "GIDA",
    "ULKER": "GIDA",
    "VAKBN": "BANKACILIK",
    "HALKB": "BANKACILIK",
    "ISMEN": "FINANS",
    "DOHOL": "HOLDING",
    "KOZAA": "MADENCILIK",
    "IPEKE": "ENERJI",
    "AKSEN": "ENERJI",
    "GWIND": "ENERJI",
    "ALFAS": "ENERJI",
    "EUPWR": "ENERJI",
    "CWENE": "ENERJI",
    "KORDS": "KIMYA"
}

def get_sector(symbol: str) -> str:
    """Returns the sector for a given symbol, defaults to 'UNKNOWN'."""
    return BIST30_SECTORS.get(symbol, "UNKNOWN")
