from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.leads import CommercialProfile


class CommercialSettingsDialog(QDialog):
    """Guided commercial setup with progressive disclosure for non-specialists."""

    def __init__(self, profile: CommercialProfile, parent: QWidget | None = None) -> None:
        super().__init__(parent, objectName="commercialSettingsDialog")
        self.setWindowTitle("Configurar minha operação")
        self.setMinimumSize(720, 600)
        self.resize(780, 660)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)
        root.addWidget(QLabel("Configurar minha operação", objectName="settingsTitle"))
        intro = QLabel(
            "Conte à Kiara o essencial sobre seu negócio. Você pode começar só pela primeira "
            "etapa e completar o restante quando quiser.",
            objectName="settingsIntro",
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.tabs = QTabWidget(objectName="settingsTabs")
        self.tabs.setAccessibleName("Etapas da configuração comercial")
        root.addWidget(self.tabs, 1)

        self.business = QLineEdit(profile.business_name)
        self.service = QLineEdit(profile.service)
        self.proposition = self._text(profile.value_proposition)
        self.ticket = QDoubleSpinBox()
        self.ticket.setRange(0, 10_000_000)
        self.ticket.setPrefix("R$ ")
        self.ticket.setDecimals(2)
        self.ticket.setValue(profile.average_ticket)
        self.tabs.addTab(self._page(
            "Comece por aqui",
            "Essas informações já permitem que a Kiara entenda o que você vende.",
            (
                ("Nome da empresa ou operação", self.business,
                 "Ex.: Clínica Aurora, Agência Norte ou João Consultoria"),
                ("O que você vende?", self.service,
                 "Descreva o principal serviço ou produto em uma frase"),
                ("Por que o cliente escolheria você?", self.proposition,
                 "Explique o resultado ou benefício mais importante"),
                ("Valor médio da venda", self.ticket,
                 "Use uma estimativa; você poderá alterar depois"),
            ),
        ), "1  Essencial")

        self.niches = QLineEdit(profile.target_niches)
        self.locations = QLineEdit(profile.target_locations)
        self.ideal = self._text(profile.ideal_customer)
        self.tabs.addTab(self._page(
            "Quem a Kiara deve procurar?",
            "Defina o público em linguagem simples. Separe vários itens por vírgula.",
            (
                ("Tipos de clientes", self.niches, "Ex.: clínicas, academias, arquitetos"),
                ("Cidades ou regiões", self.locations, "Ex.: Porto Alegre, Canoas e região"),
                ("Como é o cliente ideal?", self.ideal,
                 "Ex.: empresa com equipe comercial e necessidade de gerar reuniões"),
            ),
        ), "2  Público ideal")

        self.offers = self._text(profile.offers)
        self.differentiators = self._text(profile.differentiators)
        self.cases = self._text(profile.case_studies)
        self.pricing = self._text(profile.pricing_rules)
        self.tabs.addTab(self._page(
            "Prepare a venda",
            "A Kiara usará estas informações para preparar reuniões e propostas.",
            (
                ("Ofertas e pacotes", self.offers, "Liste o que pode ser oferecido"),
                ("Principais diferenciais", self.differentiators,
                 "O que você faz melhor ou de forma diferente?"),
                ("Resultados e provas", self.cases, "Cases, depoimentos ou números verificáveis"),
                ("Como funciona o preço?", self.pricing,
                 "Faixas, condições ou regras que a Kiara deve respeitar"),
            ),
        ), "3  Oferta")

        self.qualification = self._text(profile.qualification_rules)
        self.disqualifiers = self._text(profile.disqualifiers)
        self.discount = self._text(profile.discount_policy)
        self.proposal = self._text(profile.proposal_terms)
        self.contract = self._text(profile.contract_template)
        self.limit = QSpinBox()
        self.limit.setRange(1, 200)
        self.limit.setSuffix(" contatos/dia")
        self.limit.setValue(profile.daily_contact_limit)
        self.tabs.addTab(self._page(
            "Regras e limites",
            "Opcional. Ajuste apenas quando sua operação já tiver regras comerciais definidas.",
            (
                ("Quando um lead está pronto?", self.qualification,
                 "Critérios mínimos para reunião, proposta ou fechamento"),
                ("Quem não deve ser abordado?", self.disqualifiers,
                 "Perfis incompatíveis, restrições e sinais para interromper"),
                ("Limite diário", self.limit, "Evita excesso de contatos na operação"),
                ("Regras de desconto", self.discount, "Limites que nunca devem ser ultrapassados"),
                ("Condições da proposta", self.proposal, "Prazos, validade e condições comerciais"),
                ("Modelo ou orientação de contrato", self.contract,
                 "Texto-base ou instruções; a versão final sempre requer revisão"),
            ),
        ), "4  Avançado")

        note = QLabel(
            "🔒 A Kiara salva estas informações somente no banco local da operação.",
            objectName="settingsPrivacy",
        )
        note.setWordWrap(True)
        root.addWidget(note)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            objectName="settingsButtons",
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar configuração")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    @staticmethod
    def _text(value: str) -> QTextEdit:
        field = QTextEdit(value)
        field.setAcceptRichText(False)
        field.setFixedHeight(62)
        return field

    @staticmethod
    def _value(field: QLineEdit | QTextEdit) -> str:
        return field.text() if isinstance(field, QLineEdit) else field.toPlainText()

    @staticmethod
    def _page(
        title: str,
        description: str,
        rows: Iterable[tuple[str, QWidget, str]],
    ) -> QWidget:
        content = QWidget(objectName="settingsPage")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(QLabel(title, objectName="settingsSectionTitle"))
        copy = QLabel(description, objectName="settingsSectionHelp")
        copy.setWordWrap(True)
        layout.addWidget(copy)
        card = QFrame(objectName="settingsCard")
        form = QFormLayout(card)
        form.setContentsMargins(16, 14, 16, 14)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for label, field, help_text in rows:
            label_box = QWidget()
            label_layout = QVBoxLayout(label_box)
            label_layout.setContentsMargins(0, 3, 0, 0)
            label_layout.setSpacing(2)
            label_layout.addWidget(QLabel(label, objectName="settingsFieldLabel"))
            helper = QLabel(help_text, objectName="settingsFieldHelp")
            helper.setWordWrap(True)
            label_layout.addWidget(helper)
            field.setAccessibleName(label)
            form.addRow(label_box, field)
        layout.addWidget(card)
        layout.addStretch(1)
        scroll = QScrollArea(objectName="settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(scroll)
        return wrapper

    def commercial_profile(self) -> CommercialProfile:
        return CommercialProfile(
            business_name=self.business.text(),
            service=self.service.text(),
            target_niches=self.niches.text(),
            target_locations=self.locations.text(),
            ideal_customer=self.ideal.toPlainText(),
            value_proposition=self.proposition.toPlainText(),
            average_ticket=self.ticket.value(),
            daily_contact_limit=self.limit.value(),
            offers=self.offers.toPlainText(),
            pricing_rules=self.pricing.toPlainText(),
            differentiators=self.differentiators.toPlainText(),
            case_studies=self.cases.toPlainText(),
            qualification_rules=self.qualification.toPlainText(),
            disqualifiers=self.disqualifiers.toPlainText(),
            discount_policy=self.discount.toPlainText(),
            proposal_terms=self.proposal.toPlainText(),
            contract_template=self.contract.toPlainText(),
        )
