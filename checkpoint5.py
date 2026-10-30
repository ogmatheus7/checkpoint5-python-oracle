'''
Matheus Yudi - RM571245 - 1TDSPF
Erick Menezes - RM570325 - 1TDSPF
'''

import requests
import oracledb
import getpass

url_api = "https://api.open-meteo.com/v1/forecast"

cidades = [
    {"nome": "São Paulo", "latitude": -23.55, "longitude": -46.63},
    {"nome": "Rio de Janeiro", "latitude": -22.91, "longitude": -43.17},
    {"nome": "Curitiba", "latitude": -25.43, "longitude": -49.27},
    {"nome": "Manaus", "latitude": -3.12, "longitude": -60.02}
]

ddl_tabela = """
CREATE TABLE previsao_tempo (
    id_previsao   NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cidade        VARCHAR2(50)  NOT NULL,
    data_previsao DATE          NOT NULL,
    temp_maxima   NUMBER(4,1)   NOT NULL,
    temp_minima   NUMBER(4,1)   NOT NULL,
    temp_media    NUMBER(4,1)   NOT NULL,
    amplitude     NUMBER(4,1)   NOT NULL,
    classificacao VARCHAR2(10)  NOT NULL,
    chuva_mm      NUMBER(5,1)   NOT NULL,
    nivel_chuva   VARCHAR2(15)  NOT NULL,
    CONSTRAINT uk_cidade_data UNIQUE (cidade, data_previsao)
)
"""

def consultar_previsao(cidade):
    parametros = {
        "latitude": cidade["latitude"],
        "longitude": cidade["longitude"],
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "America/Sao_Paulo",
        "forecast_days": 7
    }

    try:
        resposta = requests.get(url_api, params=parametros, timeout=10)

        if resposta.status_code == 200:
            return resposta.json()["daily"]
        elif resposta.status_code == 404:
            print('[ERRO]: Endereço da API não encontrado (404)!')
        elif resposta.status_code >= 500:
            print(f'[ERRO]: Falha no servidor da API ({resposta.status_code})!')
        else:
            print(f'[ERRO]: A API respondeu com status {resposta.status_code}')

        return None

    except requests.exceptions.RequestException:
        print('[ERRO]: Falha na conexão com a API!')
        return None


def processar_dia(cidade, data, maxima, minima, chuva):
    media = round((maxima + minima) / 2, 1)
    amplitude = round(maxima - minima, 1)

    if media < 18:
        classificacao = "Frio"
    elif media < 24:
        classificacao = "Ameno"
    else:
        classificacao = "Quente"

    if chuva == 0:
        nivel_chuva = "Sem chuva"
    elif chuva <= 5:
        nivel_chuva = "Fraca"
    elif chuva <= 15:
        nivel_chuva = "Moderada"
    else:
        nivel_chuva = "Forte"

    return {
        "cidade": cidade,
        "data": data,
        "maxima": maxima,
        "minima": minima,
        "media": media,
        "amplitude": amplitude,
        "classificacao": classificacao,
        "chuva_mm": chuva,
        "nivel_chuva": nivel_chuva
    }


def processar_previsao(nome_cidade, diario):
    dias = []

    for data, maxima, minima, chuva in zip(
        diario["time"],
        diario["temperature_2m_max"],
        diario["temperature_2m_min"],
        diario["precipitation_sum"]
    ):
        dias.append(processar_dia(nome_cidade, data, maxima, minima, chuva))

    return dias


def conectar_oracle():
    usuario = input('Usuário Oracle: ')
    senha = getpass.getpass('Senha Oracle: ')
    dsn = oracledb.makedsn("oracle.fiap.com.br", 1521, sid="orcl")

    try:
        conexao = oracledb.connect(user=usuario, password=senha, dsn=dsn)
        print('[SUCESSO]: Conectado ao Oracle!')
        return conexao

    except oracledb.DatabaseError as erro:
        print(f'[ERRO]: Não foi possível conectar: {erro}')
        return None


def criar_tabela(conexao):
    try:
        cursor = conexao.cursor()
        cursor.execute(ddl_tabela)
        conexao.commit()
        print('[SUCESSO]: Tabela criada!')

    except oracledb.DatabaseError as erro:
        if erro.args[0].code == 955:
            print('A tabela já existe, seguindo em frente.')
        else:
            print(f'[ERRO]: Falha ao criar a tabela: {erro}')

def salvar_no_oracle(conexao, registros):
    sql = """
        INSERT INTO previsao_tempo
            (cidade, data_previsao, temp_maxima, temp_minima, temp_media,
             amplitude, classificacao, chuva_mm, nivel_chuva)
        VALUES
            (:cidade, TO_DATE(:data, 'YYYY-MM-DD'), :maxima, :minima, :media,
             :amplitude, :classificacao, :chuva_mm, :nivel_chuva)
    """
    inseridos = 0
    repetidos = 0

    try:
        cursor = conexao.cursor()

        for dia in registros:
            try:
                cursor.execute(sql, dia)
                inseridos += 1
            except oracledb.IntegrityError as erro:
                if erro.args[0].code == 1:
                    repetidos += 1
                else:
                    raise

        conexao.commit()
        print(f'[SUCESSO]: {inseridos} registros gravados, {repetidos} já existiam.')

    except oracledb.DatabaseError as erro:
        conexao.rollback()
        print(f'[ERRO]: Falha ao gravar, nada foi salvo: {erro}')


def main():
    registros = []

    for cidade in cidades:
        print(f'\nConsultando {cidade["nome"]}...')
        diario = consultar_previsao(cidade)

        if diario is None:
            continue

        registros.extend(processar_previsao(cidade["nome"], diario))

    print(f'\nTotal de registros: {len(registros)}')

    if len(registros) == 0:
        print('[ERRO]: Nenhum dado para gravar.')
        return

    conexao = conectar_oracle()

    if conexao is None:
        return

    criar_tabela(conexao)
    salvar_no_oracle(conexao, registros)
    conexao.close()


#Principal
main()