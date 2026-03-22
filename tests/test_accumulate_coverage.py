"""Testes para _accumulate_coverage() — melhoria #6 (v0.1.15).

Prova que os arquivos .ec de cada run são copiados corretamente para o
diretório cumulativo compartilhado, sem sobrescrever arquivos já existentes.
"""

import logging

import pytest

from rlmobtest.training.loop import _accumulate_coverage


@pytest.fixture
def logger():
    return logging.getLogger("test_accumulate")


class TestAccumulateCoverageCopies:
    def test_copies_single_ec_file(self, tmp_path, logger):
        src = tmp_path / "coverage"
        dst = tmp_path / "cumulative"
        src.mkdir()
        (src / "coverage_001.ec").write_bytes(b"\xca\xfe\xba\xbe")

        _accumulate_coverage(src, dst, logger)

        assert (dst / "coverage_001.ec").exists()

    def test_copies_multiple_ec_files(self, tmp_path, logger):
        src = tmp_path / "coverage"
        dst = tmp_path / "cumulative"
        src.mkdir()
        (src / "coverage_001.ec").write_bytes(b"data1")
        (src / "coverage_002.ec").write_bytes(b"data2")
        (src / "coverage_003.ec").write_bytes(b"data3")

        _accumulate_coverage(src, dst, logger)

        assert (dst / "coverage_001.ec").exists()
        assert (dst / "coverage_002.ec").exists()
        assert (dst / "coverage_003.ec").exists()

    def test_copied_content_is_identical(self, tmp_path, logger):
        src = tmp_path / "coverage"
        dst = tmp_path / "cumulative"
        src.mkdir()
        original = b"\xca\xfe\xba\xbe\x00\x10\x06"
        (src / "coverage_001.ec").write_bytes(original)

        _accumulate_coverage(src, dst, logger)

        assert (dst / "coverage_001.ec").read_bytes() == original

    def test_creates_cumulative_dir_if_missing(self, tmp_path, logger):
        src = tmp_path / "coverage"
        dst = tmp_path / "nonexistent" / "cumulative"
        src.mkdir()
        (src / "coverage.ec").write_bytes(b"ec")

        _accumulate_coverage(src, dst, logger)

        assert dst.exists()


class TestAccumulateCoverageDoesNotOverwrite:
    """Arquivos já presentes no destino não devem ser sobrescritos.

    Garante que dados de runs anteriores são preservados quando a run atual
    gera um arquivo com o mesmo timestamp — situação improvável mas possível.
    """

    def test_existing_file_not_overwritten(self, tmp_path, logger):
        src = tmp_path / "coverage"
        dst = tmp_path / "cumulative"
        src.mkdir()
        dst.mkdir()

        original_content = b"from_run1"
        new_content = b"from_run2"
        (dst / "coverage_001.ec").write_bytes(original_content)
        (src / "coverage_001.ec").write_bytes(new_content)

        _accumulate_coverage(src, dst, logger)

        assert (dst / "coverage_001.ec").read_bytes() == original_content

    def test_new_files_added_existing_preserved(self, tmp_path, logger):
        src = tmp_path / "coverage"
        dst = tmp_path / "cumulative"
        src.mkdir()
        dst.mkdir()

        (dst / "coverage_001.ec").write_bytes(b"run1")
        (src / "coverage_002.ec").write_bytes(b"run2")

        _accumulate_coverage(src, dst, logger)

        assert (dst / "coverage_001.ec").read_bytes() == b"run1"
        assert (dst / "coverage_002.ec").read_bytes() == b"run2"


class TestAccumulateCoverageEdgeCases:
    def test_empty_source_does_not_create_dst(self, tmp_path, logger):
        src = tmp_path / "coverage"
        dst = tmp_path / "cumulative"
        src.mkdir()

        _accumulate_coverage(src, dst, logger)

        assert not dst.exists()

    def test_nonexistent_source_is_safe(self, tmp_path, logger):
        src = tmp_path / "nonexistent_coverage"
        dst = tmp_path / "cumulative"

        # Não deve lançar exceção
        _accumulate_coverage(src, dst, logger)

        assert not dst.exists()

    def test_non_ec_files_not_copied(self, tmp_path, logger):
        """Apenas .ec são copiados — CSV, HTML, etc. ficam para trás."""
        src = tmp_path / "coverage"
        dst = tmp_path / "cumulative"
        src.mkdir()
        (src / "coverage.ec").write_bytes(b"ec data")
        (src / "jacoco.csv").write_bytes(b"csv data")
        (src / "index.html").write_bytes(b"html")

        _accumulate_coverage(src, dst, logger)

        assert (dst / "coverage.ec").exists()
        assert not (dst / "jacoco.csv").exists()
        assert not (dst / "index.html").exists()

    def test_idempotent_second_call(self, tmp_path, logger):
        """Chamar duas vezes com os mesmos arquivos não duplica nem corrompe."""
        src = tmp_path / "coverage"
        dst = tmp_path / "cumulative"
        src.mkdir()
        (src / "coverage_001.ec").write_bytes(b"data")

        _accumulate_coverage(src, dst, logger)
        _accumulate_coverage(src, dst, logger)

        # Ainda existe e conteúdo intacto
        assert (dst / "coverage_001.ec").read_bytes() == b"data"
