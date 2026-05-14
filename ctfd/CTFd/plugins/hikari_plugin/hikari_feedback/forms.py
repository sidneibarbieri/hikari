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
    ("none", "Sem formação formal na área"),
    ("on_the_job", "Aprendizado prático no trabalho"),
    ("vendor_certification", "Certificações profissionais"),
    ("undergraduate_computing", "Graduação em computação ou área correlata"),
    ("undergraduate_cyber", "Graduação específica em segurança cibernética"),
    ("postgraduate_computing", "Pós-graduação em computação ou área correlata"),
    ("postgraduate_cyber", "Pós-graduação específica em segurança cibernética"),
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
    formal_education = _optional_select("Formação em segurança cibernética", FORMAL_EDUCATION)

    self_cyber_defense_analyst = _score5("Analista de defesa cibernética (NICE PR-CDA-001)")
    self_incident_responder = _score5("Respondedor de incidentes cibernéticos (NICE PR-CIR-001)")
    self_threat_warning_analyst = _score5("Analista de ameaças e alertas (NICE AN-TWA-001)")
    self_forensics_analyst = _score5("Analista forense de defesa cibernética (NICE IN-FOR-001)")
    self_vuln_assessment_analyst = _score5("Analista de avaliação de vulnerabilidades (NICE PR-VAM-001)")

    tool_kibana = _score5("Kibana / Elastic")
    tool_kql = _score5("Escrita de consultas KQL")
    tool_attack_framework = _score5("Navegação em táticas e técnicas de ataque")
    tool_other_siem = _score5("Outro SIEM (Splunk, Sentinel, ...)")

    mitre_tactics_practised = _MultiCheckbox(
        "Táticas exercitadas durante esta execução",
        choices=MITRE_TACTICS,
        validators=[OptionalValidator()],
    )

    tlx_mental_demand = _score7("Demanda mental exigida pelo exercício")
    tlx_temporal_demand = _score7("Pressão de tempo durante o exercício")
    tlx_performance = _score7("Desempenho percebido (1 = consegui executar bem; 7 = tive muita dificuldade)")
    tlx_effort = _score7("Esforço necessário para concluir as tarefas")
    tlx_frustration = _score7("Frustração durante a execução")

    sus_would_use_frequently = _score5("Eu usaria este sistema com frequência (SUS-1)")
    sus_unnecessarily_complex = _score5("Achei o sistema desnecessariamente complexo (SUS-2)")
    sus_easy_to_use = _score5("Achei o sistema fácil de usar (SUS-3)")
    sus_needed_support = _score5("Eu precisaria de suporte técnico para usar o sistema (SUS-4)")
    sus_functions_well_integrated = _score5("As funções do sistema são bem integradas (SUS-5)")
    sus_too_much_inconsistency = _score5("Percebi inconsistências demais no sistema (SUS-6)")
    sus_quick_to_learn = _score5("A maioria das pessoas aprenderia a usar rapidamente (SUS-7)")
    sus_cumbersome = _score5("Achei o sistema trabalhoso de usar (SUS-8)")
    sus_felt_confident = _score5("Senti confiança ao usar o sistema (SUS-9)")
    sus_needed_to_learn_a_lot = _score5("Precisei aprender muito antes de usar o sistema (SUS-10)")

    learning_log_analysis = _score5("Melhoria percebida: análise de logs")
    learning_pattern_correlation = _score5("Melhoria percebida: correlação entre fontes")
    learning_hypothesis_generation = _score5("Melhoria percebida: geração de hipóteses")
    learning_tool_fluency = _score5("Melhoria percebida: fluência em Kibana e KQL")
    learning_time_to_detect = _score5("Melhoria percebida: tempo até detecção")
    learning_documentation = _score5("Melhoria percebida: documentação da investigação")

    realism_attack_chain = _score5("Realismo da cadeia de ataque")
    realism_telemetry = _score5("Realismo da telemetria")
    realism_pace = _score5("Realismo do ritmo e da pressão")
    methodology_coherence = _score5("Coerência metodológica do exercício")

    nps_recommend = _score10("Qual a probabilidade de recomendar o Hikari? (0-10)")

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

    submit = SubmitField("Enviar feedback")


# Visual grouping for the template. Each tuple is (section_id, title,
# description, list of field names). The template walks this and renders
# matching form fields in order.
FIELD_GROUPS: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    (
        "background",
        "Perfil e exposição prévia",
        "Informe sua experiência prévia para permitir análise por perfil. O questionário deve ser preenchido após a competição.",
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
        "Avalie sua aptidão atual em papéis profissionais de defesa cibernética. Escala: 1 = nenhuma aptidão; 5 = consigo executar com autonomia.",
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
        "1 = nunca usei; 5 = consigo ensinar outras pessoas.",
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
        "Marque as etapas da cadeia de ataque que você reconheceu ou investigou durante a competição.",
        ("mitre_tactics_practised",),
    ),
    (
        "tlx",
        "Carga de trabalho percebida",
        "Responda sobre o esforço exigido pela competição. Escala: 1 = muito baixo; 7 = muito alto.",
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
        "Responda sobre a experiência de uso da plataforma. Escala: 1 = discordo totalmente; 5 = concordo totalmente.",
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
        "Preencha após o exercício. 1 = sem mudança; 5 = melhoria substancial.",
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
        "Preencha após o exercício. 1 = pouco realista ou incoerente; 5 = compatível com operações reais.",
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
        "Preencha após o exercício.",
        ("nps_recommend",),
    ),
    (
        "reflections",
        "Reflexões qualitativas",
        "Texto livre. Opcional, mas útil para análise.",
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
