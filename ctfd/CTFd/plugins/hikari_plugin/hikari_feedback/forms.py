"""WTForms binding for the feedback questionnaire.

The form is flat by design — every field is rendered in the template by
walking ``FIELD_GROUPS`` so the visual grouping lives next to the
instrument it implements, not in the storage layer. Optional fields keep
``validators`` minimal; the Pydantic DTO is the authoritative gate.
"""

from typing import Iterable, List, Tuple

from flask_wtf import FlaskForm
from wtforms import HiddenField, IntegerField, SelectField, SelectMultipleField, SubmitField, TextAreaField, widgets
from wtforms.validators import DataRequired, NumberRange, Optional as OptionalValidator

from CTFd.forms import CTFdCSRF


YEARS_BANDS = [
    ("", "—"),
    ("none", "Sem experiência prévia"),
    ("lt_1", "Menos de 1 ano"),
    ("1_2", "1 a 2 anos"),
    ("3_5", "3 a 5 anos"),
    ("6_10", "6 a 10 anos"),
    ("gt_10", "Mais de 10 anos"),
]

PRIMARY_ROLES = [
    ("", "—"),
    ("student", "Estudante"),
    ("soc_analyst_t1", "Analista SOC, nível 1"),
    ("soc_analyst_t2", "Analista SOC, nível 2 ou superior"),
    ("incident_responder", "Respondedor de incidentes"),
    ("threat_hunter", "Threat hunter"),
    ("forensics_analyst", "Analista forense"),
    ("educator", "Educador ou instrutor"),
    ("researcher", "Pesquisador"),
    ("other", "Outro"),
]

PRIOR_CTF_BANDS = [
    ("", "—"),
    ("0", "Nenhum"),
    ("1_3", "1 a 3 eventos"),
    ("4_10", "4 a 10 eventos"),
    ("gt_10", "Mais de 10 eventos"),
]

FORMAL_EDUCATION = [
    ("", "—"),
    ("none", "Sem formação formal em computação ou segurança"),
    ("on_the_job", "Aprendizado prático predominante"),
    ("vendor_certification", "Certificação profissional em tecnologia ou segurança"),
    ("undergraduate_computing", "Graduação em computação ou área próxima"),
    ("undergraduate_cyber", "Graduação com foco em segurança cibernética"),
    ("postgraduate_computing", "Pós-graduação em computação ou área próxima"),
    ("postgraduate_cyber", "Pós-graduação com foco em segurança cibernética"),
    ("other", "Outra formação relevante"),
]

MITRE_TACTICS = [
    ("reconnaissance", "Reconhecimento"),
    ("resource_development", "Preparação de recursos"),
    ("initial_access", "Acesso inicial"),
    ("execution", "Execução"),
    ("persistence", "Persistência"),
    ("privilege_escalation", "Escalação de privilégios"),
    ("defense_evasion", "Evasão de defesa"),
    ("credential_access", "Acesso a credenciais"),
    ("discovery", "Descoberta"),
    ("lateral_movement", "Movimento lateral"),
    ("collection", "Coleta"),
    ("command_and_control", "Comando e controle"),
    ("exfiltration", "Exfiltração"),
    ("impact", "Impacto"),
]


class _MultiCheckbox(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


def _score5(label):
    return IntegerField(label, validators=[OptionalValidator(), NumberRange(min=1, max=5)])


def _score7(label):
    return IntegerField(label, validators=[OptionalValidator(), NumberRange(min=1, max=7)])


def _score10(label):
    return IntegerField(label, validators=[OptionalValidator(), NumberRange(min=0, max=10)])


def _optional_select(label, choices):
    return SelectField(label, choices=choices, validators=[OptionalValidator()])


class FeedbackForm(FlaskForm):
    class Meta:
        csrf = True
        csrf_class = CTFdCSRF
        csrf_field_name = "nonce"

    phase = HiddenField(default="post", validators=[DataRequired()])

    years_cyber_experience = _optional_select("Tempo de experiência em segurança cibernética", YEARS_BANDS)
    primary_role = _optional_select("Função principal", PRIMARY_ROLES)
    prior_ctf_count = _optional_select("Participações anteriores em CTF", PRIOR_CTF_BANDS)
    years_soc_experience = _optional_select("Tempo em SOC ou função equivalente", YEARS_BANDS)
    formal_education = _optional_select("Maior formação concluída ou em andamento", FORMAL_EDUCATION)

    self_cyber_defense_analyst = _score5("Investigar alertas, logs e evidências de defesa cibernética")
    self_incident_responder = _score5("Conduzir resposta técnica a incidentes")
    self_threat_warning_analyst = _score5("Interpretar indícios de ameaça e priorizar alertas")
    self_forensics_analyst = _score5("Analisar evidências forenses de sistemas e redes")
    self_vuln_assessment_analyst = _score5("Avaliar vulnerabilidades e impacto operacional")

    tool_kibana = _score5("Kibana / Elastic")
    tool_kql = _score5("Escrita de consultas KQL")
    tool_attack_framework = _score5("Reconhecimento de etapas de uma cadeia de ataque")
    tool_other_siem = _score5("Uso de outro SIEM, como Splunk ou Sentinel")

    mitre_tactics_practised = _MultiCheckbox(
        "Etapas da cadeia de ataque investigadas durante a competição",
        choices=MITRE_TACTICS,
        validators=[OptionalValidator()],
    )

    tlx_mental_demand = _score7("Esforço mental exigido pelos desafios (1 = baixo, 7 = alto)")
    tlx_temporal_demand = _score7("Pressão de tempo durante a competição (1 = baixa, 7 = alta)")
    tlx_performance = _score7("Dificuldade para chegar à solução (1 = baixa, 7 = alta)")
    tlx_effort = _score7("Esforço geral para concluir os desafios (1 = baixo, 7 = alto)")
    tlx_frustration = _score7("Frustração sentida durante a execução (1 = baixa, 7 = alta)")

    sus_would_use_frequently = _score5("Eu usaria o Hikari em outros treinamentos")
    sus_unnecessarily_complex = _score5("Achei o Hikari mais complexo do que precisava ser")
    sus_easy_to_use = _score5("Achei o Hikari fácil de usar")
    sus_needed_support = _score5("Eu precisaria de suporte técnico para usar o Hikari")
    sus_functions_well_integrated = _score5("As partes do Hikari funcionam de forma integrada")
    sus_too_much_inconsistency = _score5("Percebi inconsistências na experiência de uso")
    sus_quick_to_learn = _score5("A maioria das pessoas aprenderia a usar o Hikari rapidamente")
    sus_cumbersome = _score5("Achei o Hikari trabalhoso de usar")
    sus_felt_confident = _score5("Senti confiança ao usar o Hikari")
    sus_needed_to_learn_a_lot = _score5("Precisei aprender muitas coisas antes de conseguir usar o Hikari")

    learning_log_analysis = _score5("Melhoria percebida: análise de logs")
    learning_pattern_correlation = _score5("Melhoria percebida: correlação entre fontes")
    learning_hypothesis_generation = _score5("Melhoria percebida: geração de hipóteses")
    learning_tool_fluency = _score5("Melhoria percebida: fluência em Kibana e KQL")
    learning_time_to_detect = _score5("Melhoria percebida: tempo até detecção")
    learning_documentation = _score5("Melhoria percebida: documentação da investigação")

    realism_attack_chain = _score5("Realismo da cadeia de ataque")
    realism_telemetry = _score5("Realismo dos logs e eventos disponíveis no SIEM")
    realism_pace = _score5("Realismo do ritmo e da pressão")
    methodology_coherence = _score5("Coerência metodológica do exercício")

    nps_recommend = _score10("Qual é a probabilidade de recomendar o Hikari em treinamentos de defesa cibernética? (0-10)")

    most_valuable_technique = TextAreaField(
        "Técnica ou metodologia mais útil que você utilizou",
        validators=[OptionalValidator()],
    )
    biggest_learning_blocker = TextAreaField(
        "Maior obstáculo ao seu aprendizado nesta execução",
        validators=[OptionalValidator()],
    )
    suggested_scenarios = TextAreaField(
        "Cenários que você gostaria de enfrentar em próximas execuções",
        validators=[OptionalValidator()],
    )
    other_comments = TextAreaField(
        "Outro comentário relevante para registro",
        validators=[OptionalValidator()],
    )

    submit = SubmitField("Enviar respostas")


# Visual grouping for the template. Each tuple is (section_id, title,
# description, list of field names). The template walks this and renders
# matching form fields in order.
FIELD_GROUPS: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    (
        "background",
        "Perfil e exposição prévia",
        "Informe sua experiência para permitir análise por perfil. Responda este questionário após a competição.",
        (
            "years_cyber_experience",
            "primary_role",
            "prior_ctf_count",
            "years_soc_experience",
            "formal_education",
        ),
    ),
    (
        "nice_self",
        "Autoavaliação de competência",
        "Avalie sua aptidão para executar tarefas de defesa cibernética. Escala: 1 = não consigo executar; 5 = consigo executar com autonomia.",
        (
            "self_cyber_defense_analyst",
            "self_incident_responder",
            "self_threat_warning_analyst",
            "self_forensics_analyst",
            "self_vuln_assessment_analyst",
        ),
    ),
    (
        "tool_fluency",
        "Fluência em ferramentas",
        "Informe sua familiaridade com ferramentas e conceitos usados na investigação. Escala: 1 = nunca usei; 5 = consigo orientar outras pessoas.",
        (
            "tool_kibana",
            "tool_kql",
            "tool_attack_framework",
            "tool_other_siem",
        ),
    ),
    (
        "tactics",
        "Táticas de ataque praticadas",
        "Marque as etapas que você reconheceu ou investigou durante a competição.",
        ("mitre_tactics_practised",),
    ),
    (
        "tlx",
        "Carga de trabalho percebida",
        "Responda sobre o esforço exigido pela competição. Escala: 1 = muito baixo; 7 = muito alto. No item de dificuldade, 1 significa baixa dificuldade e 7 significa alta dificuldade.",
        (
            "tlx_mental_demand",
            "tlx_temporal_demand",
            "tlx_performance",
            "tlx_effort",
            "tlx_frustration",
        ),
    ),
    (
        "sus",
        "Usabilidade percebida",
        "Responda sobre a experiência de uso do Hikari. Escala: 1 = discordo totalmente; 5 = concordo totalmente.",
        (
            "sus_would_use_frequently",
            "sus_unnecessarily_complex",
            "sus_easy_to_use",
            "sus_needed_support",
            "sus_functions_well_integrated",
            "sus_too_much_inconsistency",
            "sus_quick_to_learn",
            "sus_cumbersome",
            "sus_felt_confident",
            "sus_needed_to_learn_a_lot",
        ),
    ),
    (
        "learning",
        "Melhoria percebida de habilidades",
        "Compare sua percepção antes e depois da competição. Escala: 1 = sem melhora percebida; 5 = melhora alta.",
        (
            "learning_log_analysis",
            "learning_pattern_correlation",
            "learning_hypothesis_generation",
            "learning_tool_fluency",
            "learning_time_to_detect",
            "learning_documentation",
        ),
    ),
    (
        "realism",
        "Realismo e metodologia",
        "Avalie a fidelidade do exercício. Escala: 1 = pouco realista ou pouco coerente; 5 = compatível com operações reais.",
        (
            "realism_attack_chain",
            "realism_telemetry",
            "realism_pace",
            "methodology_coherence",
        ),
    ),
    (
        "advocacy",
        "Recomendação",
        "Use 0 para nenhuma chance de recomendação e 10 para recomendação muito provável.",
        ("nps_recommend",),
    ),
    (
        "reflections",
        "Reflexões qualitativas",
        "Campos opcionais para registrar detalhes que as escalas não capturam.",
        (
            "most_valuable_technique",
            "biggest_learning_blocker",
            "suggested_scenarios",
            "other_comments",
        ),
    ),
)


def iter_groups(form: FeedbackForm) -> Iterable[Tuple[str, str, str, List]]:
    for section_id, title, description, names in FIELD_GROUPS:
        fields = [getattr(form, name) for name in names]
        yield section_id, title, description, fields
