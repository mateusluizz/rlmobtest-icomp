"""Testes para SMART_INPUTS e _detect_field_type() — melhoria #3 (v0.1.13).

Prova que:
- SMART_INPUTS contém valores de fronteira relevantes para cada categoria.
- _detect_field_type() detecta corretamente o tipo do campo a partir do
  resource-id / content-desc, selecionando a categoria de inputs correta.
"""

import pytest

from rlmobtest.android.android_env import SMART_INPUTS, _detect_field_type


# ---------------------------------------------------------------------------
# Estrutura de SMART_INPUTS
# ---------------------------------------------------------------------------


class TestSmartInputsStructure:
    EXPECTED_CATEGORIES = {"email", "password", "number", "text", "date", "phone", "currency"}

    def test_all_categories_present(self):
        assert self.EXPECTED_CATEGORIES.issubset(SMART_INPUTS.keys())

    def test_each_category_non_empty(self):
        for cat, values in SMART_INPUTS.items():
            assert len(values) > 0, f"Categoria '{cat}' está vazia"

    def test_each_category_has_multiple_values(self):
        """Mais de um valor por categoria garante diversidade de boundary testing."""
        for cat, values in SMART_INPUTS.items():
            assert len(values) >= 3, f"Categoria '{cat}' deve ter ≥3 valores"

    def test_empty_string_present_in_all_categories(self):
        """String vazia é o boundary case mais crítico para validação de obrigatoriedade."""
        for cat, values in SMART_INPUTS.items():
            assert "" in values, f"Categoria '{cat}' deve incluir string vazia"

    def test_all_values_are_strings(self):
        for cat, values in SMART_INPUTS.items():
            for v in values:
                assert isinstance(v, str), f"Categoria '{cat}': valor {v!r} não é string"


class TestSmartInputsBoundaryValues:
    """Verifica que cada categoria contém os boundary cases mais relevantes."""

    def test_email_has_invalid_formats(self):
        email_values = SMART_INPUTS["email"]
        # Deve ter pelo menos um formato inválido (sem @)
        has_invalid = any("@" not in v and v != "" for v in email_values)
        assert has_invalid, "SMART_INPUTS['email'] deve incluir formato inválido (sem @)"

    def test_email_has_valid_format(self):
        email_values = SMART_INPUTS["email"]
        has_valid = any("@" in v and "." in v for v in email_values)
        assert has_valid, "SMART_INPUTS['email'] deve incluir ao menos um formato válido"

    def test_number_has_negative(self):
        assert any(v.startswith("-") for v in SMART_INPUTS["number"])

    def test_number_has_zero(self):
        assert "0" in SMART_INPUTS["number"]

    def test_text_has_overflow(self):
        """Texto longo testa truncamento e overflow de campo."""
        long_values = [v for v in SMART_INPUTS["text"] if len(v) > 50]
        assert len(long_values) >= 1, "SMART_INPUTS['text'] deve incluir texto longo (>50 chars)"

    def test_currency_has_negative(self):
        assert any(v.startswith("-") for v in SMART_INPUTS["currency"])

    def test_date_has_invalid_date(self):
        """Datas inválidas como 00/00/0000 testam validação de formato."""
        invalid_dates = [v for v in SMART_INPUTS["date"] if "00" in v or "99" in v]
        assert len(invalid_dates) >= 1


# ---------------------------------------------------------------------------
# Detecção de tipo de campo
# ---------------------------------------------------------------------------


class TestDetectFieldType:
    """Cada método testa um campo com o resource-id / elem típico."""

    # Formato do elem: "{classname} {resourceid} {contentdesc} bounds:{bounds}"

    def test_detects_email(self):
        elem = "android.widget.EditText com.foo:id/input_email  bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "email"

    def test_detects_email_from_content_desc(self):
        elem = "android.widget.EditText com.foo:id/field1 E-mail address bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "email"

    def test_detects_password(self):
        elem = "android.widget.EditText com.foo:id/password_field  bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "password"

    def test_detects_password_from_pwd(self):
        elem = "android.widget.EditText com.foo:id/pwd  bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "password"

    def test_detects_phone(self):
        elem = "android.widget.EditText com.foo:id/phone_number  bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "phone"

    def test_detects_phone_from_tel(self):
        elem = "android.widget.EditText com.foo:id/tel_input  bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "phone"

    def test_detects_currency(self):
        elem = "android.widget.EditText com.foo:id/price_field  bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "currency"

    def test_detects_currency_from_amount(self):
        elem = "android.widget.EditText com.foo:id/amount  bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "currency"

    def test_detects_date(self):
        elem = "android.widget.EditText com.foo:id/date_input  bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "date"

    def test_detects_number(self):
        elem = "android.widget.EditText com.foo:id/number_field  bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "number"

    def test_detects_number_from_qty(self):
        elem = "android.widget.EditText com.foo:id/qty  bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "number"

    def test_unknown_field_defaults_to_text(self):
        elem = "android.widget.EditText com.foo:id/some_random_widget  bounds:[0,0][360,50]"
        assert _detect_field_type(elem) == "text"

    def test_empty_elem_defaults_to_text(self):
        assert _detect_field_type("") == "text"


class TestDetectFieldTypeSelectsCorrectInputs:
    """Prova que detect_field_type → SMART_INPUTS seleciona inputs relevantes."""

    @pytest.mark.parametrize(
        "elem, expected_category",
        [
            ("android.widget.EditText com.foo:id/email_address  bounds", "email"),
            ("android.widget.EditText com.foo:id/password_confirm  bounds", "password"),
            ("android.widget.EditText com.foo:id/mobile_number  bounds", "phone"),
            ("android.widget.EditText com.foo:id/total_amount  bounds", "currency"),
            ("android.widget.EditText com.foo:id/birth_date  bounds", "date"),
            ("android.widget.EditText com.foo:id/age_input  bounds", "number"),
            ("android.widget.EditText com.foo:id/notes_field  bounds", "text"),
        ],
    )
    def test_detected_category_has_inputs(self, elem, expected_category):
        field_type = _detect_field_type(elem)
        assert field_type == expected_category
        assert field_type in SMART_INPUTS
        assert len(SMART_INPUTS[field_type]) > 0
