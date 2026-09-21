"""
tests/test_logs
~~~~~~~~~~~~~~~

Testes do módulo de logging estruturado (JSON Lines).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ranking_msc.outputs.logs import JSONLineFormatter, log_execucao, setup_logging


class TestJSONLineFormatter:
    """Testes do formatter JSON Lines."""

    def _make_record(self, msg: str = "teste", **extra: object) -> logging.LogRecord:
        """Cria um LogRecord com extras opcionais."""
        record = logging.LogRecord(
            name="ranking_msc",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for key, value in extra.items():
            setattr(record, key, value)
        return record

    def test_formato_basico_contem_campos_obrigatorios(self) -> None:
        """Saída JSON contém ts, level, logger e msg."""
        formatter = JSONLineFormatter()
        record = self._make_record("mensagem de teste")
        output = formatter.format(record)
        data = json.loads(output)

        assert "ts" in data
        assert data["level"] == "INFO"
        assert data["logger"] == "ranking_msc"
        assert data["msg"] == "mensagem de teste"

    def test_extra_dinamico_capturado(self) -> None:
        """Campos extra={} arbitrários aparecem no JSON de saída."""
        formatter = JSONLineFormatter()
        record = self._make_record(
            "teste extras",
            execucao_id="abc-123",
            competencia="2024-01",
            campo_customizado="valor_custom",
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert data["execucao_id"] == "abc-123"
        assert data["competencia"] == "2024-01"
        assert data["campo_customizado"] == "valor_custom"

    def test_campos_internos_excluidos(self) -> None:
        """Atributos internos do LogRecord não vazam para o JSON."""
        formatter = JSONLineFormatter()
        record = self._make_record("teste internos")
        output = formatter.format(record)
        data = json.loads(output)

        # Campos internos do logging NÃO devem aparecer
        assert "args" not in data
        assert "pathname" not in data
        assert "lineno" not in data
        assert "funcName" not in data
        assert "processName" not in data
        assert "threadName" not in data

    def test_exception_capturada(self) -> None:
        """Quando há exc_info, o campo 'exception' aparece no JSON."""
        formatter = JSONLineFormatter()
        try:
            raise ValueError("erro de teste")
        except ValueError:
            import sys
            record = self._make_record("falhou")
            record.exc_info = sys.exc_info()

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "erro de teste" in data["exception"]

    def test_extra_modulo_e_tabela(self) -> None:
        """Campos 'modulo' e 'tabela' usados pelo ref_loader aparecem no JSON."""
        formatter = JSONLineFormatter()
        record = self._make_record(
            "tabela carregada",
            modulo="ref_loader",
            tabela="pcasp",
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert data["modulo"] == "ref_loader"
        assert data["tabela"] == "pcasp"


class TestLogExecucao:
    """Testes do helper log_execucao."""

    def test_log_execucao_emite_campos_extras(self) -> None:
        """log_execucao emite mensagem com campos estruturados no handler."""
        test_logger = logging.getLogger("ranking_msc.test_log_execucao")
        formatter = JSONLineFormatter()
        handler = logging.Handler()
        handler.setFormatter(formatter)

        records: list[logging.LogRecord] = []
        handler.emit = lambda r: records.append(r)  # type: ignore[assignment]
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        try:
            log_execucao(
                test_logger,
                execucao_id="exec-001",
                competencia="2024-06",
                status="OK",
                message="Pipeline concluído",
                total_pendencias=42,
            )
            assert len(records) == 1
            data = json.loads(formatter.format(records[0]))
            assert data["execucao_id"] == "exec-001"
            assert data["competencia"] == "2024-06"
            assert data["total_pendencias"] == 42
        finally:
            test_logger.removeHandler(handler)

    def test_log_execucao_mensagem_padrao(self) -> None:
        """Sem message explícita, usa formato padrão com execucao_id e status."""
        test_logger = logging.getLogger("ranking_msc.test_log_default")
        formatter = JSONLineFormatter()
        handler = logging.Handler()
        handler.setFormatter(formatter)

        records: list[logging.LogRecord] = []
        handler.emit = lambda r: records.append(r)  # type: ignore[assignment]
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        try:
            log_execucao(
                test_logger,
                execucao_id="exec-002",
                competencia="2024-06",
                status="ERRO",
            )
            assert len(records) == 1
            data = json.loads(formatter.format(records[0]))
            assert "exec-002" in data["msg"]
            assert "ERRO" in data["msg"]
        finally:
            test_logger.removeHandler(handler)


class TestSetupLogging:
    """Testes do setup_logging."""

    def test_setup_cria_logger_com_handlers(self, tmp_path: object) -> None:
        """setup_logging retorna logger com handlers de console e arquivo."""
        logger_name = "ranking_msc"
        logger = logging.getLogger(logger_name)
        # Limpar handlers existentes para teste isolado
        logger.handlers.clear()

        result = setup_logging(log_dir=str(tmp_path))

        assert result.name == logger_name
        assert len(result.handlers) == 2
        # Limpar handlers para não interferir em outros testes
        result.handlers.clear()

    def test_setup_idempotente(self, tmp_path: object) -> None:
        """Chamar setup_logging duas vezes não duplica handlers."""
        logger_name = "ranking_msc"
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()

        setup_logging(log_dir=str(tmp_path))
        result = setup_logging(log_dir=str(tmp_path))

        assert len(result.handlers) == 2
        # Um único handler de cada tipo, não apenas duas contagens coincidentes.
        arquivos = [h for h in result.handlers if isinstance(h, logging.FileHandler)]
        consoles = [
            h
            for h in result.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert len(arquivos) == 1
        assert len(consoles) == 1
        result.handlers.clear()

    def test_setup_com_handler_estranho_ja_anexado_ainda_cria_arquivo(
        self, tmp_path: object
    ) -> None:
        """Com outro handler já no logger, setup_logging ainda anexa o FileHandler do JSONL.

        Este é o cenário real do aplicativo desktop: ``desktop.launcher`` já anexou seu
        próprio handler ao logger ``ranking_msc`` antes de ``setup_logging()`` rodar. A
        guarda antiga ("se já tem handler, não faço nada") deixava o arquivo JSON Lines
        de auditoria sem ser criado nesse caso.
        """
        logger_name = "ranking_msc"
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()

        handler_estranho = logging.StreamHandler()  # stderr, como o do launcher
        logger.addHandler(handler_estranho)
        try:
            result = setup_logging(log_dir=str(tmp_path))
            result.info("linha de teste")

            arquivos = [h for h in result.handlers if isinstance(h, logging.FileHandler)]
            assert len(arquivos) == 1

            jsonl_path = Path(str(tmp_path)) / "ranking_msc.jsonl"
            assert jsonl_path.is_file()
            assert jsonl_path.stat().st_size > 0
        finally:
            logger.handlers.clear()
