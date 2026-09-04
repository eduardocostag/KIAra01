from app.leads import LeadCsvService, LeadStage, LeadStore


def test_csv_round_trip_preserves_stage_and_next_action(tmp_path):
    source = LeadStore(tmp_path / "source.db")
    identifier = source.upsert(company="Empresa RS", location="Porto Alegre", score=82)
    source.update(identifier, stage=LeadStage.PROPOSAL, next_action="Revisar proposta")
    path = tmp_path / "leads.csv"

    assert LeadCsvService().export_file(source, path) == 1

    target = LeadStore(tmp_path / "target.db")
    imported, errors = LeadCsvService().import_file(target, path)
    restored = target.list()[0]
    assert (imported, errors) == (1, ())
    assert restored.stage is LeadStage.PROPOSAL
    assert restored.next_action == "Revisar proposta"


def test_csv_rejects_invalid_stage_without_importing_row(tmp_path):
    path = tmp_path / "invalid.csv"
    path.write_text("empresa,etapa\nEmpresa RS,inexistente\n", encoding="utf-8")
    store = LeadStore(tmp_path / "leads.db")

    imported, errors = LeadCsvService().import_file(store, path)

    assert imported == 0
    assert errors == ("Linha 2: etapa inválida (inexistente)",)
    assert store.list() == []


def test_csv_reconciles_every_row_and_quarantines_anomalies(tmp_path):
    path = tmp_path / "mixed.csv"
    path.write_text(
        "Empresa,score\nValida,75\nFora da faixa,101\nSem score,abc\n",
        encoding="utf-8",
    )
    store = LeadStore(tmp_path / "leads.db")
    service = LeadCsvService()
    imported, errors = service.import_file(store, path)

    assert imported == 1
    assert len(errors) == 2
    assert service.last_reconciliation.source_rows == 3
    assert service.last_reconciliation.reconciled is True
    assert [lead.company for lead in store.list()] == ["Valida"]


def test_csv_rejects_extra_columns_without_silent_loss(tmp_path):
    path = tmp_path / "extra.csv"
    path.write_text("empresa,score\nEmpresa,20,dado-perdido\n", encoding="utf-8")
    store = LeadStore(tmp_path / "leads.db")
    service = LeadCsvService()
    imported, errors = service.import_file(store, path)

    assert imported == 0
    assert errors == ("Linha 2: possui colunas extras",)
    assert service.last_reconciliation.reconciled is True
    assert store.list() == []


def test_csv_round_trip_restores_formula_safe_text_without_stripping_real_apostrophe(tmp_path):
    source = LeadStore(tmp_path / "source.db")
    source.upsert(company="=Empresa Segura", niche="'@literal", qualification="+prioridade")
    path = tmp_path / "leads.csv"

    LeadCsvService().export_file(source, path)
    target = LeadStore(tmp_path / "target.db")
    imported, errors = LeadCsvService().import_file(target, path)

    restored = target.list()[0]
    assert (imported, errors) == (1, ())
    assert restored.company == "=Empresa Segura"
    assert restored.niche == "'@literal"
    assert restored.qualification == "+prioridade"
