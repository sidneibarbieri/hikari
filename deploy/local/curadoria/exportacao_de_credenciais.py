"""Curadoria dos desafios construídos sobre o log de exportação de credenciais.

O log guarda nove mil e novecentos e oitenta e oito registros de exportação, um
por conta, cada um com o valor que a aplicação armazenava no campo de senha.
Os desafios pedem que o competidor reconheça o que aquele valor é: uma
codificação reversível, um resumo de uma família conhecida, ou uma derivação de
chave que carrega os próprios parâmetros.

Três decisões de curadoria valem registro.

A categoria não é "Criptografia". O vocabulário do Hikari são as táticas do
ATT&CK, e o que estes desafios exercitam é leitura de material de credencial;
inventar uma categoria fora do vocabulário para dez desafios quebraria a
classificação de todos os outros.

Três contas aparecem duas vezes no log, com valores diferentes em cada
registro, porque a aplicação exportou a mesma conta antes e depois de uma troca
de algoritmo. O enunciado original não avisava disso, e quem encontrasse o
registro "errado" chegaria a outra resposta. Os enunciados afetados passam a
dizer que a conta aparece mais de uma vez e qual das duas assinaturas interessa,
descrevendo a propriedade em vez de entregar o valor.

Um desafio foi descartado. O log guardava, para joao.costa25@hotmail.com, um
resumo que não corresponde à senha que a especificação declarava como resposta:
md5 da constante mais "senha123" produz a9b741f6..., e o log traz 7e668643....
A construção está correta nas outras duas contas conferidas, então o defeito é
do valor gravado, não da regra. Sem preimagem conhecida para o valor gravado,
não há resposta possível, e a habilidade que o desafio exercitava já é coberta
por "A Tabela Pré-Computada", sobre dado que fecha.

A cadeia é progressiva de propósito. Reconhecer Base64 vem antes de reconhecer
MD5 pelo comprimento, que vem antes de derivar o tamanho em bytes, que vem
antes de reverter um resumo conhecido. Um competidor que não sabe o que é um
resumo aprende a distinguir pelos primeiros e chega aos últimos com o conceito
formado.
"""

CONTA_DO_PEPPER = "marta.santos89@yahoo.com.br"

EXPORTACAO_DE_CREDENCIAIS = {
    "chave": "exportacao-de-credenciais",
    "titulo": "Exportação de Credenciais",
    "conjunto": "credenciais",
    "desafios": [
        {
            "chave": "a-constante-da-aplicacao",
            "nome": "A Constante da Aplicação",
            "categoria": "Acesso a Credenciais",
            "dificuldade": "Fácil",
            "flag": "reseg26!",
            "descricao": (
                "Um serviço de exportação despejou em log o conteúdo do campo de senha de "
                "cada conta. No registro de marta.santos89@yahoo.com.br o valor não é um "
                "resumo: é uma cadeia que pode ser revertida, e o texto que ela esconde "
                "contém duas partes coladas.\n\n"
                "A análise de comportamento já apontava que a senha escolhida por essa "
                "usuária era gremio6502. Informe a outra parte, a constante que a aplicação "
                "acrescenta antes de calcular qualquer coisa."
            ),
            "dica": (
                "O valor não tem tamanho fixo nem é hexadecimal, e termina de um jeito que "
                "denuncia o formato de transporte. A reversão é direta e existe em qualquer "
                "linguagem."
            ),
        },
        {
            "chave": "trinta-e-dois-caracteres",
            "nome": "Trinta e Dois Caracteres",
            "categoria": "Acesso a Credenciais",
            "dificuldade": "Fácil",
            "flag": "md5",
            "depende": ["a-constante-da-aplicacao"],
            "descricao": (
                "A conta root.santos15@outlook.com aparece duas vezes na exportação, porque "
                "foi despejada antes e depois de uma troca de algoritmo. Um dos registros "
                "traz um bloco hexadecimal de comprimento fixo.\n\n"
                "Informe o nome da função de resumo que produz uma saída desse tamanho."
            ),
            "dica": (
                "Conte os caracteres do bloco hexadecimal e converta para bits: cada "
                "caractere carrega quatro. O resultado é a assinatura de uma família só."
            ),
        },
        {
            "chave": "quarenta-caracteres",
            "nome": "Quarenta Caracteres",
            "categoria": "Acesso a Credenciais",
            "dificuldade": "Fácil",
            "flag": "sha-1",
            "depende": ["trinta-e-dois-caracteres"],
            "descricao": (
                "O registro de tiago.silva70@gmail.com traz um bloco hexadecimal mais longo "
                "que o do desafio anterior. O comprimento continua sendo o que identifica a "
                "função, sem precisar reverter nada.\n\n"
                "Informe o nome da função que produz uma saída desse tamanho."
            ),
            "dica": (
                "A diferença para o caso anterior é de oito caracteres. A função é a "
                "antecessora direta da família que veio depois."
            ),
        },
        {
            "chave": "o-peso-em-bytes",
            "nome": "O Peso em Bytes",
            "categoria": "Acesso a Credenciais",
            "dificuldade": "Médio",
            "flag": "20",
            "depende": ["quarenta-caracteres"],
            "descricao": (
                "Reconhecida a função usada no registro de tiago.silva70@gmail.com, uma "
                "pergunta de dimensionamento: o que se vê no log é a representação em texto, "
                "não o que a memória guarda. Um caractere hexadecimal não é um byte.\n\n"
                "Informe quantos bytes o resumo ocupa de fato."
            ),
            "dica": (
                "Cada caractere hexadecimal representa metade de um byte. A conta é uma "
                "divisão simples sobre o comprimento que você já contou."
            ),
        },
        {
            "chave": "duzentos-e-cinquenta-e-seis-bits",
            "nome": "Duzentos e Cinquenta e Seis Bits",
            "categoria": "Acesso a Credenciais",
            "dificuldade": "Fácil",
            "flag": "sha-256",
            "depende": ["quarenta-caracteres"],
            "descricao": (
                "O registro de dev.silva51@bol.com.br traz um bloco hexadecimal maior que os "
                "dois anteriores. Ele pertence à família que sucedeu a função do desafio "
                "passado, e o membro da família se identifica pelo tamanho da saída.\n\n"
                "Informe o nome da primitiva usada."
            ),
            "dica": (
                "O nome dessa família termina com o número de bits da saída. Converta o "
                "comprimento em bits e o nome se escreve sozinho."
            ),
        },
        {
            "chave": "a-senha-que-nao-foi-protegida",
            "nome": "A Senha Que Não Foi Protegida",
            "categoria": "Acesso a Credenciais",
            "dificuldade": "Médio",
            "flag": "1234567821",
            "depende": ["a-constante-da-aplicacao"],
            "descricao": (
                "O registro de pedro.costa37@gmail.com não passou por função de resumo "
                "nenhuma: o valor foi apenas serializado, do mesmo jeito que no primeiro "
                "caso desta investigação. Quem tiver o log tem a senha.\n\n"
                "Informe a senha em texto claro escolhida pelo usuário, sem a constante da "
                "aplicação."
            ),
            "dica": (
                "Reverta a codificação e separe o que sobra da constante que você já "
                "identificou. O que resta é a senha."
            ),
        },
        {
            "chave": "a-tabela-pre-computada",
            "nome": "A Tabela Pré-Computada",
            "categoria": "Acesso a Credenciais",
            "dificuldade": "Difícil",
            "flag": "flamengo8277",
            "depende": ["a-senha-que-nao-foi-protegida", "trinta-e-dois-caracteres"],
            "descricao": (
                "A conta admin.souza58@uol.com.br aparece duas vezes na exportação. Um dos "
                "registros usa uma derivação moderna, com parâmetros embutidos; o outro usa "
                "a função legada de 128 bits, para a qual existem tabelas pré-computadas "
                "publicamente consultáveis.\n\n"
                "Use o registro legado, reverta o resumo e informe apenas a senha original, "
                "sem a constante da aplicação."
            ),
            "dica": (
                "O registro de interesse é o bloco hexadecimal curto, não o que começa com "
                "cifrão. Lembre que o valor submetido à função inclui a constante na frente."
            ),
        },
        {
            "chave": "o-sal-embutido",
            "nome": "O Sal Embutido",
            "categoria": "Acesso a Credenciais",
            "dificuldade": "Difícil",
            "flag": "MC45MTQwMjc2NjEwMDk5Mj",
            "depende": ["trinta-e-dois-caracteres"],
            "descricao": (
                "A conta marta.pereira99@protonmail.com também aparece duas vezes, e um dos "
                "registros usa uma função de derivação de chave, não um resumo simples. Esse "
                "tipo de função guarda dentro da própria saída o identificador do algoritmo, "
                "o custo de execução e o sal aleatório, tudo separado por delimitadores.\n\n"
                "Informe apenas a subcadeia correspondente ao sal."
            ),
            "dica": (
                "O formato separa suas seções por cifrão. Depois do identificador e do "
                "custo vem um trecho de comprimento fixo que é o sal, e só depois dele "
                "começa o resumo."
            ),
        },
        {
            "chave": "o-sufixo-de-quatro-digitos",
            "nome": "O Sufixo de Quatro Dígitos",
            "categoria": "Acesso a Credenciais",
            "dificuldade": "Difícil",
            "flag": "password4438",
            "depende": ["a-tabela-pre-computada", "duzentos-e-cinquenta-e-seis-bits"],
            "descricao": (
                "A conta privilegiada fernanda.oliveira44@gmail.com guarda um resumo de 256 "
                "bits, para o qual não existe tabela pública que resolva o caso. O relatório "
                "de inteligência, porém, diz que essa usuária monta a senha sempre do mesmo "
                "jeito: uma palavra-base seguida de quatro dígitos.\n\n"
                "Sabendo que a aplicação acrescenta a constante antes de calcular, determine "
                "a senha original completa."
            ),
            "dica": (
                "O espaço de busca é pequeno: uma palavra-base provável e dez mil sufixos. "
                "Um laço curto que monte constante mais palavra mais número e compare o "
                "resumo resolve em segundos."
            ),
        },
    ],
}
