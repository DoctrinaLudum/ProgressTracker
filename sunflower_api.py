# sunflower_api.py
import requests
import logging

# Configuração do Logging para este módulo
# É uma boa prática cada módulo ter seu próprio logger.
log = logging.getLogger(__name__)

# Constante específica da API
API_BASE_URL = "https://api.sunflower-land.com/community/farms/"

def get_farm_data_full(farm_id):
    """Busca os dados completos da API do Sunflower Land para um farm_id."""
    if not farm_id or not farm_id.isdigit():
        log.warning(f"Tentativa com Farm ID inválido: {farm_id}")
        return None, "Farm ID inválido. Por favor, insira apenas números."

    api_url = f"{API_BASE_URL}{farm_id}"
    log.info(f"Buscando dados da API para Farm ID {farm_id}: {api_url}")
    response = None
    try:
        response = requests.get(api_url, timeout=15) # Timeout de 15 segundos
        response.raise_for_status() # Levanta erro para status 4xx ou 5xx

        try:
            data = response.json()
            if 'farm' in data:
                log.info(f"Dados obtidos com sucesso para Farm ID: {farm_id}")
                return data, None # Retorna dados e None para erro
            else:
                log.warning(f"Resposta da API OK (status {response.status_code}) mas sem chave 'farm' para Farm ID: {farm_id}. Resposta: {response.text[:200]}...")
                return None, "A resposta da API foi recebida, mas parece incompleta (sem dados da fazenda)."
        except requests.exceptions.JSONDecodeError:
            log.exception(f"Erro ao decodificar JSON (Status {response.status_code}) para Farm ID: {farm_id}. Resposta: {response.text[:200]}...")
            return None, "A API retornou uma resposta que não é um JSON válido."

    except requests.exceptions.Timeout:
        log.error(f"Erro de Timeout ao conectar com a API para Farm ID: {farm_id}")
        return None, "A API demorou muito para responder (Timeout)."
    except requests.exceptions.HTTPError as http_err:
         status_code = http_err.response.status_code if http_err.response is not None else None
         if status_code == 404:
             log.warning(f"Erro ao buscar dados: Farm ID {farm_id} não encontrado (404).")
             return None, f"Fazenda com ID {farm_id} não encontrada. Verifique o número."
         else:
             error_detail = str(http_err)
             try:
                 if http_err.response is not None and http_err.response.content:
                     error_detail = http_err.response.json().get('message', error_detail)
             except (requests.exceptions.JSONDecodeError, AttributeError):
                 pass
             log.error(f"Erro HTTP inesperado (Status {status_code or 'N/A'}) ao buscar dados para Farm ID {farm_id}: {error_detail}")
             return None, f"Erro ao buscar dados da API (Código: {status_code or 'N/A'}). Tente novamente mais tarde."
    except requests.exceptions.RequestException as e:
        log.exception(f"Erro de conexão genérico com a API para Farm ID {farm_id}: {e}")
        return None, f"Erro de conexão ao tentar acessar a API do Sunflower Land: {e}"
    except Exception as e_geral:
        log.exception(f"Erro inesperado na função get_farm_data_full para Farm {farm_id}: {e_geral}")
        return None, "Ocorreu um erro inesperado no processamento dos dados da fazenda."

    status_code_fallback = response.status_code if response is not None else 'N/A'
    log.error(f"Erro desconhecido (Status {status_code_fallback}) ao buscar dados para Farm ID {farm_id}.")
    return None, f"Ocorreu um erro desconhecido (Código: {status_code_fallback}) ao buscar os dados."