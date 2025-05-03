# --- Versão da Aplicação ---
APP_VERSION = "0.1.0"

# Data final da temporada atual (ATUALIZE A CADA TEMPORADA)
SEASON_END_DATE = "2025-07-31" # Exemplo: Final de Julho de 2025

# Nome do Token Sazonal (Atualize a cada temporada)
SEASONAL_TOKEN_NAME = "Genissed"

# --- Itens da Loja Sazonal e Custos ---
# Estrutura: "Nome Exato do Item": {"cost": VALOR, "currency": "ticket" ou "sfl", "tier": 1/2/3/4}
SEASONAL_SHOP_ITEMS = {
    # Tier 1 (Normal) - 
    "Balloon Rug":           {"cost": 5, "currency": "sfl", "tier": 1}, # Ignorar nos cálculos de ticket
    "Amberfall Suit":        {"cost": 20,  "currency": "broken_pillar", "tier": 1}, # !! CUSTO BAIXO - BOM PARA DESBLOQUEIO?
    "Embersteel Suit":       {"cost": 50,  "currency": "ticket", "tier": 1}, # !!
    "Treasure Key":          {"cost": 200, "currency": "ticket", "tier": 1}, # !!
    "Bronze Flower Box":     {"cost": 250, "currency": "ticket", "tier": 1}, # !!
    "Flower Mask":           {"cost": 300, "currency": "ticket", "tier": 1}, # !!

    # Tier 2 (Rare) - Requer 4x T1 diferentes (tickets)
    "Glacierguard Suit":     {"cost": 60,  "currency": "sfl", "tier": 2}, # Ignorar
    "Blooomwarden Suit":     {"cost": 80,  "currency": "broken_pillar", "tier": 2}, # Ignorar
    "Rare Key":              {"cost": 500, "currency": "ticket", "tier": 2}, # !!
    "Love Charm Shirt":      {"cost": 650, "currency": "ticket", "tier": 2}, # !!
    "Silver Flower Box":     {"cost": 750, "currency": "ticket", "tier": 2}, # !!
    "Giant Yam":             {"cost": 2000,"currency": "ticket", "tier": 2}, # !!

    # Tier 3 (Epic) - Requer 4x T2 diferentes (tickets)
    "Frost Sword":           {"cost": 180, "currency": "broken_pillar", "tier": 3}, # Ignorar
    "Heart Air Balloon":     {"cost": 200, "currency": "sfl", "tier": 3}, # Ignorar
    "Luxury Key":            {"cost": 1000,"currency": "ticket", "tier": 3}, # !!
    "Flower-Scribed Statue": {"cost": 1500,"currency": "ticket", "tier": 3}, # !!
    "Gold Flower Box":       {"cost": 1500,"currency": "ticket", "tier": 3},
    "Giant Zucchini":        {"cost": 3000,"currency": "ticket", "tier": 3}, # !!

    # Tier 4 (Mega) - Requer 4x T3 diferentes (tickets)
    "Giant Kale":            {"cost": 6000, "currency": "ticket", "tier": 4},
    "Oracle Syringe":        {"cost": 8500, "currency": "ticket", "tier": 4}        
}

# Dicionário de Recompensas Base (existente)
BASE_DELIVERY_REWARDS = {
    "pumpkin' pete": 1,
    "bert": 2,
    "finley": 2,
    "miranda": 2,
    "finn": 3,
    "raven": 3,
    "cornwell": 4,
    "jester": 4,
    "timmy": 4,
    "pharaoh": 5,
    "tywin": 5,
}

# --- CONSTANTES PARA BÔNUS E TOKEN SAZONAL ---



# Dicionário de Buffs Sazonais para Entregas
# ##########################################################################
# ## ATENÇÃO! VERIFIQUE OS NOMES DOS ITENS ABAIXO CONTRA O JSON REAL!   ##
# ## Os nomes aqui DEVEM ser IDÊNTICOS aos identificadores usados na API ##
# ## quando os itens estiverem ativos/equipados/colocados.             ##
# ##########################################################################
SEASONAL_DELIVERY_BUFFS = {
    # Tipo 'vip': Verifica se o VIP está ativo
    "vip": {"type": "vip", "bonus": 2},

    # Tipo 'equipped': Verifica se o VALOR abaixo existe em farm.bumpkin.equipped.* OU farm.farmHands.bumpkins.*.equipped.*
    "Flower Mask": {"type": "equipped", "bonus": 1},      # <<< VERIFICAR NOME EXATO NO JSON!
    "Love Charm Shirt": {"type": "equipped", "bonus": 1}, # <<< VERIFICAR NOME EXATO NO JSON!

    # Tipo 'collectible': Verifica se a CHAVE abaixo existe em farm.home.collectibles OU farm.collectibles
    "Heart Air Balloon": {"type": "collectible", "bonus": 1}, # <<< VERIFICAR NOME EXATO NO JSON!

    # Adicionar outros buffs futuros aqui
}

