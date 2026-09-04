"""Human approval inbox for the governed Instagram B2C pilot."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.automation.instagram_governance import GovernedDM, InstagramDMGovernance
from app.security.kill_switch import KillSwitch


class InstagramInbox(QWidget):
    """Review governed drafts. Approval never invokes the messaging client."""

    action_changed = Signal(str, str)

    def __init__(
        self,
        governance: InstagramDMGovernance,
        kill_switch: KillSwitch,
        *,
        actor_provider: Callable[[], str],
        configuration: Mapping[str, bool | str] | None = None,
        qualification_provider: Callable[[GovernedDM], Mapping[str, object]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, objectName="instagramInbox")
        self._governance = governance
        self._kill_switch = kill_switch
        self._actor_provider = actor_provider
        self._configuration = dict(configuration or {})
        self._qualification_provider = qualification_provider
        self._actions: list[GovernedDM] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(QLabel("INSTAGRAM B2C", objectName="cockpitEyebrow"))
        layout.addWidget(QLabel("Caixa de entrada assistida", objectName="cockpitPageTitle"))
        subtitle = QLabel(
            "A Kiara qualifica e prepara rascunhos. Uma pessoa aprova cada resposta; "
            "este painel nunca envia mensagens automaticamente.",
            objectName="cockpitMuted",
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.safety_status = QLabel(objectName="instagramSafetyStatus")
        self.safety_status.setWordWrap(True)
        layout.addWidget(self.safety_status)
        self.configuration_status = QLabel(objectName="instagramConfigurationStatus")
        self.configuration_status.setWordWrap(True)
        layout.addWidget(self.configuration_status)

        body = QHBoxLayout()
        self.table = QTableWidget(0, 4, objectName="instagramApprovalTable")
        self.table.setAccessibleName("Rascunhos do Instagram aguardando decisao humana")
        self.table.setHorizontalHeaderLabels(["Contato", "Status", "Tentativas", "Rascunho"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._show_selected)
        body.addWidget(self.table, 3)

        detail = QFrame(objectName="instagramApprovalDetail")
        detail_layout = QVBoxLayout(detail)
        detail_layout.addWidget(QLabel("DETALHE E QUALIFICACAO", objectName="cockpitEyebrow"))
        self.detail = QLabel("Selecione um rascunho.", objectName="cockpitDetailBody")
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail_layout.addWidget(self.detail)
        detail_layout.addStretch(1)
        controls = QHBoxLayout()
        self.approve_button = QPushButton("Aprovar rascunho", objectName="primaryAction")
        self.approve_button.setAccessibleName("Aprovar rascunho sem enviar")
        self.block_button = QPushButton("Bloquear", objectName="dangerAction")
        self.block_button.setAccessibleName("Bloquear resposta do Instagram")
        controls.addWidget(self.approve_button)
        controls.addWidget(self.block_button)
        detail_layout.addLayout(controls)
        body.addWidget(detail, 2)
        layout.addLayout(body, 1)

        self.approve_button.clicked.connect(self._approve)
        self.block_button.clicked.connect(self._block)
        self.refresh()

    def refresh(self) -> None:
        self._actions = list(self._governance.list_actions())
        globally_stopped = self._kill_switch.stopped
        delivery_enabled = self._governance.is_enabled()
        if globally_stopped:
            safety = "PARADA GLOBAL ATIVA - aprovacoes e envios bloqueados."
        elif delivery_enabled:
            safety = "Entrega governada habilitada; envio ainda exige aprovacao humana separada."
        else:
            safety = "Modo seguro: entrega desabilitada pelo kill switch do Instagram."
        self.safety_status.setText(safety)
        self.safety_status.setProperty("stopped", globally_stopped or not delivery_enabled)
        self.configuration_status.setText(self._safe_configuration_summary())
        self.table.setRowCount(len(self._actions))
        for row, action in enumerate(self._actions):
            values = (
                f"...{action.recipient_hash[-8:]}",
                action.status.replace("_", " ").title(),
                str(action.attempts),
                action.draft,
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        if self._actions:
            self.table.selectRow(0)
        else:
            self.detail.setText("Nenhum rascunho governado na fila.")
            self._update_buttons(None)

    def _safe_configuration_summary(self) -> str:
        labels = {
            "webhook_configured": "Webhook",
            "credentials_configured": "Credenciais",
            "account_configured": "Conta Instagram",
        }
        parts = []
        for key, label in labels.items():
            value = self._configuration.get(key, False)
            parts.append(f"{label}: {'configurado' if value is True else 'pendente'}")
        return " | ".join(parts) + " | Segredos ocultos"

    def _selected(self) -> GovernedDM | None:
        row = self.table.currentRow()
        return self._actions[row] if 0 <= row < len(self._actions) else None

    def _show_selected(self) -> None:
        action = self._selected()
        if action is None:
            self._update_buttons(None)
            return
        qualification = dict(self._qualification_provider(action)) if self._qualification_provider else {}
        lines = [
            f"Contato anonimizado: ...{action.recipient_hash[-8:]}",
            f"Status: {action.status}",
            "Consentimento: inbound DM do Instagram; revalidado antes do envio",
            f"Qualificacao: {qualification.get('readiness', 'revisao humana necessaria')}",
            f"Necessidade: {qualification.get('declared_need', 'nao informada')}",
            "",
            "Rascunho preparado:",
            action.draft,
        ]
        self.detail.setText("\n".join(lines))
        self._update_buttons(action)

    def _update_buttons(self, action: GovernedDM | None) -> None:
        actionable = action is not None and action.status in {
            "pending_approval", "approved", "retry_wait"
        }
        self.approve_button.setEnabled(
            bool(action and action.status == "pending_approval" and not self._kill_switch.stopped)
        )
        self.block_button.setEnabled(actionable and not self._kill_switch.stopped)

    def _human_actor(self) -> str:
        actor = self._actor_provider().strip()
        if not actor or actor == "kiara":
            raise ValueError("Identifique o operador humano antes de decidir.")
        return actor

    def _approve(self) -> None:
        action = self._selected()
        if action is None or self._kill_switch.stopped:
            return
        try:
            changed = self._governance.approve(action.id, actor=self._human_actor())
        except ValueError as exc:
            QMessageBox.warning(self, "Aprovacao bloqueada", str(exc))
            return
        if changed:
            self.action_changed.emit(action.id, "approved")
        self.refresh()

    def _block(self) -> None:
        action = self._selected()
        if action is None or self._kill_switch.stopped:
            return
        try:
            changed = self._governance.block(action.id, actor=self._human_actor())
        except ValueError as exc:
            QMessageBox.warning(self, "Bloqueio nao aplicado", str(exc))
            return
        if changed:
            self.action_changed.emit(action.id, "blocked_by_operator")
        self.refresh()
